# Hardware validation guide

Protocol simulations are regression coverage, not evidence about physical firmware. Each tester should record the printer model, firmware/server version, Orca version, host OS and the exact operations observed. Do not extrapolate a result to all models of a brand.

## Read-only checks

Configure an explicit destination and credentials using the normal setup. From the repository run:

```sh
python -m tests.live_printer --name YOUR_CONFIGURED_PRINTER --camera
```

Omit `--camera` if no supported camera is configured. The runner records whether status is available, which fields are present, and whether one framed image was received. It neither sends print commands nor certifies camera image quality. Reports are stored under the selected state directory's `validation/` folder; screenshots remain under `snapshots/`. Inspect images separately. Review and redact any report before voluntarily sharing it; nothing is sent to GitHub automatically.

## Controlled print checks

1. Prepare a small generated model using exact printer/nozzle/material presets and an explicit physical plate. Review preflight and toolpaths.
2. Upload with the expected plate type. Confirm the unique file was stored while the printer remained idle.
3. With user authorization and current bed/material readiness, start once. Match the receipt filename and observe actual printing. Never retry a start whose outcome is unknown.
4. For an explicitly authorized control test, pause after model printing begins, observe the paused state, resume and observe running, then cancel and observe a stopped/cancelled state. Command acceptance alone does not pass a check.
5. A cancelled job does not establish successful completion. Separately finish an approved job and inspect the physical result. Record quality observations independently of firmware-reported completion.
6. Test loss of telemetry or an interrupted client only when it can be done safely with user authorization. Do not disable network security or inject errors into an active printer. Simulator lost-response coverage does not count as this hardware check.

## Current coverage boundaries

The automated suite covers five HTTP adapters and Bambu MQTT/FTPS plus TLS JPEG framing. Generic HTTP snapshot validation includes separate credentials, redirect rejection and invalid image rejection. It remains a lean set of end-to-end workflows.

Monitoring preserves raw firmware states alongside normalized phases. Bambu `FAILED` with cancellation code `0x0300400C` is reported as `cancelled`, consistent with Orca's shipped HMS catalog; unrelated HMS entries remain visible and require attention. A Bambu running state at layer zero is reported as `preparing`. If firmware later clears the code, an accepted cancel is retained for up to one hour only for the same configured printer and exact job filename, with no current fault/HMS entry. This record does not retry commands. Unmatched jobs or unknown command outcomes remain unclassified. Neither distinction changes the physical-readiness rules.

P1/A1-style TLS JPEG is implemented; other Bambu models may require unsupported RTSPS. Generic snapshots require an explicitly supplied HTTP(S) endpoint. Duet and Flashforge status fields remain more limited than Bambu, Moonraker and OctoPrint. A status read with missing fields is not proof those sensors or capabilities exist. Real Orca execution is covered on Windows, Linux and macOS. Physical testing across additional printer protocols still requires suitable hardware; see VALIDATION.md for the distinction.

References: [Bambu camera protocol research](https://github.com/Doridian/OpenBambuAPI/blob/main/video.md), [Moonraker printer API](https://moonraker.readthedocs.io/en/latest/external_api/printer/), [OctoPrint printer API](https://docs.octoprint.org/en/main/api/printer.html).
