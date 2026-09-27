# Contributing

Issues and focused PRs from forks are welcome. Only `@mazzanfar` has repository write/merge access. Contributions use the MIT license; report vulnerabilities [privately](https://github.com/mazzanfar/hermes-orcaslicer/security/advisories/new), following [SECURITY.md](SECURITY.md).

## Check existing work first

1. Search [open PRs](https://github.com/mazzanfar/hermes-orcaslicer/pulls?q=is%3Apr+is%3Aopen), [issues](https://github.com/mazzanfar/hermes-orcaslicer/issues?q=is%3Aissue) and [closed/merged PRs](https://github.com/mazzanfar/hermes-orcaslicer/pulls?q=is%3Apr+is%3Aclosed) using the feature, affected tool/protocol and error symptoms. Check current `main` too.
2. If a PR already covers the work, read its discussion and coordinate there. Help test, review or improve it where practical. For a different approach, link the existing work and explain the difference. Address the recorded reason before reviving a declined proposal.
3. Discuss large changes or new protocols in an issue before implementing them; include the workflow, API references and validation plan. Small fixes can go directly to a PR.

Repeat this search before opening your PR and link related work. Keep each PR focused on one problem.

## Set up your fork

Use Python 3.11+, Git and OpenSSL on PATH. Install stock OrcaSlicer separately for real slicing tests.

```sh
git clone https://github.com/YOUR_ACCOUNT/hermes-orcaslicer.git
cd hermes-orcaslicer
git remote add upstream https://github.com/mazzanfar/hermes-orcaslicer.git
git fetch upstream
git switch -c fix/camera-frame-timeout upstream/main
python -m venv .venv
```

Activate with `source .venv/bin/activate` on macOS/Linux or `.venv\Scripts\Activate.ps1` in PowerShell, then run `python -m pip install -e .`.

## Name branches, commits and PRs

Branches use `<type>/<short-description>` in lowercase with hyphens, optionally including an issue number: `fix/42-camera-frame-timeout`.

| Type | Purpose | Example PR title |
|---|---|---|
| `feat` | New capability | `feat(monitoring): report layer progress` |
| `fix` | Bug fix | `fix(camera): reject incomplete frames` |
| `docs` | Documentation | `docs: explain the contribution workflow` |
| `test` | Coverage | `test(upload): cover interrupted transfers` |
| `refactor` | Restructuring | `refactor: simplify status adapters` |
| `ci` | CI workflows | `ci: validate Windows slicing` |
| `chore` | Maintenance | `chore(deps): update MQTT dependency` |

Use `<type>(<optional-scope>): <specific outcome>` for commits and PR titles. Prefer titles under 72 characters. Avoid “Updates,” “Fix stuff” or “final-v2”; use GitHub's Draft status for unfinished work. Keep the title and description aligned with the final change.

## Describe your PR

Target upstream `main` and use the [template](.github/PULL_REQUEST_TEMPLATE.md):

- **What:** resulting behavior and scope; a before/after example for fixes.
- **Why:** the user problem, reproducer or missing workflow.
- **Approach:** important design choices and tradeoffs; keep small changes brief.
- **Validation:** commands/steps, actual results and relevant versions/platforms. Separate simulated tests from physical observations; state anything not run. Documentation-only changes can say so.
- **Limitations:** untested cases, compatibility or migration effects; “None known” is acceptable.
- **Related work:** issues and overlapping/dependent PRs. Use `Closes #123` only for a fully resolved issue; otherwise `Related to #123`, or state that none was found.

Before review, repeat the duplicate search, remove unrelated changes and check CI. Address review comments and update the description/results after revisions. Do not claim unperformed tests.

## Validate the change

| Change | Checks |
|---|---|
| Python or protocols | `python -m unittest discover -s tests -v` |
| Slicing, profiles, editing or export | `python -m tests.live_slicer` with stock Orca |
| Packaging or dependencies | Install with `python -m pip install .`, then `python tests/installed_package.py` |
| Hermes integration | Fresh profile; `hermes plugins doctor PATH --ci`, `compat PATH --json`, `validate PATH --json` |

Extend existing end-to-end workflows before adding tests; avoid redundant per-method mocks. CI tests installed packages on three OSes/Python versions, actual Orca binaries and CodeQL. See [measured coverage](docs/VALIDATION.md). Use an isolated Hermes profile and `HERMES_ORCA_HOME`; let Hermes manage its own dependencies. Real slicing tests never contact printers. Physical tests require explicit authorization and follow [HARDWARE_TESTING.md](docs/HARDWARE_TESTING.md).

## Preserve these contracts

- Keep printer definitions in Orca's profiles. Preserve source files; edited projects need a new slice and review.
- Configure explicit endpoints and credential variable names. No network scans, embedded secrets, TLS bypasses or credential-forwarding redirects.
- Separate upload from start. Unknown readiness is not ready; uncertain start outcomes must not be retried. Preserve artifact hashes and durable receipt protections.
- Distinguish command acceptance from physical outcome. Missing telemetry stays unknown; camera images cannot certify bed readiness.
- Use generated fixtures, licensed code and bounded dependencies. Keep private models, credentials, printer records and images out of commits and reports.
- Update relevant documentation and tool descriptions when behavior changes.

## Review and maintenance

Protected `main` requires a PR, passing checks and resolved conversations, including for the owner. Force pushes, branch deletion and automatic merging are disabled. External PRs may need owner approval before CI runs. Dependabot updates receive the same review; releases and Hermes catalog submissions are separate maintainer actions.
