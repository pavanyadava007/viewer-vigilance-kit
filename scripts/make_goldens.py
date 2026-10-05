"""(Re)generate golden images and overlay specs. Run only after a reviewed, intended change."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tests.scenarios import GOLDEN, scenarios  # noqa: E402
from viewer.render import draw, image_layer, overlay_spec  # noqa: E402


def main() -> int:
    if os.environ.get("VIEWER_DEFECT"):
        print("refusing to write goldens with VIEWER_DEFECT set")
        return 1
    GOLDEN.mkdir(parents=True, exist_ok=True)
    docs = ROOT / "docs/img"
    docs.mkdir(parents=True, exist_ok=True)
    for name, (s, view) in scenarios().items():
        layer = image_layer(s, view)
        spec = overlay_spec(s, view)
        Image.fromarray(layer, mode="L").save(GOLDEN / f"{name}.png")
        (GOLDEN / f"{name}.overlay.json").write_text(json.dumps(spec, indent=1) + "\n")
        img = draw(layer, spec)
        scale = max(1, 256 // max(img.size))
        img.resize((img.width * scale, img.height * scale), Image.NEAREST).save(
            docs / f"{name}.png"
        )
        print("wrote", name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
