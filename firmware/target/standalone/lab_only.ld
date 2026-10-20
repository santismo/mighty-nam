/* Synthetic VM layout. Deliberately no FlexSPI header, boot data or NUX
 * container. This is not a physical USB RAM-download or flash image. */
ENTRY(mpp_lab_reset)
EXTERN(mpp_vm_status mpp_vm_audio_irq mpp_vm_stop mpp_vm_diagnostic)
MEMORY {
 LAB_CODE (rx) : ORIGIN = 0x08000000, LENGTH = 0x10000
 LAB_DATA (rw) : ORIGIN = 0x20000000, LENGTH = 0x1c000
 LAB_STACK (rw) : ORIGIN = 0x2001c000, LENGTH = 0x4000
 LAB_DMA (rw) : ORIGIN = 0x202c0000, LENGTH = 0x1000
 LAB_MAILBOX (rw) : ORIGIN = 0x202c1000, LENGTH = 0x4000
}
SECTIONS {
 .vectors : { KEEP(*(.vectors)) } > LAB_CODE
 .text : { *(.text*) *(.rodata*) } > LAB_CODE
 .ARM.exidx : { *(.ARM.exidx*) } > LAB_CODE
 .data : { __data_start = .; *(.data*) __data_end = .; } > LAB_DATA AT> LAB_CODE
 __data_load = LOADADDR(.data);
 .bss (NOLOAD) : { __bss_start = .; *(.bss*) *(COMMON) __bss_end = .; } > LAB_DATA
 .dma (NOLOAD) : ALIGN(32) { __dma_start = .; KEEP(*(.dma)) __dma_end = .; } > LAB_DMA
 .mailbox (NOLOAD) : ALIGN(32) { KEEP(*(.mailbox)) } > LAB_MAILBOX
 .constructors : { *(.init_array*) *(.ctors*) } > LAB_CODE
 __stack_bottom = ORIGIN(LAB_STACK);
 __stack_top = ORIGIN(LAB_STACK)+LENGTH(LAB_STACK);
 /DISCARD/ : { *(.comment*) *(.ARM.attributes*) }
}
ASSERT(SIZEOF(.vectors)==1024,"Vector layout")
ASSERT(SIZEOF(.constructors)==0,"No dynamic initialization")
ASSERT(__bss_end<=__stack_bottom,"State/stack overlap")
ASSERT(SIZEOF(.dma)==640,"DMA contract")
