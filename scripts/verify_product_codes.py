"""Verify the configured FDA product codes against the openFDA classification endpoint.

Also lists every product code under the radiology image-software regulations
(21 CFR 892.2010 to 892.2050) so the choice in vigil/config.yaml is auditable.
Writes results/product_codes.json.
"""

from __future__ import annotations

import json
from pathlib import Path

from vigil.cli import load_config
from vigil.fda import BASE, classify
from vigil.http import CachedClient

ROOT = Path(__file__).resolve().parents[1]
REGS = ["892.2010", "892.2020", "892.2030", "892.2040", "892.2050"]


def main() -> int:
    cfg = load_config()
    client = CachedClient(ROOT / "data/raw", ttl_s=7 * 86400)
    chosen = []
    for code, expected in cfg["fda"]["product_codes"].items():
        rec = classify(client, code)
        rec["config_name"] = expected
        rec["name_matches_config"] = rec.get("device_name", "").lower() == expected.lower()
        chosen.append(rec)
    q = "regulation_number:(" + " ".join(REGS) + ")"
    j = client.get_json(f"{BASE}/classification.json", {"search": q, "limit": 100})
    candidates = sorted(
        {
            (r["product_code"], r["regulation_number"], r["device_name"])
            for r in j.get("results", [])
        }
    )
    out = {
        "chosen": chosen,
        "all_verified": all(c["name_matches_config"] for c in chosen),
        "candidates_892_2010_to_2050": [
            {"product_code": c, "regulation_number": r, "device_name": n} for c, r, n in candidates
        ],
    }
    (ROOT / "results/product_codes.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    for c in chosen:
        print(c["product_code"], c["regulation_number"], c["device_name"], c["name_matches_config"])
    return 0 if out["all_verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
