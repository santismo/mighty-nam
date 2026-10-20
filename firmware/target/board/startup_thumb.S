/* Cortex-M7 reset entry component, compile-only. No vector table or linker map
 * is invented here. Undefined integration symbols intentionally prevent this
 * object from becoming standalone firmware without board integration.
 * Interrupts stay masked through initialization. No flash writes occur.
 */
.syntax unified
.cpu cortex-m7
.fpu fpv5-d16
.thumb
.section .text.mpp_reset_entry,"ax",%progbits
.global mpp_reset_entry
.type mpp_reset_entry,%function
.thumb_func
mpp_reset_entry:
 cpsid i
 ldr r0, =__mpp_stack_top
 msr msp, r0
 ldr r0, =0xe000ed08
 ldr r1, =__mpp_vector_table
 str r1, [r0]
 ldr r0, =0xe000ed88
 ldr r1, [r0]
 orr r1, r1, #0x00f00000
 str r1, [r0]
 dsb
 isb
 bl mpp_runtime_initialize
 bl mpp_board_boot
1:
 cpsid i
 wfi
 b 1b
.size mpp_reset_entry,.-mpp_reset_entry
