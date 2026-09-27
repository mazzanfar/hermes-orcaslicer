# OrcaSlicer for Hermes Agent

[![Tests](https://github.com/mazzanfar/hermes-orcaslicer/actions/workflows/test.yml/badge.svg?branch=main)](https://github.com/mazzanfar/hermes-orcaslicer/actions/workflows/test.yml)
[![Security](https://github.com/mazzanfar/hermes-orcaslicer/actions/workflows/security.yml/badge.svg?branch=main)](https://github.com/mazzanfar/hermes-orcaslicer/actions/workflows/security.yml)
[![Release](https://img.shields.io/github/v/release/mazzanfar/hermes-orcaslicer)](https://github.com/mazzanfar/hermes-orcaslicer/releases/latest)
[![License: MIT](https://img.shields.io/github/license/mazzanfar/hermes-orcaslicer)](LICENSE)

A native Hermes plugin for preparing, slicing, reviewing and exporting 3D prints with **stock OrcaSlicer**. It uses OrcaSlicer's own installed printer, process and filament profiles—including custom presets—instead of maintaining a separate list of printer models.

**Release: 0.5.0.** Real slicing has been exercised on Windows, macOS and Linux with OrcaSlicer 2.4.2 and Bambu P1S, Prusa MK4 and Creality Ender-3 V3 profiles. These are slicing tests, not physical print certifications. Bambu LAN, PrusaLink, Duet and modern Flashforge HTTP adapters now join OctoPrint and Moonraker. Network adapters have protocol simulation tests; those tests do not certify particular hardware or firmware. See [validation](docs/VALIDATION.md).

## What works

- Discover the installed slicer and its profile libraries.
- Inspect existing Orca-compatible 3MF projects, including per-object metadata.
- Prepare STL, OBJ, STEP or 3MF jobs with exact printer/nozzle/material presets.
- Make bounded global and per-object process edits in an isolated copy, preserving the source.
- Move, rotate and scale project instances; request Orca automatic arrangement/orientation.
- Reuse one editable review copy for full interactive editing and toolpath review in native Orca. GUI launch is optional and requested at most once per job.
- Slice in the background, report failures and warnings, and read time/material estimates.
- Produce a per-layer SVG of linear extrusion moves and export the full sliced 3MF for Orca's complete preview.
- Select the physical plate explicitly and review sliced plate/nozzle/material temperatures and destination mapping before upload. An expected-plate mismatch blocks transfer before network access.
- Export verified G-code or sliced 3MF for SD/USB/native upload.
- Upload, explicitly start, monitor, pause/resume/cancel through the implemented protocols below.
- Capture a private local camera snapshot through an explicit HTTP(S) JPEG/PNG URL or a Bambu P1/A1 TLS camera connection.
- Read richer telemetry and changes since the previous observation; optionally match an upload receipt to the reported job filename.

No mouse automation, modified slicer build, bundled firmware or model service is required. The base installation includes `paho-mqtt` for Bambu LAN; other workflows use the Python standard library. You install OrcaSlicer separately. This project is independent of Nous Research and the OrcaSlicer project.

## Printer support: profiles versus connections

**The target is every printer OrcaSlicer supports, not a hard-coded list of brands.** Slicing uses the selected Orca profile; network operations use the configured connection protocol.

| Connection | Slice and export | Upload | Start/control/status |
|---|---|---|---|
| Any Orca-compatible printer, SD/USB/native handoff | Yes | Through the printer's normal workflow | Through the printer's normal workflow |
| OctoPrint | Yes | Implemented | Implemented; hardware validation pending |
| Klipper with Moonraker | Yes | Implemented | Implemented; hardware validation pending |
| Bambu LAN MQTT/FTPS | Yes | Sliced 3MF | Implemented; hardware validation pending |
| PrusaLink v1 | Yes | Plain G-code | Implemented; hardware validation pending |
| Duet RepRapFirmware 3 HTTP | Yes | Plain G-code | Implemented; hardware validation pending |
| Flashforge modern HTTP | Yes | Single-tool external-spool G-code | Implemented; hardware validation pending |
| Other cloud/vendor protocols and Flashforge material stations/legacy TCP | Yes, with an appropriate Orca profile | Native application/manual handoff | Not implemented |

An Orca printer preset is not a network API. File handoff is intentionally reported as `manual_handoff`, never “printing.” Do not route a proprietary printer through an unrelated adapter. See [connection setup and protocol limits](docs/CONNECTIONS.md). Use the [hardware acceptance checklist](docs/HARDWARE_VALIDATION.md) to validate your model and firmware.

Credential variables must use the `ORCA_` or `HERMES_ORCA_` namespace. Credential-bearing HTTP requires an explicit plaintext opt-in; see [setup and migration](docs/CONNECTIONS.md#credentials-and-migration).

## Install in Hermes

Install [OrcaSlicer](https://github.com/OrcaSlicer/OrcaSlicer/releases) and select your real printer/nozzle and filament in it. Save a small project to verify your settings first.

```sh
hermes plugins install mazzanfar/hermes-orcaslicer
hermes plugins enable orcaslicer
```

The [GitHub release](https://github.com/mazzanfar/hermes-orcaslicer/releases/latest) also provides a wheel, source archive and SHA-256 checksums for Python package users. Hermes uses the repository installation above.

This is a **repository installation**, not an official catalog entry. Follow Hermes' plugin installation review. Restart your Hermes session after enabling it. Load `orcaslicer:workflow` with Hermes’ skill tool before a printing workflow.

Hermes may report caution findings because the plugin invokes the local slicer and its test suite exercises rejection of invalid paths. Review the files it identifies and keep the scanner enabled.

Ask Hermes:

> Check OrcaSlicer, inspect my bracket.3mf, and prepare a 0.20 mm, three-wall version. Slice it and show me its first layer and time estimate. Export the sliced project without starting my printer.

For a raw model:

> Find the installed profiles for my Prusa MK4 with a 0.4 mm nozzle and PLA. Prepare and slice this STL with the compatible standard process. Show warnings and export the G-code.

For a network printer:

> Configure my Moonraker printer at https://printer.local using my exact Orca printer preset. Its API key is already in the ORCA_MOONRAKER_API_KEY environment variable. Check its status.

Then ask to upload a reviewed job and start it when the bed and material are ready. Upload and start are separate actions. Existing explicit authorization can be reused; the agent should not ask for redundant confirmation.

## Configuration

The plugin discovers normal macOS/Windows/Linux installations. Override paths when needed:

| Environment variable | Purpose |
|---|---|
| `ORCA_SLICER_PATH` | Full executable path; on macOS use `.../OrcaSlicer.app/Contents/MacOS/OrcaSlicer` |
| `ORCA_PROFILES_DIR` | Extra preset roots separated by the OS path separator (`:` on macOS/Linux, `;` on Windows) |
| `HERMES_ORCA_HOME` | Plugin state directory; defaults to `~/.hermes-orca` |
| Your chosen API-key variable | Secret used by a configured printer; its value is never an agent tool argument |

Set these in the environment inherited by Hermes. Desktop applications may not inherit terminal environment settings. Linux AppImages or custom launcher scripts may need an explicit `ORCA_PROFILES_DIR` pointing to their resource profiles; a minimal Linux host also needs Orca’s system libraries. `orca_diagnose` reports whether the executable can run and which profile roots were found.

Jobs live under `~/.hermes-orca/jobs/<id>/`. Each includes an input copy, resolved presets when supplied, a manifest, the exact command, a local slicing log and output artifacts. Printer records contain a URL and a secret **variable name**, not the secret. Nothing contacts a printer until a network tool is called. Registering the plugin performs no network or subprocess work.

### Projects and presets

- A saved Orca 3MF is the most reliable way to preserve custom geometry placement, multi-material mapping and start/end G-code.
- Raw meshes require all three preset types. Inheritance is resolved within the vendor's profile library. Missing/ambiguous parents fail rather than selecting another manufacturer's preset.
- A profile's explicit compatible-printer list is checked. Conditional compatibility expressions remain Orca's responsibility; inspect the result.
- `orca_prepare` changes globals and optionally asks Orca to arrange/orient. `orca_edit_project` edits object settings and instance transforms in a new 3MF; stale toolpaths are removed. Inspect IDs first. Rotations are about the instance origin; reassess bed contact and plate assignment. Native Orca covers advanced painting, modifiers and multi-material work. Any saved native edits require a new prepared/sliced job.
- Printer changes on a configured project are rejected; export its meshes and prepare using the new printer's presets.
- Slice one plate per job. Multi-plate projects require separate jobs with the appropriate `plate` index. No automatic consecutive printing.
- For missing/broken vendor preset dependencies, use a project exported by OrcaSlicer containing resolved settings.

### Preview and estimates

Pass `bed_type` to `orca_prepare` to select the physical plate instead of accepting a default. After slicing, call `orca_preflight` with `job_id`, `artifact`, optional configured destination `name`, and `expected_bed_type`. The offline report reads the hash-verified G-code (including the selected plate inside a sliced 3MF), shows temperatures and configured AMS/external-spool mapping, and identifies missing metadata or mismatches. Pass the same `expected_bed_type` to `orca_upload`; the upload reruns these checks and saves the report with its receipt. Omitting the expected plate produces a warning, not a claim that the physical plate matches. Existing source projects remain untouched.

Preflight reads slicer metadata; custom firmware macros may alter actual temperatures. It does not inspect the camera or certify a clean/empty bed, loaded material, geometry, adhesion or mechanical strength. Confirm physical readiness separately.

### Camera and monitoring

Configure `options.camera_url` for a direct HTTP(S) JPEG/PNG snapshot endpoint. Camera credentials are separate: `camera_api_key_env` names an optional X-Api-Key secret, and printer credentials are never forwarded to the camera. URLs must not embed credentials. Redirects are rejected. For a Bambu P1/A1, select `camera_protocol: "bambu_jpeg"` instead; it uses the configured printer CA, serial and access-code environment variable, with verified TLS on port 6000 (`camera_port` can override it). RTSP/RTSPS, cloud relay and continuous streaming are not implemented.

`orca_camera_snapshot(name=...)` saves one bounded image under the local state directory and returns its path for inspection. Images are private by default and are not published. A new request does not prove the camera image itself is current. Cropped, dark or obstructed images cannot establish that the bed is clear, and cameras cannot reliably certify grease-free surfaces.

`orca_monitor(name=..., receipt_id=...)` reads status and reports changed fields since the previous observation. Normalized `progress_percent` is 0–100 where supported; missing readings stay unknown. Temperatures, layers, remaining time and error details depend on the protocol. Bambu includes freshness and AMS tray telemetry; nested status deltas are merged. Receipt tracking reports an unknown job outcome if the filename is absent or belongs to a different job. A finished state or 100% alone does not establish that a requested job completed. This tool is a single read; scheduling and notifications remain the agent host's responsibility.

The SVG is a lightweight linear-extrusion review aid. It omits arcs and does not model every firmware command/tool offset; limitations are returned with it. Use `orca_open_native` to create/reuse a review copy; open it in the existing Orca window for full review. Set `launch=true` only when a launch is wanted; repeated calls do not create new copies or launch additional windows. No result certifies adhesion, mechanical strength, dimensional fit or arbitrary G-code safety. Times are the slicer's estimates; unknown macro duration can make them inaccurate.

## Tools

| Tool | Purpose |
|---|---|
| `orca_capabilities` | Protocol support, setup requirements and limits |
| `orca_edit_project` | New 3MF with object settings and instance transforms |
| `orca_open_native` | Reusable native editing/full-preview copy, optional one-time launch |
| `orca_diagnose` | Installed executable, version and supported flags |
| `orca_presets` | Find exact machine/process/filament presets |
| `orca_inspect` | Read project settings and object metadata |
| `orca_prepare` | Copy and configure a job |
| `orca_slice` / `orca_job` | Start and inspect local slicing |
| `orca_preview` | SVG of one layer's linear extrusion |
| `orca_export` | Copy a verified artifact to a new destination |
| `orca_printer_configure` / `orca_printers` | Configure/list explicit connections |
| `orca_printer_status` | Read hardware status |
| `orca_camera_snapshot` | Capture one local camera image for inspection |
| `orca_monitor` | Rich status, changes and optional receipt/job matching |
| `orca_preflight` | Offline review of sliced settings, expected plate and destination mapping |
| `orca_upload` | Upload without printing |
| `orca_start` | Submit a reviewed upload once |
| `orca_printer_control` | Requested pause/resume/cancel |

## Develop and test

Python 3.11+; CI exercises 3.11, 3.13 and 3.14. The base installation includes Bambu MQTT. TLS acceptance testing also uses the OpenSSL command-line utility.

```sh
git clone https://github.com/mazzanfar/hermes-orcaslicer.git
cd hermes-orcaslicer
python -m pip install .
python tests/installed_package.py
hermes plugins doctor . --ci
python -m orca_plugin.cli orca_diagnose
```

The JSON CLI can exercise every tool. Slicing in a standalone CLI process requires `--wait` so its worker stays alive:

```sh
python -m orca_plugin.cli orca_inspect '{"source":"/absolute/path/project.3mf"}'
python -m orca_plugin.cli orca_prepare '{"source":"/absolute/path/project.3mf","changes":{"layer_height":0.2,"wall_loops":3}}'
python -m orca_plugin.cli orca_slice '{"job_id":"ID_FROM_PREPARE"}' --wait
```

Opt-in real CLI tests: `python -m tests.live_slicer`. They generate a 5 mm cube, arrange/orient and slice with installed Prusa and Creality profiles, edit/reslice object settings and geometry, preview/export, and verify reusable review copies. They never contact a printer or launch GUI windows. On Linux a display or `xvfb-run` may be needed, depending on the Orca build. macOS app execution under a restrictive sandbox may abort even when `--help` works; run the smoke test in a normal local terminal.

See [changelog](CHANGELOG.md), [architecture](docs/ARCHITECTURE.md), [security and job semantics](SECURITY.md), [contributing](CONTRIBUTING.md), and [release checklist](docs/RELEASING.md).

For opt-in read-only hardware validation, configure the real connection and run `python -m tests.live_printer --name PRINTER --camera`. Omit `--camera` when unavailable; optionally pass `--receipt ID` to check job identity. `--state-dir` selects another plugin state directory. The runner sends no upload/start/control commands and writes a private local JSON report. Sharing reports or camera images is a separate user decision. See [hardware validation guide](docs/HARDWARE_TESTING.md).

## Contributing and maintenance

The repository is public and accepts issues and pull requests from forks. Only the repository owner has write/merge access. Protected `main` requires a PR and passing acceptance, real-slicer and security checks; automatic merging is disabled. See [CONTRIBUTING.md](CONTRIBUTING.md) for setup, the test matrix and protocol contribution requirements.

Dependabot checks Python dependencies and pinned GitHub Actions weekly, and security-update PRs are enabled. CodeQL, secret scanning and push protection are enabled. Use [private vulnerability reporting](https://github.com/mazzanfar/hermes-orcaslicer/security/advisories/new) for security issues.
