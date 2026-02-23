# Common Requirements for AI/ML Projects

## 1. Agent Interaction

### 1.1 Workflow and Planning

- [ ] **REQ-AGT-001**: Use the README.md as the anchor for all project documentation and link to other documents as necessary. Create the README.md based on `<PROJECT_ROOT>/docs/templates/README_template.md` and `docs/*_requirements.md`.
- [ ] **REQ-AGT-002**: Always create a detailed implementation plan with steps and sub-steps first and get the user's review and approval before implementation.
- [ ] **REQ-AGT-003**: As implementation progresses, keep updating the plan with status so that if the agent is stopped for some reason it can resume from where it left off.

### 1.2 Troubleshooting Documentation

- [ ] **REQ-AGT-004**: Document all troubleshooting commands suggested and executed by the agent or user in a separate troubleshooting guide with the commands and when, why, and how they are used.

## 2. Logging

### 2.1 Log Content and Structure

- [ ] **REQ-LOG-001**: Use structured logs (JSON or key-value) so you can query by fields like `request_id`, `file`, `prompt_id`, or `model` in your log stack.
- [ ] **REQ-LOG-002**: Include consistent core fields in every entry: `timestamp`, `level`, `service`/`component` name, `environment`, and correlation/trace IDs.
- [ ] **REQ-LOG-003**: Add AI-specific fields where relevant: `prompt_id`, `model`, `temperature`, `max_tokens`, `tool_name`, `latency_ms`, and `input_tokens`/`output_tokens` if you have them.

Example structured log (JSON):

```json
{
  "ts": "2026-02-14T06:20:00Z",
  "level": "INFO",
  "service": "api-gateway",
  "env": "prod",
  "request_id": "abc123",
  "user_id": "u_42",
  "file": "user_handler.py",
  "event": "ai_suggestion_applied",
  "model": "gpt-5.1",
  "prompt_id": "p_991",
  "latency_ms": 820
}
```

### 2.2 Prompt and AI Interaction Logging

- [ ] **REQ-LOG-004**: Log prompts and completions in a dedicated store (e.g., a SQLite/JSONL pipeline or a prompt-logging library) for auditing, debugging, and improving prompt quality.
- [ ] **REQ-LOG-005**: Attach logs close to the client that calls the AI so every completion is recorded with parameters and metadata, not just the raw text.
- [ ] **REQ-LOG-006**: Redact or hash sensitive data (e.g., secrets, PII, internal URLs) before logs are persisted; ensure you never dump full environment variables or auth tokens.
- [ ] **REQ-LOG-007**: Separate "prompt analytics" logs (for refinement and UX) from operational logs (for debugging/alerting) so you can retain them under different policies.

### 2.3 Levels, Volume, and Performance

- [ ] **REQ-LOG-008**: Use standard log levels consistently (`DEBUG`, `INFO`, `WARN`, `ERROR`) and treat logging as part of your API contract with the AI agent.
- [ ] **REQ-LOG-009**: Keep AI call traces at `INFO`, but only enable full prompt/response bodies at `DEBUG` in non-prod environments or under explicit flags.
- [ ] **REQ-LOG-010**: Add level checks or guards so expensive debug logs are not computed on hot paths in production.
- [ ] **REQ-LOG-011**: Sample high-volume events (e.g., frequent background completions) instead of logging every call, and aggregate metrics (counts, error rates, p95 latency) separately.

### 2.4 Standardization

- [ ] **REQ-LOG-012**: Centralize logging through a shared logger utility instead of scattered `print`/`console.log`, so you can enforce structured formats and context enrichment everywhere.
- [ ] **REQ-LOG-013**: Use AI itself to help sweep and standardize logs (e.g., convert ad-hoc prints to structured logs, normalize field names, fix levels) and then gate new changes via PR checks.
- [ ] **REQ-LOG-014**: For libraries and internal packages, accept a logger interface instead of instantiating your own, allowing host apps to control formatting and sinks.

### 2.5 AI-Assisted Coding Workflow

