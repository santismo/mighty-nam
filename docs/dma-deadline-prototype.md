# Guarded current-block DMA publication — offline only

`NAMDMP02` extends the earlier `NAMDMP01` research experiment with an early
previous-block prefill, private PCM staging, an ownership/deadline check, and a
latched fallback. It is independent of the active-chain experiment and is not
an installable release.

The renderer runs once per callback. Before DSP, the last completed PCM block
is copied into the eligible TX half. After DSP, protection and the existing GPT
check, the current result is rendered into private RAM. It replaces the early
fallback only if the publication guard accepts the current DMA state. A rejected
commit leaves the half untouched and selects previous-block mode until restart.
Processing continues; this guard does not alter the user's output-enable flag.

The guard saves/restores PRIMASK and reads the IRQ sequence, DWT control and
reset epoch, TX/RX descriptors and cursors, SAI error flags, TX watermark and
FIFO occupancy. It checks both possible safe cursor phases: the target half
has not started, or the preceding half still has its last minor transfer pending.
It rechecks the cursor snapshot before copying. It never reprograms a peripheral.

The guard requires more than four serial words of computed margin, a snapshot
under 2,048 DWT cycles, a complete masked transaction under 4,096 cycles, and an
entry age no greater than 100,000 cycles. These are **research assumptions**, not
proven hardware budgets. PRIMASK does not stop DMA, bus stalls or every exception.
A copy that exceeds its budget is detected after the stores; those stores cannot
be undone. A post-copy rejection is not proof that a partially fetched block
was prevented.

The fallback can repeat a block when switching from current-block to previous-
block output. If even the early prefill fails its check, the old whole half is
left in place; persistent rejection can repeat that stale audio. After a late processing fault, an already queued fallback may
play before a later eligible prefill writes silence. The experiment is not a
seamless crossfade or a universal guarantee against glitches.

## Tests

[Compiled ARM evidence](../evidence/dma-deadline-prototype/arm.json) covers the
guard decision matrix, both halves and cursor phases, PRIMASK restoration,
counter reset/wrap, malformed state, cursor movement during reads, budget edges,
and a post-copy overrun negative control. Actual whole-IRQ NAM + spring processing
runs with 8/16/32 output queue settings, with a forced late commit followed by
continued fallback and restart/reload. All peripheral timing remains synthetic.

[The conditional model](../evidence/dma-deadline-prototype/model.json) checks
publication windows under an explicit counter/serial-clock relationship and
bounded stores. Its deliberately over-budget copy produces a mixed first DMA
burst, demonstrating why post-copy detection cannot repair a violated assumption.
It does not simulate all SAI/eDMA arbitration or prove no fetch was in flight.

Dirty-RAM startup checks confirm only the intended TX watermark changes from
16 to 8; RX configuration, all four descriptors and codec writes remain unchanged.
The NAMLNK19 rebuild remains byte-identical. The guard fits the existing audited
regions by replacing optional per-effect profiling and one-shot driver snapshots;
whole-IRQ timing remains. Pages 118–126 now contain guard telemetry under marker
`0xd2000002`, not the old one-shot format.

No USB, MIDI, audio device, physical output control or updater is used by these
tests. The normal image builder refuses this prototype. Hardware measurement of
the budget, descriptor ownership, store visibility, heavy chains and bus service
is still required before an installation candidate can be justified.
