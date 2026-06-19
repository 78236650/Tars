# Archived experimental modules (v5.3.0 two-layer architecture)

The following modules are **frozen** by default in `config/modules.yaml`:

- `vessel_plan` — ship berth scheduling experiment
- `wind_stowage` — stowage calculation tool
- `presales` — presales workflow

Source remains under `tars/vessel_plan/`, `tars/api/presales.py`, and
`tools/builtin/wind_stowage.py` for reference. Re-enable via modules.yaml if needed.

Do not add new features here; port-vertical workflows belong in Layer2 skills or future orchestration extensions.