- [ ] **REQ-LOG-015**: When using an AI coding assistant, log key lifecycle events: suggestion requested, suggestion shown, suggestion accepted/rejected, and any post-edit errors or test failures.
- [ ] **REQ-LOG-016**: Correlate these events with code locations (file, function, line span) so you can later detect patterns like "AI changes here often cause test failures."
- [ ] **REQ-LOG-017**: For agentic workflows that refactor logging itself, log the agent's actions and diffs (which files changed, how many statements touched, test outcomes) as separate audit events.
- [ ] **REQ-LOG-018**: In debugging sessions where you use AI to inspect logs, treat the AI as a read-only analyst by default, and keep its summaries in separate "analysis" logs tagged with the source log set.

## 3. Observability

Track infrastructure health, data quality, model performance, and lineage across the full ML lifecycle. The core dimensions are: infrastructure and service health (latency, throughput, error rates, resource usage); data quality and drift (feature distributions, schema validity, missing values); model performance and drift (task metrics, business KPIs, prediction distributions); and lineage, versioning, and reproducibility (model registry with training data, code, hyperparameters, and environment info). Required signals include metrics (time-series KPIs with dashboards and alerts), logs (inputs, predictions, confidence scores with redaction), and traces (distributed tracing across feature stores, model servers, and downstream services).

### 3.1 Scope and Goals

- [ ] **REQ-OBS-001**: Define business goals and success metrics for the model/system.
- [ ] **REQ-OBS-002**: Define which components are in scope (data pipelines, training jobs, online inference, agents, UI, etc.).
- [ ] **REQ-OBS-003**: Document owners (teams/people) responsible for each part of the stack.

### 3.2 Model Registry, Versioning, and Lineage

- [ ] **REQ-OBS-004**: Use a versioned model registry (or equivalent) for all deployable models.
- [ ] **REQ-OBS-005**: For each model version, record training dataset reference (location, time range, schema version).
- [ ] **REQ-OBS-006**: For each model version, record model code version (commit hash, container image).
- [ ] **REQ-OBS-007**: For each model version, record hyperparameters and training configuration.
- [ ] **REQ-OBS-008**: For each model version, record evaluation metrics on validation/test sets (by segment where relevant).
- [ ] **REQ-OBS-009**: Track data inputs/outputs across pipelines for lineage.
- [ ] **REQ-OBS-010**: Track environment information (runtime, libraries, containers) for lineage.
- [ ] **REQ-OBS-011**: Track pipeline parameter configuration linked to model versions.

### 3.3 Data Observability

- [ ] **REQ-OBS-012**: Validate data schema (types, required fields, ranges) for training and inference data.
- [ ] **REQ-OBS-013**: Monitor for missing values, outliers, and invalid categories.
- [ ] **REQ-OBS-014**: Monitor feature freshness and lag (for streaming/online systems).
- [ ] **REQ-OBS-015**: Compare live input distributions to training baselines (univariate + key joint distributions) for data drift.
- [ ] **REQ-OBS-016**: Monitor output label/feedback distributions where labels are available.
- [ ] **REQ-OBS-017**: Set alerts for significant schema changes.
- [ ] **REQ-OBS-018**: Set alerts for large distribution shifts or spikes in null/invalid rates.

### 3.4 Model Performance Monitoring

- [ ] **REQ-OBS-019**: Define task metrics (accuracy, F1, AUROC, RMSE, etc.) as applicable.
- [ ] **REQ-OBS-020**: Define business KPIs tied to the model (e.g., conversion, fraud catch rate).
- [ ] **REQ-OBS-021**: Measure latency and throughput (p50/p95/p99).
- [ ] **REQ-OBS-022**: Track metrics by cohort/segment (e.g., geography, traffic source, user segment).
- [ ] **REQ-OBS-023**: For GenAI/LLM systems, track prompt-response quality scores (human or automated evals).
- [ ] **REQ-OBS-024**: For GenAI/LLM systems, track safety issues (toxicity, PII leaks, hallucinations) where relevant.
- [ ] **REQ-OBS-025**: Configure dashboards and alerts for performance degradation vs. historical baselines.
- [ ] **REQ-OBS-026**: Configure dashboards and alerts for latency/error rate regressions.

