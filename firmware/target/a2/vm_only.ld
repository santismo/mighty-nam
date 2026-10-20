/* Synthetic executable address. NOT a flash layout for the device. */
ENTRY(mpp_a2_process)
EXTERN(mpp_a2_load mpp_a2_reset)
MEMORY {
 LAB_CODE (rx) : ORIGIN = 0x08000000, LENGTH = 0x10000
 AMP_RAM (rw) : ORIGIN = 0x202e6020, LENGTH = 0x35fc0
}
SECTIONS {
 .text : { *(.text*) *(.rodata*) } > LAB_CODE
 .ARM.exidx : { *(.ARM.exidx*) } > LAB_CODE
 .data : { *(.data*) } > AMP_RAM
 .bss (NOLOAD) : { *(.bss*) *(COMMON) } > AMP_RAM
 /DISCARD/ : { *(.comment*) *(.ARM.attributes*) *(.init_array*) }
}
ASSERT(SIZEOF(.data)==0,"Explicit initialization only")
ASSERT(SIZEOF(.bss)<0x35fc0,"Exceeds retired AMP pool")
