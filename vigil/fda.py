"""openFDA fetchers: device classification, MAUDE adverse events, recalls."""

from __future__ import annotations

from datetime import date, timedelta

from .http import CachedClient
from .schema import Incident

BASE = "https://api.fda.gov/device"
PAGE = 100
RES_URL = "https://www.accessdata.fda.gov/scripts/cdrh/cfdocs/cfRES/res.cfm"


def _ymd(d: date) -> str:
    return d.strftime("%Y%m%d")


def _iso(s: str | None) -> str:
    if not s:
        return ""
    s = s.replace("-", "")
    return f"{s[:4]}-{s[4:6]}-{s[6:8]}" if len(s) >= 8 else s


def classify(client: CachedClient, code: str) -> dict:
    """Return the openFDA classification record for a product code (or {})."""
    j = client.get_json(f"{BASE}/classification.json", {"search": f"product_code:{code}"})
    res = j.get("results") or []
    if not res:
        return {}
    r = res[0]
    keys = ("product_code", "device_name", "device_class", "regulation_number")
    out = {k: r.get(k, "") for k in keys}
    out["medical_specialty"] = r.get("medical_specialty_description", "")
    return out


def _paged(client: CachedClient, endpoint: str, search: str, cap: int) -> tuple[list[dict], int]:
    out: list[dict] = []
    total = 0
    skip = 0
    while skip < cap:
        j = client.get_json(
            f"{BASE}/{endpoint}.json",
            {"search": search, "limit": PAGE, "skip": skip, "sort": _sort_field(endpoint)},
        )
        if "error" in j:  # "No matches found!"
            break
        total = j.get("meta", {}).get("results", {}).get("total", 0)
        batch = j.get("results", [])
        out.extend(batch)
        skip += PAGE
        if not batch or skip >= total:
            break
    return out, total


def _sort_field(endpoint: str) -> str:
    return "date_received:desc" if endpoint == "event" else "event_date_initiated:desc"


def maude_to_incident(r: dict, code: str) -> Incident:
    dev = (r.get("device") or [{}])[0]
    texts = [t.get("text", "") for t in r.get("mdr_text") or []]
    key = r.get("mdr_report_key", "")
    return Incident(
        source="FDA_MAUDE",
        id=r.get("report_number") or key,
        date=_iso(r.get("date_received")),
        manufacturer=dev.get("manufacturer_d_name") or r.get("manufacturer_name") or "",
        product=dev.get("brand_name") or dev.get("generic_name") or "",
        product_code=dev.get("device_report_product_code") or code,
        event_type=r.get("event_type") or "",
        text=" ".join(texts)[:4000],
        url=(
            "https://www.accessdata.fda.gov/scripts/cdrh/cfdocs/cfmaude/detail.cfm"
            f"?mdrfoi__id={key}&pc={code}"
        ),
        extra={"product_problems": r.get("product_problems") or []},
    )


def recall_to_incident(r: dict) -> Incident:
    text = f"{r.get('product_description', '')} REASON: {r.get('reason_for_recall', '')}"
    return Incident(
        source="FDA_RECALL",
        id=r.get("product_res_number") or r.get("cfres_id", ""),
        date=_iso(r.get("event_date_initiated")),
        manufacturer=r.get("recalling_firm", ""),
        product=(r.get("product_description") or "")[:160],
        product_code=r.get("product_code", ""),
        event_type=f"Recall ({r.get('recall_status', '')})",
        text=text[:4000],
        url=f"{RES_URL}?id={r.get('cfres_id', '')}",
        extra={
            "res_event_number": r.get("res_event_number", ""),
            "root_cause": r.get("root_cause_description", ""),
        },
    )


def fetch_maude(
    client: CachedClient, codes: list[str], days: int, cap: int, today: date | None = None
) -> tuple[list[Incident], dict]:
    today = today or date.today()
    start = today - timedelta(days=days)
    items: list[Incident] = []
    meta = {"date_field": "date_received", "from": start.isoformat(), "to": today.isoformat()}
    for code in codes:
        rng = f"[{_ymd(start)} TO {_ymd(today)}]"
        q = f"device.device_report_product_code:{code} AND date_received:{rng}"
        rows, total = _paged(client, "event", q, cap)
        meta[code] = {"api_total": total, "fetched": len(rows)}
        items.extend(maude_to_incident(r, code) for r in rows)
    return items, meta


def fetch_recalls(
    client: CachedClient, codes: list[str], days: int, cap: int, today: date | None = None
) -> tuple[list[Incident], dict]:
    today = today or date.today()
    start = today - timedelta(days=days)
    items: list[Incident] = []
    meta = {
        "date_field": "event_date_initiated",
        "from": start.isoformat(),
        "to": today.isoformat(),
    }
    for code in codes:
        q = f"product_code:{code} AND event_date_initiated:[{_ymd(start)} TO {_ymd(today)}]"
        rows, total = _paged(client, "recall", q, cap)
        meta[code] = {"api_total": total, "fetched": len(rows)}
        items.extend(recall_to_incident(r) for r in rows)
    return items, meta