### 3.5 Logging (Inputs, Outputs, and Decisions)

- [ ] **REQ-OBS-027**: Log inference request metadata (timestamps, IDs, model version).
- [ ] **REQ-OBS-028**: Log key features or feature summaries (with PII redacted/anonymized).
- [ ] **REQ-OBS-029**: Log predictions, confidence scores, and decision outcomes.
- [ ] **REQ-OBS-030**: For LLM/GenAI, log prompt, context, and response with redaction/pseudonymization policies.
- [ ] **REQ-OBS-031**: For LLM/GenAI, tag logs with safety flags, user feedback, and evaluation scores where available.
- [ ] **REQ-OBS-032**: Ensure logs are structured (JSON or equivalent) with consistent fields.
- [ ] **REQ-OBS-033**: Ensure logs are centralized and queryable in your logging/observability stack.
- [ ] **REQ-OBS-034**: Ensure logs are governed by retention and access policies appropriate for sensitive data.

### 3.6 Tracing and Infrastructure Metrics

- [ ] **REQ-OBS-035**: Implement distributed tracing across API gateway / UI.
- [ ] **REQ-OBS-036**: Implement distributed tracing across feature store / data service.
- [ ] **REQ-OBS-037**: Implement distributed tracing across model server / LLM gateway.
- [ ] **REQ-OBS-038**: Implement distributed tracing across downstream services (e.g., notification, billing).
- [ ] **REQ-OBS-039**: Collect CPU, GPU, memory, disk, and network usage metrics for each component.
- [ ] **REQ-OBS-040**: Monitor container/pod restarts and health checks.
- [ ] **REQ-OBS-041**: Monitor queue lengths and backlog for batch/stream pipelines.
- [ ] **REQ-OBS-042**: Link traces/metrics to model versions and requests where possible.

### 3.7 Explainability, Bias, and Safety

- [ ] **REQ-OBS-043**: Provide local explanations for individual predictions (e.g., feature attribution) where required.
- [ ] **REQ-OBS-044**: Provide global insights into feature importance and model behavior.
- [ ] **REQ-OBS-045**: Compare performance across key demographic or business segments for bias monitoring.
- [ ] **REQ-OBS-046**: Log and track bias metrics pre- and post-deployment as part of model cards.
- [ ] **REQ-OBS-047**: For GenAI, monitor for harmful or policy-violating content using safety evaluators (toxicity, self-harm, privacy, etc.).
- [ ] **REQ-OBS-048**: For GenAI, log safety incidents and mitigation actions for audit.

### 3.8 Alerting and Runbooks

- [ ] **REQ-OBS-049**: Define alert thresholds for data quality and drift events.
- [ ] **REQ-OBS-050**: Define alert thresholds for model performance drops.
- [ ] **REQ-OBS-051**: Define alert thresholds for latency/error spikes.
- [ ] **REQ-OBS-052**: Define alert thresholds for safety/bias incidents.
- [ ] **REQ-OBS-053**: Create runbooks for each alert type specifying possible root causes, immediate mitigation steps (rollback, traffic shifting, feature gating), and longer-term remediation (retraining, feature engineering, prompt updates).
- [ ] **REQ-OBS-054**: Test alerts and runbooks periodically (game days / chaos drills).

### 3.9 Experiment Tracking and Deployment

- [ ] **REQ-OBS-055**: Track experiment hyperparameters, datasets, seeds, and code versions.
- [ ] **REQ-OBS-056**: Store metrics and artifacts per run in a central tracking system.
- [ ] **REQ-OBS-057**: Use canary / shadow / A/B deployments for new models or prompts.
- [ ] **REQ-OBS-058**: Compare metrics between old and new versions before full promotion.
- [ ] **REQ-OBS-059**: Ensure rollback is quick and traceable to a specific prior version.

### 3.10 Compliance, Privacy, and Auditability

- [ ] **REQ-OBS-060**: Document data sources, data use, and consent requirements.
- [ ] **REQ-OBS-061**: Enforce PII/PHI handling and redaction rules in logs and datasets.
- [ ] **REQ-OBS-062**: Enforce access controls for observability tools and raw logs.
- [ ] **REQ-OBS-063**: Ensure you can reconstruct "which model, data, and config produced this prediction at this time" (full audit trail).

