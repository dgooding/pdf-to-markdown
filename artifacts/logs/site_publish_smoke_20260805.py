import json
import tempfile
import time
import uuid
from pathlib import Path
from urllib import parse, request

base = "http://127.0.0.1:8001"
tmp = Path(tempfile.mkdtemp(prefix="site-smoke-"))
src = tmp / "sample.md"
src.write_text("# Service Desk Publish Smoke\n\nThis document was published from the converter.\n", encoding="utf-8")

boundary = "----Boundary" + uuid.uuid4().hex
parts: list[bytes] = []
parts.append((f"--{boundary}\r\n").encode())
parts.append((f"Content-Disposition: form-data; name=\"files\"; filename=\"{src.name}\"\r\n").encode())
parts.append(b"Content-Type: text/markdown\r\n\r\n")
parts.append(src.read_bytes())
parts.append(b"\r\n")
parts.append((f"--{boundary}\r\n").encode())
parts.append(b"Content-Disposition: form-data; name=\"workflow\"\r\n\r\nconvert\r\n")
parts.append((f"--{boundary}\r\n").encode())
parts.append(b"Content-Disposition: form-data; name=\"pdf_mode\"\r\n\r\nhybrid\r\n")
parts.append((f"--{boundary}--\r\n").encode())
body = b"".join(parts)

req = request.Request(
    base + "/api/convert",
    data=body,
    method="POST",
    headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
)
payload = json.loads(request.urlopen(req, timeout=60).read().decode())
job = payload["job_id"]
status = {}
for _ in range(120):
    status = json.loads(request.urlopen(base + f"/api/status/{job}", timeout=30).read().decode())
    if status.get("status") in {"completed", "failed"}:
        break
    time.sleep(0.1)
assert status.get("status") == "completed", status

publish_body = parse.urlencode({"site_path": "user-manuals/service-desk-publish-smoke"}).encode()
publish_req = request.Request(
    base + f"/api/publish/{job}",
    data=publish_body,
    method="POST",
    headers={"Content-Type": "application/x-www-form-urlencoded"},
)
publish = json.loads(request.urlopen(publish_req, timeout=60).read().decode())
assert publish["status"] == "published", publish

page = request.urlopen(base + publish["published_url"], timeout=60).read().decode("utf-8")
home = request.urlopen(base + "/docs/", timeout=60).read().decode("utf-8")
contact = request.urlopen(base + "/docs/contact/", timeout=60).read().decode("utf-8")

print("PUBLISHED_URL", publish["published_url"])
print("PAGE_HAS_TITLE", "Service Desk Publish Smoke" in page)
print("HOME_OK", "ITSD Service Desk" in home)
print("CONTACT_FORM_OK", '<form action="/api/contact"' in contact)
