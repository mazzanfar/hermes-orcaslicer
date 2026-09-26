# 0.2.0 preview

Adds 20-tool workflows for object editing, reusable native review copies, explicit build-plate selection and offline preflight. Direct protocols now include Bambu LAN MQTT/FTPS, PrusaLink v1, Duet RepRapFirmware HTTP and modern single-tool Flashforge HTTP alongside OctoPrint and Moonraker.

Camera snapshots support explicit HTTP(S) JPEG/PNG endpoints and Bambu P1/A1 TLS JPEG. Monitoring reports available temperatures, progress, layers, errors and changes, with optional receipt-to-filename matching. Missing or different job identity remains unknown. Monitoring is one observation, not a background notification service.

The base installation now includes the bounded MQTT dependency so a normal Hermes install can use Bambu LAN without a separate manual package install. The `[bambu]` extra remains compatible. The diagnosis tool points agents to the bundled `orcaslicer:workflow` skill.

Validation includes a lean 14-test acceptance suite, actual Hermes runtime/catalog checks and stock OrcaSlicer 2.4.2 offline workflows on macOS and Linux. Windows has Python/protocol CI coverage; real Windows slicing remains unverified. See [validation](VALIDATION.md) for precise evidence and limits.

Direct connection support depends on the protocol, model and firmware; an Orca profile does not establish network compatibility. Cloud services, RTSP/RTSPS camera streams, continuous video, Flashforge material stations and autonomous printing remain outside this preview. Private camera and hardware-session records are not distributed.

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