### 3.11 Project-Specific Observability

- [ ] **REQ-OBS-064**: Define domain-specific checks (e.g., fraud, medical safety, financial risk).
- [ ] **REQ-OBS-065**: Create custom evaluation datasets and red-team scenarios for GenAI agents.
- [ ] **REQ-OBS-066**: Document any additional governance or reporting needs (internal or regulatory).

## 4. Testing

Test the ML pipeline like software: unit tests for preprocessing, feature engineering, and inference wrappers; integration tests for multi-step flows (load → transform → train → evaluate); and end-to-end tests for realistic workflows in production-like environments. Validate data schemas and distributions before training and at inference time, including synthetic minimum functionality tests (MFTs) with hand-crafted datasets. Test model performance with holdout/cross-validation, segment-level checks, and robustness tests (invariance and directional expectations). For edge cases, test extreme values, missing features, adversarial inputs, and prompt injections. Automate regression tests in CI, run continuous evaluation in production, and maintain documented test catalogs with explicit promotion criteria.

### 4.1 Scope and Objectives

- [ ] **REQ-TST-001**: Define project goal and primary model use case.
- [ ] **REQ-TST-002**: Identify critical risks (data quality, bias, safety, drift, latency).
- [ ] **REQ-TST-003**: Decide which environments will be covered by tests (dev, staging, prod shadow).

### 4.2 Data and Schema Testing

- [ ] **REQ-TST-004**: Validate column names, types, and required fields (input schema tests).
- [ ] **REQ-TST-005**: Enforce allowed ranges and categorical domains.
- [ ] **REQ-TST-006**: Check missing values and invalid values per feature.
- [ ] **REQ-TST-007**: Detect duplicates and obvious outliers.
- [ ] **REQ-TST-008**: Compare basic stats (mean, std, quantiles) vs. training baselines for distribution checks.
- [ ] **REQ-TST-009**: Alert when drift exceeds defined thresholds.

### 4.3 Unit Tests (Code-Level)

- [ ] **REQ-TST-010**: Test individual preprocessing and feature engineering transforms on small, known inputs.
- [ ] **REQ-TST-011**: Assert shape, type, and invariants (e.g., normalized ranges) for transforms.
- [ ] **REQ-TST-012**: Cover metrics, loss functions, and custom logic in utility and helper function tests.
- [ ] **REQ-TST-013**: Ensure proper error handling for invalid inputs.
- [ ] **REQ-TST-014**: Test request parsing and response formatting in inference wrapper / serving code.
- [ ] **REQ-TST-015**: Verify default values and fallback behavior.

### 4.4 Integration and End-to-End Tests

- [ ] **REQ-TST-016**: Verify "load → preprocess → train → evaluate" works on a small fixture dataset (pipeline integration).
- [ ] **REQ-TST-017**: Ensure all paths and configs resolve correctly in CI.
- [ ] **REQ-TST-018**: Verify "request → feature store → model → response" works with test inputs (inference path).
- [ ] **REQ-TST-019**: Ensure errors surface with clear messages and appropriate status codes.
- [ ] **REQ-TST-020**: Verify full end-to-end "happy path" workflow passes in a production-like environment (e.g., container).

### 4.5 Model Evaluation Tests

- [ ] **REQ-TST-021**: Define target metrics (e.g., accuracy, F1, AUROC, RMSE, BLEU) and minimum thresholds.
- [ ] **REQ-TST-022**: Lock in a baseline model for regression comparison.
- [ ] **REQ-TST-023**: Evaluate metrics across key segments (e.g., geography, device type, demographic group).
- [ ] **REQ-TST-024**: Run invariance tests (label-preserving perturbations should keep predictions stable).
- [ ] **REQ-TST-025**: Run directional expectation tests (known changes should move predictions in expected directions).

### 4.6 Special Tests for GenAI / LLM Systems

