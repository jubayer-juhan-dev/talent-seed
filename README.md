# Talent Seed

Crypto developer talent data built from Electric Capital's Open Dev Data (CC BY 4.0), and a recruiter-facing
web viewer over it.

- **Data pipeline:** `scripts/m1_…` to `m5_…`, rules in `config/talent_seed_thresholds.toml`,
  tables in [`docs/talent_seed_tables.md`](docs/talent_seed_tables.md).
- **Viewer:** FastAPI (`viewer_api/`) + React (`web/`). How to run, change, test and deploy it:
  [`docs/viewer_run_and_deploy.md`](docs/viewer_run_and_deploy.md).
- **Plan the viewer was built to:** [`docs/modernization_plan.md`](docs/modernization_plan.md).

Data files (`data/`, `raw_open_dev_data/`, `exports/`) are not in git: they are large and contain personal data.
