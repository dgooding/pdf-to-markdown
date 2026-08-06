# Convert and Publish

Production conversion runs entirely on GitHub Actions. Repository administrators upload a source document to `incoming/`; GitHub converts it with the full Python pipeline, commits the generated Markdown and assets, and deploys this site through GitHub Pages.

<div class="github-admin-actions">
  <a class="github-admin-primary" href="https://github.com/dgooding/pdf-to-markdown/upload/main/incoming">Upload a document</a>
  <a href="https://github.com/dgooding/pdf-to-markdown/actions/workflows/convert-publish.yml">Conversion status</a>
  <a href="https://github.com/dgooding/pdf-to-markdown/actions/workflows/delete-published.yml">Delete workflow</a>
</div>

## Submit a document

1. Sign in to GitHub with an account that has write access to the repository.
2. Select **Upload a document** above.
3. Upload one or more supported files into `incoming/` and commit directly to `main`.
4. Open **Conversion status** to follow the queued Actions run.
5. When the run completes, the generated page appears under **Documents**.

Supported source formats are PDF, DOCX, Markdown, and text. PDF modes can also be selected by manually running the conversion workflow.

!!! warning
    This repository is public. Every source file uploaded to `incoming/` is public and remains recoverable from Git history even after Actions removes it from the latest revision.

## Delete a document

Use the **Delete** button beside a published document. It opens a prefilled GitHub request. The deletion workflow checks that the requester has repository write permission before changing any content.

Repository administrators can alternatively run the **Delete workflow** manually and enter the normalized document path.

## How authorization works

GitHub identity and repository permissions are the authorization boundary. This Pages site stores no passcode, personal access token, OAuth token, or browser credential.

## Local conversion

For private or immediate local conversion, clone the repository and run `LAUNCH.bat`. The FastAPI editor remains available locally at `http://127.0.0.1:8000/editor`; it is not the production GitHub Pages runtime.
