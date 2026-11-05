# Asterion Control 0.3.0 — source prototype

Continuation of the fully included Asterion Remote 0.2.0 source, renamed and extended to Asterion Control. The existing README.md explains the current baseline, which still relies on ADB for Android control and snapshot capture.

New API operations (all require the existing Bearer token):

- `GET /api/v1/device-health` — measured host health with explicit sensor availability
- `GET /api/v1/internal/scripts` — list installed scripts under `ASTERION_CONTROL_SCRIPTS` (default `%USERPROFILE%\\.asterion-control\\scripts` on Windows)
- `POST /api/v1/internal/scripts/run` with `{"script_id":"build_app","arguments":["AsterionArt"],"cwd":"."}`
- `POST /api/v1/internal/scripts/batch` with `{"mode":"parallel","jobs":[{"script_id":"test_app"},{"script_id":"collect_logs"}]}`
- `GET /api/v1/commands/{jobid}` — output/status of each job, also reused by script-run responses

`ASTERION_ALLOW_SHELL=1` must be explicitly enabled to use scripts. `ASTERION_CONTROL_SCRIPTS` points to a controlled directory of previously installed scripts. Script filenames must match exact IDs and supported extensions (.py/.ps1/.cmd/.bat/.sh). No code learning or embedded AI exists in Control. The end-user phone interface hides the terminal navigation; APIs remain for authorized ChatGPT operation.

Run tests from the package root: `python -m pytest -q tests/test_remote.py tests/test_control.py`.

See `PROGRESS.md` for verification and limitations. The final requirements remain those frozen in `7STAR_FROZEN_MASTER.md` in GitHub; a standalone Android agent is not implemented yet.
