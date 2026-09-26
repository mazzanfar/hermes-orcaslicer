# Release checklist

- Run unit/protocol tests on Linux, macOS and Windows.
- Run Hermes' actual plugin doctor, not just a mock registration test.
- Run the opt-in real Orca CLI tests with the supported build(s).
- Exercise export and preview; ensure failed/unknown jobs cannot be sent.
- Update `docs/VALIDATION.md` with measured results and known limitations.
- Review `git diff --cached` for user models, profiles, credentials, addresses and private logs.
- Keep versions synchronized in `plugin.yaml`, `pyproject.toml` and `orca_plugin.__version__`.
- Publish preview versions as prereleases until hardware/OS acceptance coverage is adequate.
- Only submit to the Hermes catalog after the public repository and pinned release commit exist. Catalog admission requires a maintainer-reviewed PR; publishing this repository does not imply admission.

The catalog submission should use name `orcaslicer`, repository `https://github.com/mazzanfar/hermes-orcaslicer`, community tier, tools category and maintainer `mazzanfar`. Enumerate the tools from `plugin.yaml` and pin the exact reviewed 40-character commit. Do not invent a SHA or claim catalog availability before it is merged.
