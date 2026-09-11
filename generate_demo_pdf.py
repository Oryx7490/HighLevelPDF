from pathlib import Path
import json

from app import DEMO_PATH, build_pdf

root = Path(__file__).resolve().parent
estimate = json.loads(DEMO_PATH.read_text(encoding="utf-8"))["estimates"][0]
(root.parent / "cotizacion-demo-highlevel.pdf").write_bytes(build_pdf(estimate))
print(root.parent / "cotizacion-demo-highlevel.pdf")
