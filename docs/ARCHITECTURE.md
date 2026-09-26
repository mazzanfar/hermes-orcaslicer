# Architecture

`__init__.py` is the directory-plugin wrapper. `orca_plugin.register` registers native Hermes tools and the bundled workflow skill. It constructs lightweight service objects; it does not probe the system, start a process or contact a printer during registration. The same service powers the JSON command-line interface and the pip entry point.

## Layers

1. `profiles.py`: discover installed profile roots, resolve vendor-scoped inheritance, inspect 3MF settings, validate bounded edits. Names come from preset JSON rather than filenames. Missing parents are errors; no cross-vendor fallback when ambiguous.
2. `slicer.py`: discover/check the stock binary, create immutable-by-contract job input copies, execute CLI slicing, collect artifacts and inspect G-code metadata. No machine model allow-list. An explicit compatible-printer list is checked, but Orca remains the slicer and configuration validator.
3. `preview.py`: a portable SVG of linear extrusion for a selected layer. Reports omitted arc/coordinate semantics. It is not a replacement for Orca's native 3D preview.
4. `printers.py`: profile-bound connection records and capability-specific protocol adapters. Local file export is universal. Direct upload/start/status depends on the connection type.

## Job states

`prepared → slicing → sliced | failed`

If a service loses ownership of a running process after restart, `orca_job` reports `unknown`. It does not certify leftover output. Long-lived Hermes sessions own asynchronous workers; the standalone CLI waits for its worker. A 30-minute timeout terminates the slicer. Input/artifact hashes prevent accidental edits from silently reusing a prior review. This is not protection against an attacker who controls the plugin's state files.

Remote receipts progress `uploaded → start_outcome_unknown → start_accepted`. The attempt marker is created exclusively before network submission. A failed/uncertain response cannot automatically be retried. Upload names include random suffixes to avoid replacing another client's files.

## Compatibility boundaries

Stock Orca's CLI flags differ between releases. `orca_diagnose` checks required flags. Linux GUI-linked builds may need Xvfb. The CLI and preset format are tested against OrcaSlicer 2.4.2 on macOS; other OS builds need live validation in addition to unit CI.

Built-in configuration assets are not copied into this repository. A saved 3MF is preferred for printer-specific customizations, multi-material mapping and unusual profiles. Existing object/plate overrides are preserved. Arbitrary geometry transformations and arbitrary G-code execution are deliberately absent from the first release.

## Upstream references

- [Hermes native plugin guide](https://hermes-agent.nousresearch.com/docs/developer-guide/plugins)
- [Hermes catalog submission/review](https://hermes-agent.nousresearch.com/docs/user-guide/features/plugin-catalog)
- [OrcaSlicer CLI actions](https://www.orcaslicer.com/wiki/cli/cli_actions)
- [OctoPrint files API](https://docs.octoprint.org/en/main/api/files.html)
- [OctoPrint job API](https://docs.octoprint.org/en/main/api/job.html)
- [Moonraker printer API](https://moonraker.readthedocs.io/en/latest/external_api/printer/)
- [Moonraker file management](https://moonraker.readthedocs.io/en/latest/external_api/file_manager/)

The executable's own `--help` was used to verify the exact slicing flags. No modified Orca fork or third-party MCP implementation is required.
