# Hardware validation

No physical print has been completed by this plugin during development. The owner's available hardware is a Bambu P1S. Other adapters currently have protocol simulations only.

## P1S session, 2026-09-26

- Existing Orca profile, printer serial, endpoint and saved access code were found locally. Credentials were used only in a child process environment and were not printed or committed.
- Tried read-only TCP/TLS connections to the two configured LAN services. Both returned the OS error `EHOSTUNREACH` before TLS or authentication.
- Waiting for confirmation of the current printer IP and LAN/developer-mode status. A VPN or local-network permission can also affect reachability; no network/security settings were changed.
- No files were uploaded and no printer start, pause, resume, cancel, heat or motion command was sent.

## Acceptance sequence when reachable

1. Establish current model/nozzle, material and actual firmware; read idle status and SD-card availability with verified TLS.
2. Prepare a small generated test model with exact installed P1S machine/process/filament presets. Inspect estimated time, first layer, complete native toolpaths, and AMS/external-spool mapping.
3. Upload the verified sliced 3MF; observe the printer remains idle and the correct unique file is stored.
4. After user authorization for that concrete job and confirmation of a clear bed/material, start once. Observe the expected filename and actual printing state.
5. Exercise pause/resume/cancel only with user intent; observe each actual state. A cancelled test does not establish successful completion or quality. Finish another approved test if needed.
6. Record observed result, firmware, slicer version, connection mode and any limitations. Keep private addresses, serials, credentials and model files out of public records.

Network simulators exercise the same tools and transport code, but cannot prove physical print quality or firmware compatibility. Do not mark other hardware validated based on the P1S test.
