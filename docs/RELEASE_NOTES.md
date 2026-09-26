# 0.1.0 preview

First public native Hermes plugin for stock OrcaSlicer, with 14 tools covering preset discovery, isolated job preparation, local slicing, warnings/estimates, linear layer preview, verified export and optional network printer operations.

Printer models come from OrcaSlicer's own installed profiles. File handoff is available across Orca-supported printers. Direct OctoPrint and Moonraker adapters implement upload, explicit start, status and requested pause/resume/cancel. Native Bambu/PrusaLink/Duet/Flashforge job submission is not included yet.

Validated:

- 24 unit/protocol tests on Linux/macOS/Windows with Python 3.11/3.13.
- Native Hermes runtime registration and public-repository installation with scanning enabled.
- Real stock OrcaSlicer 2.4.2 slicing on macOS using Bambu P1S, Prusa MK4 and Creality Ender-3 V3 profiles.
- First-layer SVG and export workflow on generated Prusa/Creality cube jobs.

Physical network operations are simulated in tests and still require real hardware validation. Real Windows/Linux slicing, full geometry/arc previews, per-object editing, additional connection protocols and official catalog review remain outstanding. This is a preview, not a claim of universal unattended printing.

Install:

```sh
hermes plugins install mazzanfar/hermes-orcaslicer
hermes plugins enable orcaslicer
```

Restart the Hermes session afterward. See README and docs/VALIDATION.md for configuration and exact limitations.
