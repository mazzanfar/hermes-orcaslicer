# OrcaSlicer for Hermes Agent

A native Hermes plugin for preparing, slicing, reviewing and exporting 3D prints with **stock OrcaSlicer**. It uses OrcaSlicer's own installed printer, process and filament profiles—including custom presets—instead of maintaining a separate list of printer models.

**Status: 0.1.0 preview.** Real slicing has been exercised on macOS with OrcaSlicer 2.4.2 and Bambu P1S, Prusa MK4 and Creality Ender-3 V3 profiles. These are slicing tests, not physical print certifications. Network adapters have protocol simulation tests; physical printer validation is still needed. See [validation](docs/VALIDATION.md).

## What works

- Discover the installed slicer and its profile libraries.
- Inspect existing Orca-compatible 3MF projects, including per-object metadata.
- Prepare STL, OBJ, STEP or 3MF jobs with exact printer/nozzle/material presets.
- Make bounded global process edits in an isolated copy, preserving the source.
- Slice in the background, report failures and warnings, and read time/material estimates.
- Produce a per-layer SVG of linear extrusion moves and export the full sliced 3MF for Orca's complete preview.
- Export verified G-code or sliced 3MF for SD/USB/native upload.
- Upload, explicitly start, monitor, pause/resume/cancel through OctoPrint and Moonraker.

No mouse automation, modified slicer build, bundled firmware, model service, or Python runtime dependencies are required. You install OrcaSlicer separately. This project is independent of Nous Research and the OrcaSlicer project.

## Printer support: profiles versus connections

**The target is every printer OrcaSlicer supports, not a hard-coded list of brands.** Slicing uses the selected Orca profile; network operations use the configured connection protocol.

| Connection | Slice and export | Upload | Start/control/status |
|---|---|---|---|
| Any Orca-compatible printer, SD/USB/native handoff | Yes | Through the printer's normal workflow | Through the printer's normal workflow |
| OctoPrint | Yes | Implemented | Implemented; hardware validation pending |
| Klipper with Moonraker | Yes | Implemented | Implemented; hardware validation pending |
| Bambu native LAN/cloud, PrusaLink, Duet, Flashforge, other proprietary protocols | Yes, with an appropriate Orca profile | Native application/manual handoff in this release | Not implemented in this release |

An Orca printer preset is not a network API. File handoff is intentionally reported as `manual_handoff`, never “printing.” Do not route a proprietary printer through an unrelated adapter. A P1S can use this plugin to slice/export its sliced 3MF; native P1S job submission is not yet implemented.

## Install in Hermes

