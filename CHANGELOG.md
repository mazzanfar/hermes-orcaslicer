# Changelog

User-facing changes, newest first. Dates use UTC; historical previews remain labeled as such.

## [Unreleased]

## [0.5.0] — 2026-09-27

### Fixed
- Block model-steered forwarding of unrelated environment secrets by enforcing dedicated credential namespaces at configuration and use, including saved connections.
- Require HTTPS for credential-bearing printer/camera requests unless plaintext is explicitly enabled for that connection; includes Duet's default password.

### Changed
- Document migration for legacy connections and independent project status. Existing protocol workflows cover rejected names and blocked plaintext without adding test cases.

## [0.4.0] — 2026-09-27

### Added
- Verified wheel and source archive with SHA-256 checksums attached to the GitHub release.

### Changed
- Updated build tooling and SHA-pinned GitHub Actions through Dependabot.
- Clarified contribution workflow, duplicate-work searches, branch/PR naming and validation expectations; added README badges and this changelog.

## [0.3.0] — 2026-09-27

### Added
- Real OrcaSlicer 2.4.2 CI on Windows, macOS and Linux; installed-package checks across Python 3.11, 3.13 and 3.14.
- End-to-end coverage for first/last layer previews, both export formats, job recovery, overwrite protection, editing/reslicing and invalid meshes.
- Contribution and security reporting guides, protected-main checks, Dependabot and CodeQL.

### Changed
- Promoted the documented 20-tool workflows to a stable release. Hardware compatibility remains scoped to [recorded validation](docs/VALIDATION.md).

## [0.2.0] — 2026-09-26 (preview)

### Added
- Object editing, native review copies, explicit plate selection and offline upload preflight, expanding the plugin to 20 tools.
- Bambu LAN, PrusaLink, Duet and modern single-tool Flashforge connections.
- HTTP(S) JPEG/PNG and Bambu P1/A1 camera snapshots; richer progress, temperature, layer, error and job-identity monitoring.

### Changed
- Included Bambu MQTT in the base install; retained the optional `bambu` extra for compatibility.
- Consolidated acceptance into lean end-to-end workflows; validated real slicing on macOS and Linux.

## [0.1.0] — 2026-09-26 (preview)

### Added
- Initial 14-tool Hermes plugin: native Orca profile discovery, isolated preparation, slicing, estimates, layer previews and verified exports.
- OctoPrint and Moonraker upload, explicit start, status and requested pause/resume/cancel.
- Hermes installation checks, cross-platform protocol tests and real macOS slicing.

[Unreleased]: https://github.com/mazzanfar/hermes-orcaslicer/compare/v0.5.0...main
[0.5.0]: https://github.com/mazzanfar/hermes-orcaslicer/compare/v0.4.0...v0.5.0
[0.4.0]: https://github.com/mazzanfar/hermes-orcaslicer/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/mazzanfar/hermes-orcaslicer/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/mazzanfar/hermes-orcaslicer/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/mazzanfar/hermes-orcaslicer/releases/tag/v0.1.0
