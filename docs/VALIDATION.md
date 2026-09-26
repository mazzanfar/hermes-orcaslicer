# Validation record

Date: 2026-09-26. Preview release; no physical print was started as part of development.

The 24-test suite passed locally and in all six CI combinations: Linux, macOS and Windows, each with Python 3.11 and 3.13. Wheel installation and its Hermes entry point/bundled skill were verified in an isolated Python environment. Installation from the public GitHub repository, with Hermes security scanning enabled, and Plugin Doctor against that installed copy both passed in a disposable Hermes home. The user's active Hermes installation was not changed.

## Executed locally

- Native Hermes `plugins doctor . --ci`: passes actual discovery, manifest parsing, namespaced import and registration of 14 tools. This caught and corrected a real skill-registration path type mismatch.
- Stock OrcaSlicer 2.4.2 on macOS: executable discovery and required CLI flags verified.
- Bambu Lab P1S 0.4 nozzle: an existing saved project was copied, edited and sliced through the stock CLI. G-code and sliced 3MF were produced; source remained separate. The user's project is not included in this repository.
- Prusa MK4 0.4 nozzle: a generated 5 mm cube was sliced from raw STL using resolved stock machine, process and PLA profiles. G-code and sliced 3MF produced; first-layer SVG and verified export exercised.
- Creality Ender-3 V3 0.4 nozzle: same raw-model workflow with Creality's own profiles. G-code and sliced 3MF produced; first-layer SVG and verified export exercised.
- Profile-library audit: 1,001 machine, 2,882 process and 5,913 filament preset inheritance chains resolved from the installed library. These are counts of presets, not distinct printer models. 39 additional instantiated presets had missing or ambiguous parents in that library; the plugin refuses to guess. Use an Orca-exported project with resolved settings for such cases.
- Unit/protocol suite covers vendor isolation, inheritance failures, source preservation, edit validation, nozzle bounds, concrete preset identity, failed slicing, archive path isolation, hashes, export collisions, SVG semantics, profile mismatch, printer busy state, upload without start, expired receipts, no start retry, HTTP request formatting, redirect refusal, secret-safe errors and plugin registration.

## Important observations

The inherited `printer_settings_id` in a stock Creality base was just `Creality`; using it directly falsely rejected a compatible process. The plugin now sets the concrete selected preset's name when flattening machine settings.

macOS slicing of raw meshes aborted under the restricted development sandbox, despite `--help` working. The same offline commands succeeded outside that sandbox. Ordinary terminal use is the supported execution environment; this plugin cannot grant OS permissions.

The Prusa profile reported a long first-layer/startup estimate for a tiny cube. Estimates are surfaced as Orca produced them; the plugin does not “correct” firmware/macro timing guesses.

## Not yet established

- Physical print quality, fit, strength or hardware behavior on any printer.
- Live uploads/start/pause/resume/cancel on OctoPrint or Moonraker hardware. Tests simulate the documented protocols.
- Real Orca CLI execution on Linux and Windows. Cross-platform unit CI does not establish this.
- Native Bambu, PrusaLink, Duet, Flashforge or proprietary cloud control.
- All unusual Orca profiles, conditional compatibility expressions, toolchangers and multi-material layouts.
- Complete geometry/support/arc visualization; the lightweight SVG is only a linear toolpath aid.
- Hermes official catalog review or acceptance.

These are release limitations, not silently passing tests. Hardware testers should report printer model, firmware/server version, Orca version, nozzle/material, operating system and exact observed operation, omitting secrets and private files.
