/* V1.5.6 lab candidate only; existing retired AMP code and RAM.
   Model slot is separately patched in-memory at payload offset 0x344000. */
ENTRY(mpp_stock_amp_process)
EXTERN(mpp_stock_amp_init)
MEMORY {
 RETIRED_AMP_CODE (rx) : ORIGIN = 0x0001a0a4, LENGTH = 0x13e4
 RETIRED_AMP_STATE (rw) : ORIGIN = 0x202e4020, LENGTH = 0x37fc0
}
SECTIONS {
 .text : { *(.text*) *(.rodata*) } > RETIRED_AMP_CODE
 .ARM.exidx : { *(.ARM.exidx*) } > RETIRED_AMP_CODE
 .data : { *(.data*) } > RETIRED_AMP_STATE
 .bss (NOLOAD) : { *(.bss*) *(COMMON) } > RETIRED_AMP_STATE
 /DISCARD/ : { *(.comment*) *(.ARM.attributes*) }
}
ASSERT(SIZEOF(.data)==0,"No hidden initialized data")
ASSERT(SIZEOF(.bss)<0x37fc0,"Exceeded retired AMP state")
