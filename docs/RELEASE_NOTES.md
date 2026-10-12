# 0.5.1

`orca_diagnose` now distinguishes a failed OrcaSlicer process from an incompatible CLI. It reports the exit code and a bounded, printable runtime-error summary; missing flags are checked only after successful help output.

Both CodeQL steps use 4.38.3. Dependabot groups all future CodeQL updates, including major versions, so init and analyze stay compatible. The README banner is refreshed.

Wheel, source archive and SHA-256 checksums accompany the release. The 20-tool capability set and credential protections are unchanged. No new physical printer validation is claimed. See [changelog](../CHANGELOG.md) and [validation](VALIDATION.md).
