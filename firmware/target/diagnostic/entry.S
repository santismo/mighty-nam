/* Offline link/entry diagnostic. Not an approved NUX application image.
 * No peripheral start, USB, flash or ROM-entry operation is reachable here.
 * Cache/MPU-enabled handoffs deliberately stop before using candidate RAM.
 * This does not validate that a physical loader has populated our code/RAM. */
.syntax unified
.cpu cortex-m7
.fpu fpv5-d16
.thumb
.section .vectors,"a",%progbits
.global mpp_diag_vectors
mpp_diag_vectors:
 .word __stack_top
 .word mpp_diag_reset
 .rept 254
 .word mpp_diag_fault
 .endr
.section .text.mpp_diag_reset,"ax",%progbits
.global mpp_diag_reset
.type mpp_diag_reset,%function
.thumb_func
mpp_diag_reset:
 cpsid i
 /* No stack or RAM accesses before the entry checks. */
 mrs r1, ipsr
 movs r0, #1
 cmp r1, #0
 bne.w mpp_diag_rejected
 mrs r1, control
 movs r0, #2
 cmp r1, #0
 bne.w mpp_diag_rejected
 ldr r1, =0xe000ed14
 ldr r1, [r1]
 movs r0, #3
 tst r1, #0x30000
 bne mpp_diag_rejected
 ldr r1, =0xe000ed94
 ldr r1, [r1]
 movs r0, #4
 tst r1, #1
 bne mpp_diag_rejected
 mrs r1, faultmask
 movs r0, #5
 cmp r1, #0
 bne.w mpp_diag_rejected
#ifdef MPP_STARTUP_CONTROL
 /* Check declared TCM capacity BEFORE setting/using the candidate stack.
  * ARM SZ 3..10 encodes 4..512 KiB. Larger mappings are outside this RT1170
  * candidate contract. This does NOT prove FlexRAM bank backing/ownership,
  * loader copy length, DMA quiescence, or ECC initialization.
  */
 ldr r1, =0xe000ef90
 ldr r1, [r1]
 movs r0, #6
 tst r1, #1
 beq.w mpp_diag_rejected
 ubfx r1, r1, #3, #4
 movs r0, #7
 cmp r1, #3
 blo.w mpp_diag_rejected
 cmp r1, #10
 bhi.w mpp_diag_rejected
 mov.w r2, #512
 lsl.w r2, r2, r1
 ldr r3, =__image_load_end
 cmp r2, r3
 blo.w mpp_diag_rejected
 ldr r1, =0xe000ef94
 ldr r1, [r1]
 movs r0, #8
 tst r1, #1
 beq.w mpp_diag_rejected
 ubfx r1, r1, #3, #4
 movs r0, #9
 cmp r1, #3
 blo.w mpp_diag_rejected
 cmp r1, #10
 bhi.w mpp_diag_rejected
 mov.w r2, #512
 lsl.w r2, r2, r1
 ldr r3, =__stack_top
 sub.w r3, r3, #0x20000000
 cmp r2, r3
 blo.w mpp_diag_rejected
#endif
 ldr r0, =__stack_top
 msr msp, r0
 isb
 ldr r0, =0xe000ed08
 ldr r1, =mpp_diag_vectors
 str r1, [r0]
 dsb
 isb
#ifdef MPP_STARTUP_CONTROL
 bl mpp_startup_watchdogs
 cmp r0, #0
 bne mpp_diag_watchdog_failed
#endif
 ldr r0, =__data_load
 ldr r1, =__data_start
 ldr r2, =__data_end
1:
 cmp r1, r2
 bhs 2f
 ldr r3, [r0], #4
 str r3, [r1], #4
 b 1b
2:
 ldr r1, =__bss_start
 ldr r2, =__bss_end
 movs r3, #0
3:
 cmp r1, r2
 bhs 4f
 str r3, [r1], #4
 b 3b
4:
 ldr r1, =__stack_bottom
 ldr r2, =0x5354414b
 str r2, [r1]
 bl mpp_diag_main
.global mpp_diag_idle
mpp_diag_idle:
 wfi
 b mpp_diag_idle
.global mpp_diag_rejected
mpp_diag_rejected:
 /* r0 holds the reason; no trustworthy writable diagnostic memory yet. */
 wfi
 b mpp_diag_rejected
#ifdef MPP_STARTUP_CONTROL
.global mpp_diag_watchdog_failed
mpp_diag_watchdog_failed:
 /* r0 carries the watchdog failure; runtime storage is not initialized. */
 wfi
 b mpp_diag_watchdog_failed
#endif
.size mpp_diag_reset, .-mpp_diag_reset
.global mpp_diag_fault
.type mpp_diag_fault,%function
.thumb_func
mpp_diag_fault:
 cpsid i
 mrs r0, ipsr
.global mpp_diag_fault_park
mpp_diag_fault_park:
 /* Never call C, touch an untrusted exception frame, or try a reset. */
 wfi
 b mpp_diag_fault_park
.size mpp_diag_fault, .-mpp_diag_fault
