# Development conventions

Keep tests lean. Prefer end-to-end workflows through the public registered tools over per-function unit tests. Extend existing workflows instead of creating redundant test layers. Keep targeted regressions for important edge cases that are impractical to exercise end to end. Simulated printer tests must never be described as hardware validation.
