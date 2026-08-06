# RUNBOOK — prototype-v2-rc1

## Production on GitHub

- Public site: `https://dgooding.github.io/pdf-to-markdown/`
- Upload intake: `https://github.com/dgooding/pdf-to-markdown/upload/main/incoming`
- Conversion status: `https://github.com/dgooding/pdf-to-markdown/actions/workflows/convert-publish.yml`
- Pages status: `https://github.com/dgooding/pdf-to-markdown/actions/workflows/pages.yml`
- Delete workflow: `https://github.com/dgooding/pdf-to-markdown/actions/workflows/delete-published.yml`
- Production authorization is repository write permission; no Pages passcode or browser token is used.

### Publish through GitHub

1. Upload supported source files to `incoming/` and commit to `main`.
2. Monitor **Convert and publish incoming documents** in Actions.
3. Confirm the Actions bot commits generated Markdown/assets and removes processed inbox files from the latest revision.
4. Confirm Pages deployment and the new entry under **Documents**.

### Delete through GitHub

1. Click Delete beside a document or run **Delete published document** manually.
2. The issue path verifies the requester has `write`, `maintain`, or `admin` permission.
3. Confirm the deletion commit and Pages deployment.

Source uploads are public and remain recoverable from Git history.

## Defaults and behavior
- FastAPI is local/offline tooling, not the production host.
- Default application startup port (repository launch policy): `8000` via `LAUNCH.bat`.
- Current validated runtime instance used in release checks: `http://127.0.0.1:8001/editor`.
- Development override behavior: `uvicorn --port <PORT>` may be used for alternate local ports.
- MkDocs is developer-only and must not auto-start during normal converter startup.
- Port `8012` must not start automatically in normal application startup.

## Environment setup
- Windows + Python 3.9.13.
- Workspace root:
  - `C:\Users\A083101\OneDrive - PROGRESSIVE CASUALTY INSURANCE COMPANY\Desktop\PDF to Markdown App Needs Py3.9`

## Dependency installation
- Standard install (online):
  - `C:/Python39/python.exe -m pip install -r requirements.txt`
- Wheelhouse/offline-style install (if used in this environment):
  - `C:/Python39/python.exe -m pip install --no-index --find-links wheelhouse -r requirements.txt`

## Starting the converter
- Repository launcher:
  - `LAUNCH.bat`
- Direct server start:
  - `C:/Python39/python.exe -m uvicorn app:app --host 127.0.0.1 --port 8000`

## Opening /editor
- URL:
  - `http://127.0.0.1:8000/editor`

## Running direct conversion
- Single file:
  - `C:/Python39/python.exe convert_to_md.py "<input-file>" --output-dir "<output-dir>" --overwrite --pdf-mode hybrid`
- Recursive directory conversion:
  - `C:/Python39/python.exe convert_to_md.py "<input-dir>" --recursive --output-dir "<output-dir>" --overwrite --pdf-mode hybrid`

## Calling /api/convert
- Integration reference:
  - `C:/Python39/python.exe -m unittest tests.test_endpoint_integration -v`

## Downloading a result
- Flow:
  1. `POST /api/convert`
  2. Poll `GET /api/status/{job_id}` until `completed`
  3. Download `GET /api/download/{job_id}`

## Running full tests
- `C:/Python39/python.exe -m unittest discover -s tests -v`

## Generating synthetic fixtures
- `C:/Python39/python.exe generate_test_corpus.py --output-dir tests/fixtures/generated --seed 20260730 --groups docx,pdf --cleanup --validate`

## Running the benchmark
- `C:/Python39/python.exe benchmark_generated_corpus.py --corpus-manifest tests/fixtures/generated/generated-corpus.json`

## Running batch conversion
- Dry run:
  - `C:/Python39/python.exe batch_convert.py "<input-root>" --output-root "<output-root>" --recursive --dry-run`
- Execute with overwrite:
  - `C:/Python39/python.exe batch_convert.py "<input-root>" --output-root "<output-root>" --recursive --force`
- Resume:
  - `C:/Python39/python.exe batch_convert.py "<input-root>" --output-root "<output-root>" --recursive --resume`

## Running staged MkDocs migration
- `C:/Python39/python.exe mkdocs_stage_migration.py "<source-markdown>" --source-assets-dir "<source-assets-dir>" --docs-root "<mkdocs-docs-root>" --conflict-strategy versioned_copy`

## Checking OCR availability
- `C:/Python39/python.exe -c "from convert_to_md import detect_tesseract_provider; import json; print(json.dumps(detect_tesseract_provider(None), indent=2))"`

## Inspecting manifests
- `C:/Python39/python.exe -c "import json,glob; p=sorted(glob.glob('**/*-manifest.json', recursive=True)); print(p[-1]); print(json.dumps(json.load(open(p[-1],encoding='utf-8')), indent=2)[:4000])"`

## Inspecting quality reports
- `C:/Python39/python.exe -c "import json,glob; p=sorted(glob.glob('**/*-quality-report.json', recursive=True)); print(p[-1]); print(json.dumps(json.load(open(p[-1],encoding='utf-8')), indent=2)[:4000])"`

## Finding logs
- Primary log directory:
  - `artifacts/logs/`
- Release evidence logs:
  - `artifacts/releases/prototype-v2-rc1/`

## Troubleshooting failed jobs
1. Check API job status payload (`/api/status/{job_id}`) for `error` and `suggestion`.
2. Verify file extension is supported (`.pdf`, `.docx`, `.md`, `.txt`).
3. Check upload size/count against API limits.
4. Check manifest/quality-report presence in output package.
5. Re-run endpoint integration tests and review latest log in `artifacts/logs/`.

## Rolling back to stable checkpoint
1. Use archived release evidence and checkpoint markdowns in `artifacts/releases/prototype-v2-rc1/`.
2. Restore target code/content from your source control or archived snapshot.
3. Re-run:
   - full tests
   - benchmark
   - endpoint runtime checks (`/editor`, `/api/convert`, package contents)
4. Confirm no automatic MkDocs startup and no listener on port `8012`.
