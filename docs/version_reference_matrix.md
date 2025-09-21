# Version Reference Matrix

| Artifact | Location | Version Expression | Purpose |
| --- | --- | --- | --- |
| Python package metadata | `pyproject.toml` (`[project].version`, `[tool.poetry].version`) | `0.1.4` | Controls Python distribution and Poetry lockstep. |
| Rust engine crate | `core/rust_engine/Cargo.toml` (`[package].version`) | `0.1.4` | Aligns PyO3 extension crate version with Python bindings. |
| Plugin distribution | `plugins/pyproject.toml` (`[project].version`) | `0.1.4` | Ensures plugin registry publishes matching artifacts. |
| Sample plugin | `plugins/sample_plugin/pyproject.toml` (`[project].version`) | `0.1.4` | Demonstrates plugin template version pin. |
| CLI scaffolding | `forzium/cli.py` | `forzium==0.1.4` / `forzium-engine==0.1.4` and generated `pyproject` snippet | Seeds new projects with the release version. |
| Deployment templates | `infrastructure/deployment/templates/*.yml` | Docker/Helm image tags `0.1.4` | Keeps runtime images aligned with release tag. |
| Observability dashboards | `infrastructure/monitoring/dashboards/forzium_observability.json` | `"forzium_release": "0.1.4"` | Labels metrics exports with release metadata. |
| Scenario catalog | `scenarios/release_v0_1_4.yaml` / `.json` | `v0.1.4` | Couples load templates to release. |
| Public documentation | `README.md`, `docs/migration.md`, `docs/scenario_templates.md`, `Test_Strategy.md` | `v0.1.4` | Communicates current release to developers and QA. |

> This matrix is consumed by automated cross-validation to guarantee every externally visible artifact references the canonical `forzium.__version__` value.