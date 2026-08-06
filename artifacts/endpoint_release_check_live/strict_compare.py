import io
import json
import time
import uuid
import zipfile
import hashlib
from pathlib import Path
from urllib import request

base='http://127.0.0.1:8001'
pdf=Path('file-sample_150kB.pdf')
out=Path('artifacts/endpoint_release_check_live')
out.mkdir(parents=True, exist_ok=True)

boundary=f'----Boundary{uuid.uuid4().hex}'
parts=[]
def add_field(name,val):
    parts.append((f'--{boundary}\r\n').encode())
    parts.append((f'Content-Disposition: form-data; name="{name}"\r\n\r\n').encode())
    parts.append(str(val).encode())
    parts.append(b'\r\n')
def add_file(name,path):
    parts.append((f'--{boundary}\r\n').encode())
    parts.append((f'Content-Disposition: form-data; name="{name}"; filename="{path.name}"\r\n').encode())
    parts.append(b'Content-Type: application/pdf\r\n\r\n')
    parts.append(path.read_bytes())
    parts.append(b'\r\n')
add_file('files',pdf)
add_field('workflow','convert')
add_field('pdf_mode','hybrid')
parts.append((f'--{boundary}--\r\n').encode())
body=b''.join(parts)

req=request.Request(f'{base}/api/convert', data=body, method='POST', headers={'Content-Type': f'multipart/form-data; boundary={boundary}'})
with request.urlopen(req, timeout=120) as r:
    status=r.getcode(); payload=json.loads(r.read().decode())
job=payload['job_id']
for _ in range(160):
    with request.urlopen(f'{base}/api/status/{job}', timeout=30) as r:
        s=json.loads(r.read().decode())
    if s.get('status') in {'completed','failed'}: break
    time.sleep(0.25)
if s.get('status')!='completed':
    print('ENDPOINT_TESTED','/api/convert'); print('HTTP_STATUS',status); print('BLOCKER',f'job status {s}'); raise SystemExit(1)

zip_path=out/'endpoint_package.zip'
with request.urlopen(f'{base}/api/download/{job}', timeout=180) as r:
    zip_path.write_bytes(r.read())

extract=out/'extracted'
if extract.exists():
    import shutil; shutil.rmtree(extract)
extract.mkdir(parents=True, exist_ok=True)
with zipfile.ZipFile(zip_path,'r') as zf:
    zf.extractall(extract)

endpoint_md=(extract/'docs'/'index.md')
endpoint_assets=(extract/'docs'/'assets')
manifest_path=next(extract.glob('*-manifest.json'))
quality_path=next(extract.glob('*-quality-report.json'))

backend_md=Path('artifacts/final_milestone/file-sample_150kB.md')
backend_assets=Path('artifacts/final_milestone/assets')
backend_manifest=Path('artifacts/final_milestone/file-sample_150kb-manifest.json')
backend_quality=Path('artifacts/final_milestone/file-sample_150kb-quality-report.json')

norm=lambda t:'\n'.join(line.rstrip() for line in t.replace('\r\n','\n').replace('\r','\n').strip().split('\n'))
compare_md = norm(endpoint_md.read_text(encoding='utf-8'))==norm(backend_md.read_text(encoding='utf-8'))

eas=sorted(p.name for p in endpoint_assets.glob('*') if p.is_file())
bas=sorted(p.name for p in backend_assets.glob('*') if p.is_file())
compare_assets = eas==bas
if compare_assets:
    for n in eas:
        h1=hashlib.sha256((endpoint_assets/n).read_bytes()).hexdigest(); h2=hashlib.sha256((backend_assets/n).read_bytes()).hexdigest()
        if h1!=h2: compare_assets=False; break

def normalize_manifest(p):
    return {
        'technical_status': p.get('technical_status'),
        'fidelity_status': p.get('fidelity_status'),
        'validation': p.get('validation'),
        'effective_configuration': p.get('effective_configuration'),
        'pages': [
            {'page_number': pg.get('page_number'),'selected_candidate': pg.get('selected_candidate'),'technical_status': pg.get('technical_status'),'fidelity_status': pg.get('fidelity_status')}
            for pg in p.get('document_result',{}).get('pages',[])
        ],
    }

def normalize_quality(p):
    return {
        'technical_status': p.get('technical_status'),
        'fidelity_status': p.get('fidelity_status'),
        'effective_configuration': p.get('effective_configuration'),
        'pages': [
            {'page_number': pg.get('page_number'),'selected_candidate': pg.get('selected_candidate'),'technical_status': pg.get('technical_status'),'fidelity_status': pg.get('fidelity_status')}
            for pg in p.get('page_summaries',[])
        ],
    }

em=json.loads(manifest_path.read_text(encoding='utf-8')); bm=json.loads(backend_manifest.read_text(encoding='utf-8'))
compare_manifest = normalize_manifest(em)==normalize_manifest(bm)
eq=json.loads(quality_path.read_text(encoding='utf-8')); bq=json.loads(backend_quality.read_text(encoding='utf-8'))
compare_quality = normalize_quality(eq)==normalize_quality(bq)

print('ENDPOINT_TESTED','/api/convert')
print('HTTP_STATUS',status)
print('OUTPUT_MD',endpoint_md.as_posix())
print('OUTPUT_ASSETS',endpoint_assets.as_posix())
print('OUTPUT_MANIFEST',manifest_path.as_posix())
print('OUTPUT_QUALITY',quality_path.as_posix())
print('COMPARE_MD',compare_md)
print('COMPARE_ASSETS',compare_assets)
print('COMPARE_MANIFEST_CORE',compare_manifest)
print('COMPARE_QUALITY_CORE',compare_quality)
