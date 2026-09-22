from pathlib import Path
from urllib.request import Request, urlopen
import ssl

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data" / "raw"

URLS = {
    "fy1c_gp.json": "https://celestrak.org/NORAD/elements/gp.php?GROUP=FENGYUN-1C-DEBRIS&FORMAT=JSON",
    "fy1c_satcat.json": "https://celestrak.org/satcat/records.php?NAME=FENGYUN%201C%20DEB&FORMAT=JSON&ONORBIT=1&MAX=5000",
}

DATA_DIR.mkdir(parents=True, exist_ok=True)
for name, url in URLS.items():
    request = Request(url, headers={"User-Agent": "Codex orbital-analysis/1.0"})
    with urlopen(request, timeout=120, context=ssl.create_default_context()) as response:
        content = response.read()
        (DATA_DIR / name).write_bytes(content)
        print(name, len(content), response.headers.get("content-type"))
