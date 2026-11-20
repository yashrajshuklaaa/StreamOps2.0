# Changelog

## Unreleased

### P0 - Evidence and citation audit

- Replaced unsupported paper results and production claims with an explicit prototype and evaluation-status report.
- Corrected the SpecBox reference to arXiv:2607.23933; retained only cited works whose arXiv records were verified.
- Marked the legacy TTFE benchmark as simulated in its output and documentation.
- Updated the project overview, architecture, FinOps, and core-concepts documentation to distinguish implemented behavior from planned work.
- Rebuilt the MkDocs site; documented API routes and marked the Helm/Terraform examples as legacy and unvalidated for the Go/Rust services.
- No measured TTFE, cold-start masking, cloud-cost savings, or proxy-overhead results are currently reported.

### Validation

- Go control-plane tests: passed.
- Rust intent-engine tests: 4 passed.
- Python regression tests: 18 passed with explicit pytest plugins. The environment's default pytest plugin autoload fails because `platformdirs.pytest_plugin` is unavailable.
- Strict MkDocs build: passed.

### Open risks

- There is no raw benchmark dataset or reproducible end-to-end agent/tool execution evaluation.
- Intent scores are not calibrated probabilities; configured cost values are not live prices.
- The Rust request currently runs synchronously on the Go streaming path and may delay token forwarding.
- The claim endpoint adopts a pod but does not execute a tool payload.
