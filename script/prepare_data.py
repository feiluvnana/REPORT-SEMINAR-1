"""Extract <req> elements from selected PURE XML documents into normalized JSON."""
import json, re, sys
import html
from pathlib import Path

# Windows consoles default to a legacy code page; force UTF-8 so non-ASCII text prints safely.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

from paths import RAW_DIR as RAW, doc_path  # noqa: E402
DOCS = {"keepass": "2008 - keepass.xml", "peering": "2008 - peering.xml", "gammaj": "0000 - gamma j.xml"}
TITLE_OVERRIDE = {"gammaj": "Web Store (Gamma J)"}  # first <title> in this file is nested/empty
PREFIX = {"keepass": "KP", "peering": "PE", "gammaj": "GJ"}

def clean(s):
    return re.sub(r"\s+", " ", s).strip()

for key, fname in DOCS.items():
    txt = (RAW / fname).read_text(encoding="utf-8-sig")
    # regex parsing (pyexpat unavailable on this machine)
    m = re.search(r"<title>(.*?)</title>", txt, re.S)
    title = clean(re.sub(r"<[^>]+>", " ", m.group(1))) if m else ""
    title = TITLE_OVERRIDE.get(key) or title or key
    reqs = []
    for i, body in enumerate(re.findall(r"<req\b[^>]*>(.*?)</req>", txt, re.S), 1):
        t = clean(html.unescape(re.sub(r"<[^>]+>", " ", body)))
        if t:
            reqs.append({"req_id": f"{PREFIX[key]}-{i:03d}", "text": t})
    out = {"doc_id": key, "title": title, "source": f"PURE dataset (Ferrari et al., 2017): {fname}", "requirements": reqs}
    doc_path(key).write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n")
    print(key, title, len(reqs))
