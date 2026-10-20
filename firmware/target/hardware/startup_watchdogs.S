/* Owned early-startup routine, offline diagnostic only. Register facts:
 * i.MX RT1170 RM Rev.5 ch78/79. Requires owned stack/code, exclusive chip
 * ownership, privileged Thread mode and PRIMASK=1. No C storage is used.
 * Poll counts bound software loops, NOT elapsed bus/watchdog time on silicon.
 * WDOG1/2 WDE cannot be cleared once set: reject rather than pretend otherwise.
 */
.syntax unified
.cpu cortex-m7
.thumb
.section .text.mpp_startup_watchdogs,"ax",%progbits
.global mpp_startup_watchdogs
.type mpp_startup_watchdogs,%function
.thumb_func
mpp_startup_watchdogs:
 mrs r1, ipsr
 mrs r2, control
 orrs r1, r2
 mrs r2, primask
 cmp r2, #1
 bne .Linvalid
 cmp r1, #0
 bne .Linvalid
 mrs r1, faultmask
 cmp r1, #0
 bne .Linvalid
 push {r4-r8, lr}
 /* Preflight every watchdog before any peripheral write. */
 ldr r4, =0x40030000
 ldrh r1, [r4]
 movs r0, #2
 tst r1, #4
 bne .Ldone
 ldr r5, =0x40034000
 ldrh r1, [r5]
 movs r0, #3
 tst r1, #4
 bne .Ldone
 ldr r6, =0x40038000
 ldr r6, [r6]
 ldr r7, =0x40c10000
 ldr r7, [r7]
 movs r0, #4
 tst r6, #0x80
 beq .Lsettled3
 tst r6, #0x20
 beq .Ldone
.Lsettled3:
 tst r6, #0x400
 beq .Lunsettled
 tst r6, #0x800
 bne .Lunsettled
.Lcheck4:
 movs r0, #5
 tst r7, #0x80
 beq .Lsettled4
 tst r7, #0x20
 beq .Ldone
.Lsettled4:
 tst r7, #0x400
 beq .Lunsettled
 tst r7, #0x800
 bne .Lunsettled
.Lpreflight_done:
 /* Separate power-down counters can run even with WDE=0. WCR is untouched. */
 ldrh r1, [r4, #8]
 tst r1, #1
 beq .Lpde2
 movs r1, #0
 strh r1, [r4, #8]
 dsb
 ldrh r1, [r4, #8]
 movs r0, #13
 tst r1, #1
 bne .Ldone
.Lpde2:
 ldrh r1, [r5, #8]
 tst r1, #1
 beq .Lrt3
 movs r1, #0
 strh r1, [r5, #8]
 dsb
 ldrh r1, [r5, #8]
 movs r0, #14
 tst r1, #1
 bne .Ldone
.Lrt3:
 ldr r0, =0x40038000
 mov r1, r6
 movs r2, #7
 bl .Ldisable_rt
 cmp r0, #0
 bne .Ldone
 ldr r0, =0x40c10000
 mov r1, r7
 movs r2, #10
 bl .Ldisable_rt
.Ldone:
 pop {r4-r8, pc}
.Lunsettled:
 movs r0, #6
 b .Ldone
.Linvalid:
 movs r0, #1
 bx lr
.size mpp_startup_watchdogs, .-mpp_startup_watchdogs

/* r0=base, r1=stable CS snapshot, r2=unlock error code (commit=+1, mismatch=+2).
 * The two 16-bit command words are consecutive stores to the 32-bit CNT
 * register, as in NXP's SDK; CMD32EN selects a single packed command instead.
 * Caller preserves r4-r8. No callbacks or C calls inside the write window. */
.type mpp_disable_rt_internal,%function
.thumb_func
mpp_disable_rt_internal:
.Ldisable_rt:
 tst r1, #0x80
 beq .Lrt_ok
 movw r3, #0xb37f
 and r3, r1, r3
 movw r12, #2048
 tst r1, #0x2000
 beq .Lunlock16
 ldr r1, =0xd928c520
 str r1, [r0, #4]
 b .Lunlock_wait
.Lunlock16:
 movw r4, #0xc520
 movw r5, #0xd928
 str r4, [r0, #4]
 str r5, [r0, #4]
.Lunlock_wait:
 ldr r1, [r0]
 tst r1, #0x800
 bne .Lwrite_cs
 subs r12, r12, #1
 bne .Lunlock_wait
 mov r0, r2
 bx lr
.Lwrite_cs:
 str r3, [r0]
 dsb
 movw r12, #2048
.Lcommit_wait:
 ldr r1, [r0]
 tst r1, #0x800
 bne .Lcommit_retry
 tst r1, #0x400
 bne .Lverify
.Lcommit_retry:
 subs r12, r12, #1
 bne .Lcommit_wait
 adds r0, r2, #1
 bx lr
.Lverify:
 movw r4, #0xb3ff
 and r1, r1, r4
 cmp r1, r3
 bne .Lmismatch
.Lrt_ok:
 movs r0, #0
 bx lr
.Lmismatch:
 adds r0, r2, #2
 bx lr
.size mpp_disable_rt_internal, .-mpp_disable_rt_internal