- [ ] **REQ-TST-026**: Define evaluation criteria (e.g., relevance, correctness, style) and scoring protocol.
- [ ] **REQ-TST-027**: Maintain a curated set of prompts with expected qualities or reference outputs.
- [ ] **REQ-TST-028**: Create prompt suites to probe for policy violations (toxicity, self-harm, PII, prompt injection).
- [ ] **REQ-TST-029**: Implement automatic checks or human review for flagged outputs.
- [ ] **REQ-TST-030**: Re-run core prompt suite on each major model/prompt change and compare scores (regression tests).

### 4.7 Performance, Load, and Reliability Testing

- [ ] **REQ-TST-031**: Measure p50/p95/p99 latency under realistic load.
- [ ] **REQ-TST-032**: Test throughput vs. target QPS and record resource usage.
- [ ] **REQ-TST-033**: Validate scaling behavior and graceful degradation under peak load.
- [ ] **REQ-TST-034**: Confirm rate limiting and backpressure mechanisms.
- [ ] **REQ-TST-035**: Test timeouts, partial failures, and fallback strategies (e.g., cached predictions).

### 4.8 Bias, Fairness, and Safety

- [ ] **REQ-TST-036**: Compare metrics across protected or critical groups where appropriate (bias/fairness checks).
- [ ] **REQ-TST-037**: Document observed disparities and mitigation steps.
- [ ] **REQ-TST-038**: Test domain-specific safety scenarios (fraud, medical, financial, etc.).
- [ ] **REQ-TST-039**: Check for harmful failure modes and worst-case behavior.

### 4.9 Regression and CI/CD Integration

- [ ] **REQ-TST-040**: Capture baseline metrics and behaviors; fail if new versions regress beyond agreed tolerances.
- [ ] **REQ-TST-041**: Run unit and key integration tests on every commit/PR.
- [ ] **REQ-TST-042**: Run heavier evaluation tests on scheduled or pre-release pipelines.
- [ ] **REQ-TST-043**: Document required tests and thresholds for promoting a model to staging and production.

### 4.10 Reproducibility and Documentation

- [ ] **REQ-TST-044**: Fix random seeds for tests and training runs under test.
- [ ] **REQ-TST-045**: Record library versions, configs, and model artifacts for failed runs.
- [ ] **REQ-TST-046**: Maintain a catalog of tests (data, model, safety, performance) and what risks each covers.
- [ ] **REQ-TST-047**: Link tests to runbooks for debugging common failures.

### 4.11 Project-Specific Tests

- [ ] **REQ-TST-048**: Define domain-specific acceptance tests (e.g., fraud detection scenarios, ranking quality, recommendation diversity).
- [ ] **REQ-TST-049**: Wire custom dashboards and alerts into monitoring for "tests in production."
- [ ] **REQ-TST-050**: Implement any regulatory/compliance-driven tests required in your domain.

### 4.12 Test Environment Isolation

- [ ] **REQ-TST-051**: Isolate test environments from `.env` and dev configuration. Override environment variables in root `conftest.py` (or equivalent) to ensure tests run deterministically against mocks with calibrated thresholds.
- [ ] **REQ-TST-052**: Separate test thresholds calibrated for mocks from real model integration thresholds. Unit tests should run against mocks; real model integration tests should be in a separate category with appropriate tolerances and explicitly opted into.
- [ ] **REQ-TST-053**: When adding global handlers or middleware (logging buffers, metrics collectors), verify existing tests that assert on handler counts, middleware ordering, or singleton state.

## 5. Running the Application

