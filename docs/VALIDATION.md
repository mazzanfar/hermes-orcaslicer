# Validation record

Updated: 2026-09-27. Release 0.3.0. This record focuses on reproducible offline and simulated-protocol checks; it is not hardware certification.

The current acceptance suite has 14 tests and uses registered plugin handlers. It passes locally and all six Linux/macOS/Windows × Python 3.11/3.13 CI combinations passed for the 0.2.0 candidate ([run 36279726356](https://github.com/mazzanfar/hermes-orcaslicer/actions/runs/36279726356)). CI runs Python and simulated printer protocols, not the Orca application. Release checks additionally use actual Hermes and stock OrcaSlicer as described below.

## Executed locally

- Native Hermes `plugins doctor . --ci`: passes actual discovery, manifest parsing, namespaced import and registration of 20 tools. This caught and corrected a real skill-registration path type mismatch.
- Stock OrcaSlicer 2.4.2 on macOS: executable discovery and required CLI flags verified.
- Bambu Lab P1S 0.4 nozzle: an existing saved project was copied, edited and sliced through the stock CLI. G-code and sliced 3MF were produced; source remained separate. The user's project is not included in this repository.
- Prusa MK4 0.4 nozzle: a generated 5 mm cube was sliced from raw STL using resolved stock machine, process and PLA profiles. G-code and sliced 3MF produced; first-layer SVG and verified export exercised.
- Creality Ender-3 V3 0.4 nozzle: same raw-model workflow with Creality's own profiles. G-code and sliced 3MF produced; first-layer SVG and verified export exercised.
- Profile-library audit: 1,001 machine, 2,882 process and 5,913 filament preset inheritance chains resolved from the installed library. These are counts of presets, not distinct printer models. 39 additional instantiated presets had missing or ambiguous parents in that library; the plugin refuses to guess. Use an Orca-exported project with resolved settings for such cases.
- The lean acceptance suite now has 14 tests: one tool-to-TLS Bambu workflow, three tool-to-HTTP workflows plus 10 focused profile/artifact regressions. It passed locally and across all six Linux/macOS/Windows × Python 3.11/3.13 CI combinations in [run 36270671681](https://github.com/mazzanfar/hermes-orcaslicer/actions/runs/36270671681). The workflows use registered Hermes handlers and a loopback printer simulator for OctoPrint, Moonraker, PrusaLink v1, Duet and modern Flashforge HTTP, exercising actual HTTP authentication, multipart upload, start/control, observed status, lost replies across agent restart, redirects, busy/mismatched destinations, expired receipts and changed artifacts. Bambu uses actual TLS MQTT and FTPS sockets against a loopback simulator, including byte-identical upload, separate start, observed control states, and a lost acknowledgment across agent restart. These are protocol simulations, not hardware tests.
- The opt-in real Orca workflow now asserts prepare → slice → preview → byte-identical export through registered Hermes handlers for both Prusa and Creality; both passed locally. The Prusa project also passed per-object settings plus move/rotate/scale editing and a second real slice; settings persisted in the final project. Review-copy reuse is checked without launching GUI windows.

## Important observations

The existing acceptance workflows now exercise explicit plate selection, offline preflight for plain G-code and embedded selected-plate G-code, and rejection of a mismatched expected plate before upload. The suite remains at 14 tests. Stock Orca CLI runs passed with explicit Textured PEI selection for Prusa MK4, Creality Ender-3 V3 and Bambu P1S profiles; both artifact formats report the selected plate and first-layer temperature. These are offline slicing checks, not new physical prints.

The inherited `printer_settings_id` in a stock Creality base was just `Creality`; using it directly falsely rejected a compatible process. The plugin now sets the concrete selected preset's name when flattening machine settings.

macOS slicing of raw meshes aborted under the restricted development sandbox, despite `--help` working. The same offline commands succeeded outside that sandbox. Ordinary terminal use is the supported execution environment; this plugin cannot grant OS permissions.

The Prusa profile reported a long first-layer/startup estimate for a tiny cube. Estimates are surfaced as Orca produced them; the plugin does not “correct” firmware/macro timing guesses.

## Not yet established

- Broad physical print quality, fit, strength or hardware/firmware compatibility. Private development sessions are not a public certification program.
- Broad hardware/firmware validation of uploads, start and pause/resume/cancel. Protocol simulations alone do not establish this.
- Hardware/firmware behavior beyond independently observed configurations. Real Orca CLI execution is now covered on all three desktop platforms.
- General hardware compatibility across Bambu LAN, PrusaLink, Duet and Flashforge HTTP models and firmware versions. Bambu cloud and other unimplemented protocols remain unavailable.
- All unusual Orca profiles, conditional compatibility expressions, toolchangers and multi-material layouts.
- Automated understanding of complete geometry/support/arc visualization. Full interactive review is provided by native Orca; the plugin SVG remains a linear toolpath aid. Native launch is not proof of review.
- Hermes official catalog review or acceptance.

These are release limitations, not silently passing tests. Hardware testers should report printer model, firmware/server version, Orca version, nozzle/material, operating system and exact observed operation, omitting secrets and private files.

## 0.2.0 release acceptance

- Stock OrcaSlicer 2.4.2 on Ubuntu 24.04: the same `tests.live_slicer` workflow passed for Prusa MK4, Creality Ender-3 V3 and Bambu P1S presets. All four slices, including the edited Prusa project, completed. Explicit plate preflight, linear preview, unchanged source and byte-identical export assertions passed. This was offline slicing of a generated cube, with no printer contact.
- The Linux AppImage needed additional shared libraries on a minimal host. The acceptance environment extracted these privately and used `ORCA_SLICER_PATH`, `ORCA_PROFILES_DIR` and its library path explicitly. This does not establish automatic AppImage discovery or compatibility with every Linux distribution.
- A clean named Hermes profile installed the pinned public plugin with the normal installer and scanning enabled. A real model conversation loaded `orcaslicer:workflow` and invoked registered capability and diagnosis tools. No running gateway was restarted.
- Current Hermes catalog validation reported every check passing, including actual registration/capability matching and a `safe` security scan with no warnings. Plugin Doctor registered all 20 tools; compatibility scanning found no deprecated imports.
- The clean-install check exposed that an optional Bambu dependency was not installed by Hermes. Version 0.2.0 moves bounded `paho-mqtt>=2.1,<3` into the base dependencies; `[bambu]` remains an alias for older install instructions.

Camera framing, bounded reads, separate HTTP credentials, TLS identity checks, monitoring job identity and cancellation inference across a restarted client are exercised in the existing protocol workflows. These checks do not certify image contents, capture freshness or physical bed readiness.

- A complete Hermes model conversation discovered the exact Prusa profiles, prepared and sliced a generated cube, polled completion, generated a first-layer SVG, checked explicit-plate preflight and exported both G-code and sliced 3MF. The isolated conversation record confirms calls to the registered plugin tools and `skill_view`.
- A separate model conversation read a loopback Moonraker simulator twice, reported unchanged telemetry, fetched the generated 8×8 JPEG fixture and inspected it with Hermes vision. It described a solid-color image and did not infer bed readiness. The server recorded exactly two status GETs and one snapshot GET, with zero start commands. This is agent integration coverage, not hardware evidence.
- Installing the 0.2.0 candidate through Hermes prepared `paho-mqtt` 2.1.0 automatically in its managed runtime. Validation remained green with a `safe` scan and no warnings. Job state outside the installed source survived replacement.
- The 0.2.0 wheel contains the bundled skill and bounded base MQTT dependency and excludes tests, private session records and credentials.

## 0.3.0 cross-platform release gates

[The first expanded CI run](https://github.com/mazzanfar/hermes-orcaslicer/actions/runs/36281386035) passed actual OrcaSlicer 2.4.2 on Windows, macOS and Ubuntu 24.04, alongside the six existing installed-package/protocol jobs. The release workflow additionally includes Python 3.14 and runs on pushes, PRs, manual dispatch and a weekly schedule.

The acceptance runner imports the installed package from `site-packages` outside the repository import path, validates the package entry point, bundled skill, base MQTT dependency and CLI, then runs the existing protocol workflows. This prevents an incomplete wheel from passing solely because source files are present in the checkout.

Each real-slicer job downloads an official OS-specific Orca 2.4.2 asset, verifies its pinned SHA-256, and installs it only in the disposable runner directory. The same registered-tool workflow exercises:

- Raw generated STL with Prusa MK4, Creality Ender-3 V3 and Bambu P1S profiles.
- Explicit plate selection and preflight of both G-code and sliced 3MF.
- First and last layer linear previews.
- Fresh-service access to completed jobs and byte-identical export of both formats.
- Rejection of an existing export destination and preservation of the input model.
- Saved-project inspection, object process changes, move/rotate/scale and real reslicing.
- An actually malformed STL passed to Orca, followed by failed-job export rejection.

The protocol suite remains 14 substantive tests, extended rather than duplicated. Physical printing is never invoked by CI. Real-slicer results do not certify mechanical strength, fit, camera cleanliness assessment or every printer's firmware protocol. CodeQL runs separately on Python code and the release requires its check as well.
