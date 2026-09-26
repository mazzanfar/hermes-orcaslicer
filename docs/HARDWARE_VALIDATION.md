# Hardware validation

No physical print has been completed by this plugin during development. The owner's available hardware is a Bambu P1S. Other adapters currently have protocol simulations only.

## P1S session, 2026-09-26

- Existing Orca profile, printer serial, endpoint and saved access code were found locally. Credentials were used only in a child process environment and were not printed or committed.
- Initial connections returned `EHOSTUNREACH`. After the owner enabled macOS Local Network access, both MQTT and implicit FTPS connected with certificate and serial-identity verification enabled.
- The real registered status tool received fresh telemetry: `FINISH`, ready, SD card available and 0.4 mm nozzle. Firmware version has not yet been established.
- A generated 5 mm cube was prepared and sliced offline with the P1S 0.4 mm machine, its compatible 0.20 mm Standard process and Generic PLA. Orca estimated 0.24 g and 8m 4s including startup. The first-layer SVG was generated. This is a candidate test job, pending full review and physical bed/material/AMS confirmation.
- Hardware exposed an FTPS incompatibility: Python's default upload waited for a TLS shutdown reply that the P1S did not send. The complete file was stored, but the operation timed out. The adapter now closes the data socket and requires FTP completion plus matching remote size. The existing TLS workflow covers this behavior; all 14 tests passed locally.
- The real registered upload tool successfully transferred the 28,139-byte sliced 3MF, verified its stored size and created a receipt. Fresh status afterward remained `FINISH` and ready. Diagnostic attempts also left uniquely named test files on the SD card.
- No printer start, pause, resume, cancel, heat or motion command was sent. Physical printing, full native toolpath review and current bed/material/AMS confirmation remain outstanding.

## Acceptance sequence when reachable

1. Establish current model/nozzle, material and actual firmware; read idle status and SD-card availability with verified TLS.
2. Prepare a small generated test model with exact installed P1S machine/process/filament presets. Inspect estimated time, first layer, complete native toolpaths, and AMS/external-spool mapping.
3. Upload the verified sliced 3MF; observe the printer remains idle and the correct unique file is stored.
4. After user authorization for that concrete job and confirmation of a clear bed/material, start once. Observe the expected filename and actual printing state.
5. Exercise pause/resume/cancel only with user intent; observe each actual state. A cancelled test does not establish successful completion or quality. Finish another approved test if needed.
6. Record observed result, firmware, slicer version, connection mode and any limitations. Keep private addresses, serials, credentials and model files out of public records.

Network simulators exercise the same tools and transport code, but cannot prove physical print quality or firmware compatibility. Do not mark other hardware validated based on the P1S test.
