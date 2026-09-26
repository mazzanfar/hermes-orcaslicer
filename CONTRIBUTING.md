# Contributing

Keep printer model support in Orca's profiles; add connection protocols, not brand-specific slicing assumptions. Do not copy manufacturer presets or another project's source without checking its license. This plugin invokes OrcaSlicer as a separately installed program and does not redistribute its AGPL code or profile assets.

Run `python -m unittest discover -s tests -v` and `hermes plugins doctor . --ci`. New protocol adapters need tests for authentication, busy/disconnected states, upload without start, explicit start, uncertain responses and repeated calls. Document API references and real hardware/firmware tested. Do not mark protocol simulations as hardware certification.

Add an adapter in `orca_plugin/printers.py` or split it into its own module. Implement `status`, `upload`, `start` and `control`, then register its protocol in `ADAPTERS` and the tool schema. `status` must have an explicit `ready_to_start`; an unknown state must be false. `upload` must never auto-start. Return command acceptance separately from observed printer state. Do not add automatic timeout retries for state-changing requests.

The initial preview does not yet implement native Bambu/PrusaLink/Duet/Flashforge connections, interactive bed arrangement, per-object editing, complete 3D toolpath rendering, or restartable slice workers. Contributions should include a reproducible acceptance test rather than a capability claim alone.
