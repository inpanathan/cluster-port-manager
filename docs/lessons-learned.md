# Lessons Learned

Consolidated from implementation sessions. Update this document after resolving non-trivial debugging sessions.
Last updated: YYYY-MM-DD.

---

## 1. Infrastructure & Deployment

<!-- Add lessons about deployment scripts, container runtimes, networking, OS/package management -->

---

## 2. Architecture & Code Patterns

### 2.1 Service Layer

<!-- Document patterns for service organization, dependency injection, abstractions -->

### 2.2 Configuration

| Pattern | Why |
|---------|-----|
| **Precedence: defaults < YAML < env vars** | YAML for non-sensitive defaults. Env vars for secrets and per-environment overrides. |
| **Never store secrets in YAML** | Pydantic-settings kwargs from YAML can override env vars. Secrets must be env-only. |
| **Never inline comments in `.env`** | Parsers include comment text as part of the value. Comments go on separate lines above. |
| **`__` (double underscore) for nested env vars** | `SETTING__NESTED_KEY` maps to `settings.setting.nested_key`. |

---

## 3. Testing

| Lesson | Details |
|--------|---------|
| **Override env vars in `conftest.py`** | Prevents `.env` leakage into tests. Test config is explicit, not inherited. |
| **Separate dev and test infrastructure ports** | Dev and test stacks must use different ports to avoid conflicts. |
| **Test doubles subclass real clients** | Override network methods, not the entire class. Keeps tests close to production behavior. |
| **Adding global handlers breaks test assertions** | New middleware or logging handlers can change handler counts. Verify existing tests after adding globals. |
| **Broad `except Exception` masks real errors** | Catch the narrowest type. Mock fallbacks should only catch `ImportError`. |

---

## 4. Deployment & Scripts

| Lesson | Details |
|--------|---------|
| **Idempotent != safe to re-run** | Sentinel files prevent step re-execution but don't detect downstream state. Check for running services before destructive ops. |
| **Kill zombie processes before port binding** | `lsof -ti:<PORT> \| xargs kill` before starting services. Prevents `EADDRINUSE`. |
| **Scripts must resolve project root** | Scripts in `scripts/` must `cd` to project root before invoking tools that expect root-relative paths. |
| **Head-first sequential start** | For distributed systems: start head node, poll for readiness, then start workers. |

---

## 5. Agent Workflow

### 5.1 Hard Rules

| Rule | Why |
|------|-----|
| **Plan filing is step zero** | Save to `coding-agent/plans/` before any code. |
| **"Stop" means stop** | When user interrupts, address why immediately. Don't continue background work. |
| **Don't duplicate user work** | If user provides a complete plan, they've done the research. Don't re-explore. |

### 5.2 Documentation Triggers

| When | Do |
|------|----|
| **After resolving a non-trivial bug** | Document in `docs/troubleshooting.md` with commands used (REQ-AGT-004). |
| **After creating scripts/commands/endpoints** | Update `docs/app_cheatsheet.md` before task completion. |
| **After adding alert types or failure modes** | Create/update runbook in `docs/runbook/`. |
| **After completing any non-trivial task** | Write summary to `coding-agent/summaries/<NNN>-<short-name>.md`. |

---

## 6. Unresolved / Deferred Items

<!-- Track items that need future attention -->

| Item | Source | Status |
|------|--------|--------|
| _Example: Frontend vitest tests_ | _Session N_ | _Not yet implemented_ |

---

## 7. Diagnostic Quick Reference

<!-- Add project-specific diagnostic commands as they are discovered -->

```bash
# Health check
curl http://localhost:8000/health

# Check for port conflicts
lsof -i :8000
```