Install [OrcaSlicer](https://github.com/OrcaSlicer/OrcaSlicer/releases) and select your real printer/nozzle and filament in it. Save a small project to verify your settings first.

```sh
hermes plugins install mazzanfar/hermes-orcaslicer
hermes plugins enable orcaslicer
```

This is a **repository installation**, not an official catalog entry. Follow Hermes' plugin installation review. Restart your Hermes session after enabling it.

Hermes may report caution findings because the plugin invokes the local slicer and its test suite exercises rejection of invalid paths. Review the files it identifies and keep the scanner enabled.

Ask Hermes:

> Check OrcaSlicer, inspect my bracket.3mf, and prepare a 0.20 mm, three-wall version. Slice it and show me its first layer and time estimate. Export the sliced project without starting my printer.

For a raw model:

> Find the installed profiles for my Prusa MK4 with a 0.4 mm nozzle and PLA. Prepare and slice this STL with the compatible standard process. Show warnings and export the G-code.

For a network printer:

> Configure my Moonraker printer at http://printer.local:7125 using my exact Orca printer preset. Its API key is already in the MOONRAKER_API_KEY environment variable. Check its status.

Then ask to upload a reviewed job and start it when the bed and material are ready. Upload and start are separate actions. Existing explicit authorization can be reused; the agent should not ask for redundant confirmation.

## Configuration

The plugin discovers normal macOS/Windows/Linux installations. Override paths when needed:

| Environment variable | Purpose |
|---|---|
| `ORCA_SLICER_PATH` | Full executable path; on macOS use `.../OrcaSlicer.app/Contents/MacOS/OrcaSlicer` |
| `ORCA_PROFILES_DIR` | Extra preset roots separated by the OS path separator (`:` on macOS/Linux, `;` on Windows) |
| `HERMES_ORCA_HOME` | Plugin state directory; defaults to `~/.hermes-orca` |
| Your chosen API-key variable | Secret used by a configured printer; its value is never an agent tool argument |

Set these in the environment inherited by Hermes. Desktop applications may not inherit terminal environment settings.

Jobs live under `~/.hermes-orca/jobs/<id>/`. Each includes an input copy, resolved presets when supplied, a manifest, the exact command, a local slicing log and output artifacts. Printer records contain a URL and a secret **variable name**, not the secret. Nothing contacts a printer until a network tool is called. Registering the plugin performs no network or subprocess work.

### Projects and presets

- A saved Orca 3MF is the most reliable way to preserve custom geometry placement, multi-material mapping and start/end G-code.
- Raw meshes require all three preset types. Inheritance is resolved within the vendor's profile library. Missing/ambiguous parents fail rather than selecting another manufacturer's preset.
- A profile's explicit compatible-printer list is checked. Conditional compatibility expressions remain Orca's responsibility; inspect the result.
- Edits change global process settings. Object and plate overrides remain intact and can supersede them. Per-object editing and automatic orientation are not exposed in 0.1.0.
- Printer changes on a configured project are rejected; export its meshes and prepare using the new printer's presets.
- Slice one plate per job. Multi-plate projects require separate jobs with the appropriate `plate` index. No automatic consecutive printing.
- For missing/broken vendor preset dependencies, use a project exported by OrcaSlicer containing resolved settings.

### Preview and estimates

The SVG is a lightweight linear-extrusion review aid. It omits arcs and does not model every firmware command/tool offset; limitations are returned with it. Open the sliced 3MF in OrcaSlicer for full review. No result certifies adhesion, mechanical strength, dimensional fit or arbitrary G-code safety. Times are the slicer's estimates; unknown macro duration can make them inaccurate.

## Tools

| Tool | Purpose |
|---|---|
| `orca_diagnose` | Installed executable, version and supported flags |
| `orca_presets` | Find exact machine/process/filament presets |
| `orca_inspect` | Read project settings and object metadata |
| `orca_prepare` | Copy and configure a job |
| `orca_slice` / `orca_job` | Start and inspect local slicing |
| `orca_preview` | SVG of one layer's linear extrusion |
| `orca_export` | Copy a verified artifact to a new destination |
| `orca_printer_configure` / `orca_printers` | Configure/list explicit connections |
| `orca_printer_status` | Read hardware status |
| `orca_upload` | Upload without printing |
| `orca_start` | Submit a reviewed upload once |
| `orca_printer_control` | Requested pause/resume/cancel |

## Develop and test

Python 3.11+; no third-party runtime dependencies.

```sh
git clone https://github.com/mazzanfar/hermes-orcaslicer.git
cd hermes-orcaslicer
python -m unittest discover -s tests -v
hermes plugins doctor . --ci
python -m orca_plugin.cli orca_diagnose
```

The JSON CLI can exercise every tool. Slicing in a standalone CLI process requires `--wait` so its worker stays alive:

```sh
python -m orca_plugin.cli orca_inspect '{"source":"/absolute/path/project.3mf"}'
python -m orca_plugin.cli orca_prepare '{"source":"/absolute/path/project.3mf","changes":{"layer_height":0.2,"wall_loops":3}}'
python -m orca_plugin.cli orca_slice '{"job_id":"ID_FROM_PREPARE"}' --wait
```

Opt-in real CLI tests: `python -m tests.live_slicer`. They generate a 5 mm cube, slice with installed Prusa and Creality profiles, and never contact a printer. On Linux a display or `xvfb-run` may be needed, depending on the Orca build. macOS app execution under a restrictive sandbox may abort even when `--help` works; run the smoke test in a normal local terminal.

See [architecture](docs/ARCHITECTURE.md), [security and job semantics](SECURITY.md), [contributing](CONTRIBUTING.md), and [release checklist](docs/RELEASING.md).