- [ ] **REQ-RUN-001**: Create scripts for starting and running the application and place those scripts with appropriate names under the scripts folder.
- [ ] **REQ-RUN-002**: Document how to run these scripts in a file named app_cheatsheet.md.
- [ ] **REQ-RUN-003**: Add all the necessary URLs and other details in the app_cheatsheet.md.
- [ ] **REQ-RUN-004**: Scripts in subdirectories (e.g., `scripts/`) must resolve the project root before invoking tools that expect root-relative module paths or configs.
- [ ] **REQ-RUN-005**: Start scripts should be idempotent — detect and stop any existing process before starting a new one to avoid port conflicts and orphaned processes.
- [ ] **REQ-RUN-006**: Differentiate background process helpers for long-running daemons from batch job wrappers. Batch jobs must propagate the child process exit code instead of treating all exits as failures.
- [ ] **REQ-RUN-007**: Document default development credentials (from seed scripts) in the app cheatsheet so new developers can log in without reading source code.
- [ ] **REQ-RUN-008**: Provide start and stop scripts for every service in the stack (backend, frontend, workers). Consistency across services reduces onboarding friction.
- [ ] **REQ-RUN-009**: Start scripts must kill zombie processes holding the target port before binding. Use `lsof -ti:<PORT>` or equivalent to detect and terminate stale listeners so restarts succeed without manual intervention.
- [ ] **REQ-RUN-010**: When a frontend dev server proxies API requests to a backend, the proxy must have a connect timeout (e.g. 5 seconds) so that a dead backend produces a fast, clear error instead of an indefinite hang.
- [ ] **REQ-RUN-011**: Applications with slow startup (model loading, index building, large dataset ingestion) should log progress indicators during initialization and expose a readiness endpoint (separate from the liveness health check) so that dependent services and developers can distinguish "still starting" from "crashed."
- [ ] **REQ-RUN-012**: After a state-changing action that assigns or routes work (e.g. case assignment, job dispatch), the response and/or UI must surface who or what the work was routed to, so the user can immediately follow up without querying the system.

## 6. Security

- [ ] **REQ-SEC-001**: Store secrets in a secrets manager or environment variables; never commit secrets to version control.
- [ ] **REQ-SEC-002**: Validate and sanitize all external inputs before processing.
- [ ] **REQ-SEC-003**: Implement prompt injection defenses for LLM-facing inputs (input filtering, output validation, system prompt isolation).
- [ ] **REQ-SEC-004**: Enforce least-privilege access controls for services, APIs, and data stores.
- [ ] **REQ-SEC-005**: Scan container images and dependencies for known vulnerabilities before deployment.
- [ ] **REQ-SEC-006**: Sign and verify model artifacts to prevent tampering.
- [ ] **REQ-SEC-007**: Apply rate limiting and throttling to public-facing endpoints.
- [ ] **REQ-SEC-008**: Conduct periodic security reviews and penetration testing.
- [ ] **REQ-SEC-009**: Add model weights, binary artifacts (ONNX, safetensors), terminal recordings, and large data files to `.gitignore` proactively. Review untracked files before every commit to catch large binaries.

## 7. Configuration Management

- [ ] **REQ-CFG-001**: Use layered configuration (defaults, environment, overrides) with a single entry point.
- [ ] **REQ-CFG-002**: Separate configuration per environment (dev, staging, production) without code changes.
- [ ] **REQ-CFG-003**: Validate all configuration values at startup and fail fast on invalid settings.
- [ ] **REQ-CFG-004**: Version-control all hyperparameters and experiment configurations alongside code.
- [ ] **REQ-CFG-005**: Use feature flags for incremental rollout of new capabilities.
- [ ] **REQ-CFG-006**: Never use inline comments in `.env` files. Many parsers (pydantic-settings, python-dotenv) include the comment text as part of the value. Place comments on their own line above the variable.
- [ ] **REQ-CFG-007**: Never store secrets or connection strings in YAML config files. In layered config systems, YAML values passed as explicit constructor kwargs override environment variables. Use YAML only for non-sensitive defaults; secrets must come exclusively from environment variables or a secrets manager.
- [ ] **REQ-CFG-008**: Avoid redundant config flags that control the same behavior (e.g., `use_mocks` and `MODEL_BACKEND`). Use a single source of truth for mode switching and document precedence clearly if multiple flags exist.
- [ ] **REQ-CFG-009**: Isolate test configuration from development and production. Create a dedicated test config and override environment variables in test fixtures to prevent `.env` leakage into tests.

## 8. Error Handling and Resilience

