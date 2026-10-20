/* Emulator-only vector/reset image. Link addresses are synthetic, not a NUX
 * application map or NXP ROM image. Physical cache/handoff support is pending. */
.syntax unified
.cpu cortex-m7
.fpu fpv5-d16
.thumb
.section .vectors,"a",%progbits
.global mpp_vectors
mpp_vectors:
 .word __stack_top
 .word mpp_lab_reset
 .rept 14
 .word mpp_lab_fault
 .endr
 .word mpp_vm_audio_irq
 .rept 239
 .word mpp_lab_fault
 .endr
.section .text.mpp_lab_reset,"ax",%progbits
.global mpp_lab_reset
.type mpp_lab_reset,%function
.thumb_func
mpp_lab_reset:
 cpsid i
 ldr r0, =__stack_top
 msr msp, r0
 movs r0, #0
 msr control, r0
 isb
 ldr r0, =0xe000ed14
 ldr r1, [r0]
 tst r1, #0x30000
 bne mpp_lab_handoff_rejected
 ldr r0, =0xe000ed08
 ldr r1, =mpp_vectors
 str r1, [r0]
 ldr r0, =0xe000ed88
 ldr r1, [r0]
 orr r1, r1, #0x00f00000
 str r1, [r0]
 dsb
 isb
 bl mpp_runtime_initialize
 bl mpp_board_boot
.global mpp_lab_idle
mpp_lab_idle:
 wfi
 b mpp_lab_idle
.global mpp_lab_handoff_rejected
mpp_lab_handoff_rejected:
 wfi
 b mpp_lab_handoff_rejected
.global mpp_lab_fault
.type mpp_lab_fault,%function
.thumb_func
mpp_lab_fault:
 cpsid i
 bl mpp_vm_stop
 b mpp_lab_idle
