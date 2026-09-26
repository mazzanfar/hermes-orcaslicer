# Hardware acceptance

Protocol simulations are reproducible tests, not hardware certification. Validate each model, firmware and connection mode independently using the sequence below. Private development-session records and camera images are kept outside this public repository. See [the reporting guide](HARDWARE_TESTING.md) for opt-in checks and a sanitized report template.

## Acceptance sequence when reachable

1. Establish current model/nozzle, material and actual firmware; read idle status and SD-card availability with verified TLS.
2. Prepare a small generated test model with exact installed P1S machine/process/filament presets. Inspect estimated time, first layer, complete native toolpaths, and AMS/external-spool mapping.
3. Upload the verified sliced 3MF; observe the printer remains idle and the correct unique file is stored.
4. After user authorization for that concrete job and confirmation of a clear bed/material, start once. Observe the expected filename and actual printing state.
5. Exercise pause/resume/cancel only with user intent; observe each actual state. A cancelled test does not establish successful completion or quality. Finish another approved test if needed.
6. Record observed result, firmware, slicer version, connection mode and any limitations. Keep private addresses, serials, credentials and model files out of public records.

Network simulators exercise the same tools and transport code, but cannot prove physical print quality or firmware compatibility. Do not mark other hardware validated based on the P1S test.
