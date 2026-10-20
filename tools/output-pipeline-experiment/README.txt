OFFLINE EXPERIMENT ONLY — no installable firmware

The patch moves headphone packing to callback entry using the previous
protected stereo block, matching the stock producer order. It adds one
eight-frame block of pipeline latency. NAM code, level pad, ramp and fault
threshold are unchanged. It is isolated under work/nam-output-pipeline/source;
the canonical NAMLNK07 sources, installed app and plug were not changed.

Both Marshall Lite and Fender Super Reverb A2 Lite match the pinned NAM
reference exactly for the 2,128 boundary samples in each case. The old and
new output sequences are identical except for the intended one-block delay.
Mute, effect-transition and latched-fault checks clear output on both halves.
The steady-state fixture deliberately skips the startup settle/ramp duration;
this does NOT replace the complete release regression suite.

The experiment retains identity NAMLNK07 solely for CPU harness compatibility.
Do not package or install that ELF. A physical test needs a separately named
release, complete final-build regressions and matching controller support.
Real DMA deadlines and audible benefit remain unverified.
No capture weights are included in this folder. The Fender model remains
private local test input.
