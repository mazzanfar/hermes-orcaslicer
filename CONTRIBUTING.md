# Contributing to OrcaSlicer for Hermes

Bug reports, documentation improvements, test results and focused pull requests are welcome. This repository is public: anyone can open issues or propose a change from a fork. Repository write and merge permissions are controlled by the owner, `@mazzanfar`. Opening a PR does not grant those permissions.

## Before starting

Search open and closed issues/PRs first. For a large change or a new protocol, open an issue describing the user workflow, official API references and how it can be validated. Small fixes can go directly to a PR. Report vulnerabilities privately through [GitHub security reporting](https://github.com/mazzanfar/hermes-orcaslicer/security/advisories/new); see [SECURITY.md](SECURITY.md).

Keep printer model definitions in OrcaSlicer's profiles, including custom profiles. This plugin integrates stock OrcaSlicer; it does not maintain a second printer database or redistribute Orca binaries, vendor presets or third-party model assets. Check licenses before contributing source or fixtures. Use small generated models for reproducible examples.

## Development setup

Use Python 3.11 or newer, Git, and OpenSSL on PATH for the TLS protocol tests. Install stock OrcaSlicer separately when testing real slicing.

```sh
git clone https://github.com/YOUR_ACCOUNT/hermes-orcaslicer.git
cd hermes-orcaslicer
python -m venv .venv
```

Activate with `source .venv/bin/activate` on macOS/Linux or `.venv\Scripts\Activate.ps1` in Windows PowerShell, then:

```sh
python -m pip install -e .
python -m unittest discover -s tests -v
```

Create a branch in your fork. Keep each PR focused on one user-visible problem; use descriptive commits such as `fix(camera): reject incomplete frames`.

For Hermes integration, use a disposable named profile or `HERMES_HOME` and set `HERMES_ORCA_HOME` to a separate temporary state directory. Do not alter a running personal gateway to test a plugin. Install through Hermes' normal dependency preparation path; do not mutate its managed environment with pip.

## Validation that matters

Extend existing end-to-end workflows through the registered tools before adding tests. A small number of substantive workflows is preferred to per-method mocks or tests that merely mirror implementation. Focused regressions are useful for important cases that cannot be covered practically end to end.

| Change | Relevant checks |
|---|---|
| Any Python change | `python -m unittest discover -s tests -v` |
| Slicing, editing, profiles or export | `python -m tests.live_slicer` with stock Orca installed |
| Registration, packaging or dependencies | Fresh Hermes install; `hermes plugins doctor PATH --ci`, `hermes plugins compat PATH --json`, `hermes plugins validate PATH --json` |
| Printer protocol, camera or monitoring | Existing HTTP/TLS end-to-end workflows; opt-in hardware checks when available |
| Release | All required CI checks, installed-wheel workflow, real cross-platform slicing and documented Hermes acceptance |

Real-slicer tests generate their own cube, exercise raw and saved-project workflows, object edits, preflight, previews and export, and never contact a printer. Set `ORCA_SLICER_PATH` and `ORCA_PROFILES_DIR` when discovery needs help. Linux AppImages need their system libraries and sometimes `xvfb-run`. `test-output/` is ignored and contains local artifacts.

CI exercises Python/protocol workflows across operating systems and Python versions, installed package behavior, and actual pinned OrcaSlicer binaries. An OS matrix of simulated protocols alone is not evidence that the Orca application works there. Read [VALIDATION.md](docs/VALIDATION.md) for measured coverage.

Physical testing is opt-in and requires a reviewed job and explicit user authorization. Follow [HARDWARE_TESTING.md](docs/HARDWARE_TESTING.md). A simulator passing is never hardware certification. Report exact model, firmware, connection mode and observed operation; redact serials, addresses, credentials, private models and camera images. Never repeat a start with an unknown outcome to make a test pass.

## Implementation contracts

- Preserve source projects and installed presets. Edits produce new projects; edited projects must be sliced and reviewed again.
- Configure explicit network endpoints and credential variable names. No network scans, embedded secrets, TLS bypasses or credential-forwarding redirects.
- Keep upload separate from start. Status must explicitly establish readiness; unknown state is not ready.
- Bind artifacts and receipts to their hashes and configured destination. Preserve durable duplicate-start protection across restarts.
- Report command acceptance separately from physical outcome. Do not automatically retry uncertain state-changing requests.
- Camera images and logs are private local artifacts. A camera cannot certify cleanliness or physical readiness; missing telemetry stays unknown.
- Add protocols through adapters and declared capabilities, not printer-brand slicing branches. Document supported API versions and limitations.
- Use bounded dependencies, with the oldest API-compatible minimum and a suitable upper bound. Pin CI actions to commit SHAs. Dependabot proposes updates; it does not merge them.

## Pull requests and review

Use the PR template to explain the problem, resulting behavior, validation and remaining limitations. Include a reproducer for fixes. Update tool descriptions, README and relevant protocol documentation when behavior changes. Do not commit generated builds, private test outputs or secrets.

`main` requires a PR, passing required checks and resolved review conversations, including for the owner. Force pushes and branch deletion are blocked. The owner reviews and merges contributions; outside contributors work through forks. No automatic merging is enabled. CI for an outside contributor may await owner approval before it can run.

Dependency PRs receive the same review and checks as code changes. Security updates are enabled independently of weekly version-update checks. A release/tag and a Hermes catalog pin update are separate maintainer actions; contributors must not claim catalog acceptance before upstream review.

Contributions are made under this repository's MIT license. Be respectful, explain disagreements with evidence, and keep reports focused on reproducible behavior.
