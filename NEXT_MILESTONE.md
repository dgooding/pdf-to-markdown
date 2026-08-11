# Next Milestone

- Verify the global Admin control is absent after GitHub Pages and Render redeploy from the 2026-08-11 source update.
- Enable GitHub Pages with **GitHub Actions** as the source and verify `https://dgooding.github.io/pdf-to-markdown/`.
- Run a harmless public `incoming/` upload → conversion → publish → delete smoke cycle and retain Actions evidence.
- Disable/delete the Render service only after GitHub Pages remains live and the smoke cycle passes.
- Complete actual human review of the 17 prepared synthetic fixtures and run the approved 5–10 document real-world pilot.
- Optional UX follow-up: decide whether to expose a second visible assets/package control in `/editor` in addition to the default Markdown download.
- Optional content-governance follow-up: define a preferred published-doc taxonomy (for example `troubleshooting/`, `faqs/`, `user-manuals/`) and approval rules for site publishing.
- Validate search relevance as the approved production document library grows.
- Keep interactive site code out of indexed Markdown and never add browser-stored GitHub credentials.
- Keep the minimal runtime route surface stable; add new site features only for an approved operational need.
- Run `cleanup_for_github.ps1` before release commits to keep generated evidence out of the repository.
- Preserve the flat sidebar unless an approved operational requirement needs another top-level page.
