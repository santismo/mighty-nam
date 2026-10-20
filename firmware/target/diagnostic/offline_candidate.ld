/* Candidate layout only. Zero vectors and MSP come from saved stock payloads;
 * code budget, copy extent, free DTCM and DMA ownership are NOT established.
 * Deliberately no NXP boot header or NUX update wrapper. */
ENTRY(mpp_diag_reset)
MEMORY {
 CODE (rx) : ORIGIN = 0x00000000, LENGTH = 0x10000
 DATA (rw) : ORIGIN = 0x20000000, LENGTH = 0x30000
 STACK (rw) : ORIGIN = 0x20030000, LENGTH = 0x6000
 DMA_CANDIDATE (rw) : ORIGIN = 0x202c0000, LENGTH = 0x1000
}
SECTIONS {
 .vectors : { KEEP(*(.vectors)) } > CODE
 .text : { *(.text*) *(.rodata*) . = ALIGN(4); } > CODE
 .ARM.exidx : { *(.ARM.exidx*) } > CODE
 .data : { __data_start = .; *(.data*) . = ALIGN(4); __data_end = .; } > DATA AT> CODE
 __data_load = LOADADDR(.data);
 __image_load_end = LOADADDR(.data)+SIZEOF(.data);
 .bss (NOLOAD) : { __bss_start = .; *(.bss*) *(COMMON) . = ALIGN(4); __bss_end = .; } > DATA
 .dma (NOLOAD) : ALIGN(32) { __dma_start = .; KEEP(*(.dma)) __dma_end = .; } > DMA_CANDIDATE
 .stack (NOLOAD) : { __stack_bottom = .; . += LENGTH(STACK); __stack_top = .; } > STACK
 .constructors : { *(.init_array*) *(.ctors*) *(.preinit_array*) *(.fini_array*) } > CODE
 /DISCARD/ : { *(.comment*) *(.ARM.attributes*) }
}
ASSERT(SIZEOF(.vectors)==1024, "Vector table must cover all 234 RT1176 entries")
ASSERT(__stack_top==0x20036000, "Observed stock MSP")
ASSERT(__bss_end<=__stack_bottom, "State and stack overlap")
ASSERT(__image_load_end<=0x10000, "Candidate code budget exceeded")
ASSERT((__data_start%4)==0 && (__bss_start%4)==0, "Word initialization alignment")
ASSERT(SIZEOF(.dma)==640, "DMA reservation contract")
ASSERT((__dma_start%32)==0, "DMA cache-line alignment")
ASSERT(SIZEOF(.constructors)==0, "No dynamic constructors")
