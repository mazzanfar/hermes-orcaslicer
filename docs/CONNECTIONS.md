# Printer connections

Slicing uses Orca's profiles. The connection protocol must match the printer's actual server/firmware. `orca_capabilities` reports implemented operations and limitations. These implementations have simulator tests, not hardware certification. No cloud credentials, LAN scanning, heater controls or arbitrary G-code tool are provided.

Camera snapshots are available through an explicitly configured HTTP(S) endpoint or the Bambu P1/A1 TLS JPEG protocol. See the README for setup. Automatic plate-clear certification is not implemented: readiness telemetry and camera images cannot establish that the entire build plate is empty or free of grease and residue. Confirm physical bed readiness separately before starting.

All connections bind to an exact `printer_profile`. `orca_upload` returns a receipt without printing; `orca_start` consumes a reviewed receipt once. `orca_printer_control` accepts pause/resume/cancel. Always observe status after a command: acceptance is not proof of motion or completion.

Every `*_env` option names an environment variable that must start with `ORCA_` or `HERMES_ORCA_` (for example `ORCA_OCTOPRINT_KEY`). When a connection carries a credential, its URL must be `https://` unless `options.allow_plaintext_credentials: true` is set deliberately; see [SECURITY.md](../SECURITY.md).

## Bambu LAN

Requires firmware that allows local MQTT/FTPS, usually LAN-only mode and, on authorization-controlled firmware, Developer Mode. Cloud submission is not implemented. Enabling these modes is a user decision; the plugin never changes printer security settings.

On macOS, allow Local Network access for the application running the agent. A denied permission can surface as `EHOSTUNREACH` even when the printer responds to ping. P1S hardware checks have verified secure status and upload; physical printing remains pending (see [validation record](HARDWARE_VALIDATION.md)).

The base plugin installation includes `paho-mqtt>=2.1,<3`; let Hermes prepare its declared dependencies when enabling the plugin. Python 3.11+ is required. The `[bambu]` extra remains a compatibility alias. Other adapters use the Python standard library.

Configure `kind=bambu_lan`, `url=https://PRINTER_IP`, and these `options`:

- `serial`: exact printer serial number.
- `access_code_env`: name of the environment variable containing the existing LAN access code.
- `ca_file`: trusted manufacturer CA/certificate file. Orca includes `Resources/cert/printer.cer` in its macOS app; use the equivalent trusted installed resource on other platforms. TLS checks both certificate trust and serial identity. Never substitute an unverified certificate or disable verification to clear an error.
- `use_ams`: false for external spool, true for AMS. With AMS, `ams_mapping` must explicitly map each used filament/tool index to a tray index; unused entries can be -1. Do not infer mapping from colors alone.
- `bed_levelling` defaults true. `flow_cali`, `vibration_cali`, and `timelapse` default false. Choose only options supported by the actual printer.
- `mqtt_port` and `ftps_port` default to 8883 and 990.

Only a verified sliced `.3mf` is accepted. The selected plate must have embedded G-code. FTPS uploads a unique file and checks its size; start uses the selected plate and archive checksum. An MQTT PUBACK alone would not establish printer acceptance: the implementation waits for the printer's matching command response. A missing response leaves the outcome unknown, even when printing may have begun.

The agent keeps one MQTT session per connection, requests one initial snapshot, and merges subsequent P1 telemetry deltas. Stale/disconnected state is not ready. It does not reconnect and replay commands. Restart the agent to establish a new session after disconnect, then inspect printer status before further action. Different firmware may vary in acknowledgment and telemetry behavior; test on hardware before relying on this workflow.

## PrusaLink v1

Use `kind=prusalink`, the actual HTTP(S) endpoint, and `options.storage` (`usb`, `local`, or `sdcard`; default `usb`). Authentication can use `api_key_env`, or HTTP Digest with `options.username` and `options.password_env`. Credentials remain in environment variables.

This adapter requires the v1 API with PUT file upload. Upload explicitly disables printing and overwriting. Start is a separate POST to the file. Pause/resume/cancel target the current job ID. Older OctoPrint-compatible-only PrusaLink and Prusa Connect cloud are not covered by this adapter.

## Duet RepRapFirmware 3

Use `kind=duet`, the controller HTTP(S) endpoint, and optionally `options.password_env`. Without it, the protocol's default `reprap` password is used. Status uses the object model. Unique HTTP sessions are closed after each request; older shared IP-based sessions are left to expire so another client's session is not explicitly disconnected.

Uploads use `rr_upload`; start/pause/resume/cancel send only the fixed firmware commands required for those operations. Command buffering does not mean the requested state has been reached. Duet Software Framework (`/machine/...`) is a separate protocol and is not implemented.

## Flashforge modern HTTP

Use `kind=flashforge_http`, the printer endpoint (normally `http://PRINTER_IP:8898`, so `options.allow_plaintext_credentials: true` is required for the access code), `options.serial`, and `options.access_code_env`. This adapter covers the modern `/detail`, `/uploadGcode`, `/printGcode`, and `/control` protocol. `bed_levelling` defaults true at start.

Currently supports single-tool external-spool jobs. Material-station mappings, multi-tool jobs, Creator-specific command variations, and legacy TCP/serial protocol are not implemented; use native Orca for those. Upload explicitly sets `printNow=false`. Only the documented `ready` state is considered ready; finish/cancel dialogs must be resolved at the printer. Firmware may acknowledge an unsupported control command without acting, so verify status afterward.

## OctoPrint and Moonraker

Configure the actual endpoint and optional API-key environment variable. Both upload without selecting/starting and use separate start/control operations. Existing profile/hash/receipt guards apply to every protocol.

## API references

- [Prusa's maintained OpenAPI specification](https://github.com/prusa3d/Prusa-Link-Web/blob/master/spec/openapi.yaml)
- [Duet's firmware HTTP reference](https://github.com/Duet3D/RepRapFirmware/wiki/HTTP-requests)
- [Orca's Flashforge upload implementation](https://github.com/OrcaSlicer/OrcaSlicer/blob/main/src/slic3r/Utils/Flashforge.cpp)
- [Flashforge protocol research](https://github.com/Parallel-7/flashforge-api-docs/wiki/HTTP-REST-API) — independent firmware research, not a vendor support guarantee.
- [Bambu's LAN networking explanation](https://blog.bambulab.com/answering-network-security-concerns/)
- [Bambu protocol research](https://github.com/Doridian/OpenBambuAPI) — independent protocol documentation; this is not an official Bambu SDK.
- [Eclipse Paho client documentation](https://eclipse.dev/paho/files/paho.mqtt.python/html/client.html)
