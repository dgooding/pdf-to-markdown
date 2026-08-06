# AGENTS.md

## Execution Policy for This Repository
- Work in bounded milestones with checkpoint updates after each milestone.
- Preserve original converter UI and route (`/editor`) as primary product surface.
- Do not auto-launch MkDocs during normal conversion runtime.
- Maintain direct/endpoint parity via authoritative conversion service.
- Keep technical validation separate from content-fidelity classification.

## Required Verification Cadence
After milestone changes:
1. Focused tests
2. Full test suite (`unittest discover -s tests -v`)
3. Endpoint parity check (`strict_compare_run.py`)
4. Checkpoint updates:
   - `PROJECT_STATE.md`
   - `ARCHITECTURE.md`
   - `DECISIONS.md`
   - `TESTING.md`
   - `NEXT_MILESTONE.md`
   - `artifacts/diagnostics/course_correction_inventory.md`

## Artifact Logging
- Save milestone logs under `artifacts/logs/`.
- Keep benchmark and parity artifacts in dedicated timestamped folders.