- [ ] **REQ-ERR-001**: Define a consistent error response format across all services and APIs.
- [ ] **REQ-ERR-002**: Implement graceful degradation (fallback responses, cached results) when downstream services fail.
- [ ] **REQ-ERR-003**: Set explicit timeouts for all external calls (APIs, databases, model inference).
- [ ] **REQ-ERR-004**: Use retries with exponential backoff and jitter for transient failures.
- [ ] **REQ-ERR-005**: Log all exceptions with full context (stack trace, request ID, input summary) for debugging.
- [ ] **REQ-ERR-006**: Catch the narrowest exception type needed. Broad `except Exception` or multi-type catches like `except (ImportError, OSError)` mask real runtime errors. Fallback-to-mock patterns should only catch `ImportError`.
- [ ] **REQ-ERR-007**: Set explicit output limits (e.g., `max_tokens`) for every LLM generation call. Never rely on large defaults — a 4096-token default for a 15-word response causes multi-minute generation times.

## 9. Dependency Management

- [ ] **REQ-DEP-001**: Pin all dependency versions in lock files (e.g., `requirements.txt`, `poetry.lock`, `package-lock.json`).
- [ ] **REQ-DEP-002**: Use virtual environments or containers to isolate project dependencies.
- [ ] **REQ-DEP-003**: Run automated vulnerability scanning on dependencies (e.g., `pip-audit`, `npm audit`, Dependabot).
- [ ] **REQ-DEP-004**: Document system-level requirements (OS packages, GPU drivers, CUDA versions) needed to build and run the project.
- [ ] **REQ-DEP-005**: When using optional dependency groups (extras), setup and CI scripts must install all required extras explicitly (e.g., `uv sync --extra dev --extra ml --extra voice`), not just the dev extra.
- [ ] **REQ-DEP-006**: Use the project's package manager to execute commands (e.g., `uv run pytest` instead of `python -m pytest`) to ensure the correct virtual environment and dependencies are used.

## 10. Documentation Standards

- [ ] **REQ-DOC-001**: Write docstrings for all public modules, classes, and functions.
- [ ] **REQ-DOC-002**: Maintain an architecture document describing system components, data flow, and integration points.
- [ ] **REQ-DOC-003**: Create operational runbooks for deployment, rollback, and incident response.
- [ ] **REQ-DOC-004**: Keep a changelog that records notable changes, migrations, and breaking changes per release.
- [ ] **REQ-DOC-005**: Generate and publish API documentation (e.g., OpenAPI/Swagger) for all service endpoints.
- [ ] **REQ-DOC-006**: The deployment runbook must include prerequisite installation steps (database server, Node.js/npm, GPU drivers, system packages) as the first section, before any operational procedures.
- [ ] **REQ-DOC-007**: When scripts source configuration from `.env`, maintain a `.env.example` template that includes all required variables with descriptive comments on separate lines above each variable.

## 11. CI/CD

- [ ] **REQ-CIC-001**: Enforce PR quality gates (linting, type checks, unit tests) that must pass before merge.
- [ ] **REQ-CIC-002**: Run scheduled integration and evaluation tests (nightly or weekly) for model pipelines.
- [ ] **REQ-CIC-003**: Automate deployment to staging and production via pipeline (no manual steps).
- [ ] **REQ-CIC-004**: Run post-deploy smoke tests to verify critical paths after each deployment.
- [ ] **REQ-CIC-005**: Define pipelines as code (e.g., GitHub Actions, GitLab CI YAML) and version-control them.
- [ ] **REQ-CIC-006**: Configure pre-commit hooks for large file detection to prevent accidental commits of model weights, ONNX files, datasets, and other binary artifacts.
- [ ] **REQ-CIC-007**: Always review auto-generated database migration files (e.g., Alembic autogenerate) before applying. Auto-generated migrations may include extraneous schema changes beyond the intended modification.

## 12. Data Management and Versioning

- [ ] **REQ-DAT-001**: Version datasets and data transformations using a data versioning tool (e.g., DVC, LakeFS).
- [ ] **REQ-DAT-002**: Validate data pipeline outputs at each stage before downstream consumption.
- [ ] **REQ-DAT-003**: Define and enforce data retention and deletion policies.
- [ ] **REQ-DAT-004**: Store large artifacts (models, datasets) in dedicated artifact storage, not in Git.
- [ ] **REQ-DAT-005**: Track end-to-end data lineage from raw sources through features to model predictions.
