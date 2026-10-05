"""Vigilance monitor tests. Offline: all network responses come from tests/fixtures."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from vigil import bfarm, cli, fda
from vigil.digest import render_markdown, write_csv
from vigil.schema import Incident, dedupe
from vigil.state import State
from vigil.tagger import Rules, tag

pytestmark = pytest.mark.vigil
FIX = Path(__file__).parent / "fixtures"


def _fx(name: str) -> str:
    return (FIX / name).read_text(encoding="utf-8")


class FakeClient:
    """Stands in for CachedClient; serves fixture files by URL."""

    def __init__(self, *a, **k) -> None:
        self.n_network = 0
        self.n_cache = 0

    def get_text(self, url: str, params=None, ttl_s=None) -> str:
        if url.endswith("RSSNewsfeed.xml?nn=597716"):
            return _fx("bfarm_rss.xml")
        if "kundeninfo" in url:  # reuse one detail page, swap in this notice's number
            num = url.rsplit("/", 1)[1].split("_")[0].replace("-", "/")
            return _fx("bfarm_detail.html").replace("39225/26", num)
        if "_node.html" in url:
            return _fx("bfarm_list_page1.html")
        raise KeyError(url)

    def get_json(self, url: str, params=None, ttl_s=None) -> dict:
        name = {
            "event.json": "fda_event_llz.json",
            "recall.json": "fda_recall_llz.json",
            "classification.json": "fda_classification_llz.json",
        }[url.rsplit("/", 1)[1]]
        j = json.loads(_fx(name))
        j.setdefault("meta", {}).setdefault("results", {})["total"] = len(j["results"])
        return j


def test_classification_lookup():
    rec = fda.classify(FakeClient(), "LLZ")
    assert rec["device_name"] == "System, Image Processing, Radiological"
    assert rec["regulation_number"] == "892.2050"


def test_maude_to_incident():
    rs = json.loads(_fx("fda_event_llz.json"))["results"]
    assert fda.maude_to_incident(rs[0], "LLZ").text == ""  # some reports carry no narrative
    r = rs[1]
    it = fda.maude_to_incident(r, "LLZ")
    assert it.source == "FDA_MAUDE"
    assert it.id == r["report_number"]
    assert it.date == f"{r['date_received'][:4]}-{r['date_received'][4:6]}-{r['date_received'][6:]}"
    assert it.product_code == "LLZ"
    assert "mdrfoi__id=" + r["mdr_report_key"] in it.url
    assert it.text and isinstance(it.extra["product_problems"], list)


def test_recall_to_incident():
    r = json.loads(_fx("fda_recall_llz.json"))["results"][0]
    it = fda.recall_to_incident(r)
    assert it.source == "FDA_RECALL"
    assert it.id == r["product_res_number"]
    assert it.date == r["event_date_initiated"]
    assert "REASON:" in it.text
    assert it.url.endswith(f"id={r['cfres_id']}")


def test_parse_rss():
    rows = bfarm.parse_rss(_fx("bfarm_rss.xml"))
    assert len(rows) == 20
    assert rows[0]["date"] == "2026-10-02"
    assert rows[0]["url"].endswith("45469-26_kundeninfo_de.html")


def test_parse_list_page():
    rows = bfarm.parse_list(_fx("bfarm_list_page1.html"))
    assert len(rows) == 50
    ct = next(r for r in rows if r["ref"] == "39225/26")
    assert ct["group"] == "Radiologische Technik - Computertomografen"
    assert ct["date"] == "2026-10-01"


def test_parse_detail_page():
    d = bfarm.parse_detail(_fx("bfarm_detail.html"))
    assert d == {"group": "Radiologische Technik - Computertomografen", "ref": "39225/26"}


def test_split_title():
    t = "Dringende Sicherheitsinformation zu AW Server von GE Medical Systems SCS"
    assert bfarm.split_title(t) == ("AW Server", "GE Medical Systems SCS")


def _inc(i: str, source: str = "FDA_MAUDE", **kw) -> Incident:
    base = dict(
        source=source,
        id=i,
        date="2026-09-01",
        manufacturer="M",
        product="P",
        product_code="LLZ",
        event_type="Malfunction",
        text="",
        url="https://example.org",
    )
    base.update(kw)
    return Incident(**base)


def test_dedupe():
    items = [_inc("1"), _inc("2"), _inc("1"), _inc("1", source="FDA_RECALL")]
    assert [i.uid for i in dedupe(items)] == ["FDA_MAUDE:1", "FDA_MAUDE:2", "FDA_RECALL:1"]


def test_state_reports_only_new(tmp_path):
    st = State(tmp_path / "s.json")
    first = [_inc("1"), _inc("2")]
    assert len(st.new_items(first)) == 2
    st.mark(first)
    st.save()
    st2 = State(tmp_path / "s.json")
    assert [i.id for i in st2.new_items([_inc("2"), _inc("3")])] == ["3"]
    assert st2.last_run is not None


def test_tagger_categories():
    r = Rules.load()
    txt = "Images displayed with wrong orientation; left-right flipped after DICOM import"
    tags = r.categorize(txt)
    assert {"image_display", "orientation_laterality", "interoperability"} <= set(tags)
    assert r.categorize("The application froze while loading a study") == ["performance_freeze"]
    assert "wrong_patient" in r.categorize("study was associated with the wrong patient")
    assert "measurement" in r.categorize("distance measurement off by 10 percent")
    assert r.is_relevant("Dringende Sicherheitsinformation zu PACS Viewer von X")
    assert not r.is_relevant("Dringende Sicherheitsinformation zu Infusionsbesteck von Y")
    assert "relevance" in r.explain("DICOM viewer freeze")


def test_tag_bfarm_group_relevance():
    a = _inc("1", source="BFARM_FSN", product_code="Radiologische Technik - CT", text="Foo von X")
    b = _inc("2", source="BFARM_FSN", product_code="Dentalprodukte - X", text="Foo von X")
    c = _inc("3", source="FDA_RECALL", text="anything")
    tag([a, b, c], bfarm_groups=("Radiologische Technik",))
    assert (a.relevant, b.relevant, c.relevant) == (True, False, True)


def test_digest_markdown_and_csv(tmp_path):
    items = tag([_inc("1", text="image not displayed"), _inc("2", source="BFARM_FSN")])
    md = render_markdown(items, "T", "P")
    assert "| FDA_MAUDE | 1 | 1 |" in md
    assert "| image_display | 1 | 0 | 0 |" in md
    write_csv(items, tmp_path / "d.csv")
    rows = list(csv.DictReader((tmp_path / "d.csv").open()))
    assert rows[0]["tags"] == "image_display"


def test_run_offline_end_to_end(tmp_path, monkeypatch):
    monkeypatch.setattr(cli, "CachedClient", FakeClient)
    args = ["--today", "2026-10-05", "run", "--state", str(tmp_path / "st.json")]
    assert cli.main([*args, "--out", str(tmp_path / "r1")]) == 0
    meta = json.loads((tmp_path / "r1/latest.json").read_text())
    n1 = sum(v["n"] for v in meta["new"].values())
    assert meta["fetched"]["BFARM_FSN"]["n"] == 20
    assert n1 == sum(v["n"] for v in meta["fetched"].values())
    assert (tmp_path / "r1/digest-2026-10-05.md").exists()
    # second run with the same data: nothing new
    assert cli.main([*args, "--out", str(tmp_path / "r2")]) == 0
    meta2 = json.loads((tmp_path / "r2/latest.json").read_text())
    assert meta2["new"] == {}
