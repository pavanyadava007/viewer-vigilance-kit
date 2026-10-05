"""BfArM field safety notices (Kundeninformationen) via RSS, detail pages and list pages."""

from __future__ import annotations

import html
import re
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime

from .http import CachedClient
from .schema import Incident

_TAG = re.compile(r"<[^>]+>")
_WS = re.compile(r"\s+")
_ROW = re.compile(r"<tr>\s*<td>\s*(\d{2}\.\d{2}\.\d{4})\s*</td>\s*<td>(.*?)</td>\s*</tr>", re.S)
_LINK = re.compile(r'<a href="([^"]+kundeninfo[^"]*)"[^>]*>(.*?)</a>', re.S)
_GROUP = re.compile(r"<strong>\s*Produktgruppe\s*</strong>(.*?)(?:<br\s*/?>|</p>|</dd>)", re.S)
_REF = re.compile(r"<strong>\s*Referenznummer\s*</strong>(.*?)(?:<br\s*/?>|</p>|</dd>)", re.S)
_DETAIL_GROUP = re.compile(r"Produktgruppe\s*</[^>]+>\s*(?:<[^>]+>\s*)*([^<]+)", re.S)
_DETAIL_REF = re.compile(r"Referenznummer\s*</[^>]+>\s*(?:<[^>]+>\s*)*([^<]+)", re.S)
_DATE = re.compile(r"\b(\d{2})\.(\d{2})\.(\d{4})\b")


def _clean(s: str) -> str:
    return _WS.sub(" ", html.unescape(_TAG.sub(" ", s))).strip()


def _de_date(s: str) -> str:
    m = _DATE.search(s)
    return f"{m.group(3)}-{m.group(2)}-{m.group(1)}" if m else ""


def split_title(title: str) -> tuple[str, str]:
    """'Dringende Sicherheitsinformation zu X von Y' -> (product X, manufacturer Y)."""
    t = re.sub(r"^\s*(Dringende\s+)?Sicherheitsinformation\s+(zu|zum|zur)\s+", "", title)
    if " von " in t:
        prod, man = t.rsplit(" von ", 1)
        return prod.strip(), man.strip()
    return t.strip(), ""


def _strip_nn(url: str) -> str:
    return url.split("?")[0]


def notice_id(url: str, ref: str) -> str:
    if ref:
        return ref.strip()
    m = re.search(r"/(\d+-\d+)_kundeninfo", url)
    return m.group(1).replace("-", "/") if m else url


def parse_rss(xml_text: str) -> list[dict]:
    root = ET.fromstring(xml_text)
    out = []
    for item in root.iter("item"):
        title = (item.findtext("title") or "").strip()
        link = _strip_nn((item.findtext("link") or "").strip())
        pub = item.findtext("pubDate") or ""
        try:
            d = parsedate_to_datetime(pub).date().isoformat()
        except (TypeError, ValueError):
            d = ""
        out.append({"title": title, "url": link, "date": d})
    return out


def parse_detail(html_text: str) -> dict:
    g = _DETAIL_GROUP.search(html_text)
    r = _DETAIL_REF.search(html_text)
    return {
        "group": _clean(g.group(1)) if g else "",
        "ref": _clean(r.group(1)) if r else "",
    }


def parse_list(html_text: str) -> list[dict]:
    out = []
    for m in _ROW.finditer(html_text):
        d, cell = m.group(1), m.group(2)
        lk = _LINK.search(cell)
        if not lk:
            continue
        g = _GROUP.search(cell)
        r = _REF.search(cell)
        out.append(
            {
                "date": _de_date(d),
                "url": _strip_nn(html.unescape(lk.group(1))),
                "title": _clean(lk.group(2)),
                "group": _clean(g.group(1)) if g else "",
                "ref": _clean(r.group(1)) if r else "",
            }
        )
    return out


def to_incident(row: dict) -> Incident:
    product, manufacturer = split_title(row["title"])
    return Incident(
        source="BFARM_FSN",
        id=notice_id(row["url"], row.get("ref", "")),
        date=row.get("date", ""),
        manufacturer=manufacturer,
        product=product,
        product_code=row.get("group", ""),
        event_type="Field safety notice",
        text=row["title"],
        url=row["url"],
        extra={"produktgruppe": row.get("group", "")},
    )


def fetch_rss(client: CachedClient, rss_url: str, details: bool = True) -> list[Incident]:
    rows = parse_rss(client.get_text(rss_url, ttl_s=3600))
    out = []
    for row in rows:
        if details:
            # Detail pages do not change once published: cache for a long time.
            info = parse_detail(client.get_text(row["url"], ttl_s=365 * 86400))
            row.update(info)
        out.append(to_incident(row))
    return out


def fetch_list(client: CachedClient, list_url: str, pages: int) -> list[Incident]:
    out: list[Incident] = []
    for p in range(1, pages + 1):
        params = None if p == 1 else {"gtp": f"964800_list%3D{p}"}
        rows = parse_list(client.get_text(list_url, params))
        if not rows:
            break
        out.extend(to_incident(r) for r in rows)
    return out
