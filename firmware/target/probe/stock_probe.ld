/* Retired stock AMP window; shared with the existing audited AMP overlay.
 * This probe and the A2 overlay are alternatives, never combined here. */
ENTRY(mpp_stock_amp_init)
MEMORY {
 CODE (rx) : ORIGIN = 0x1a0a4, LENGTH = 0x13e4
 STATE (rw) : ORIGIN = 0x202e4020, LENGTH = 0x1fe0
}
SECTIONS {
 .text : { *(.text*) *(.rodata*) } > CODE
 .ARM.exidx : { *(.ARM.exidx*) } > CODE
 .data : { *(.data*) } > STATE
 .bss (NOLOAD) : { *(.bss*) *(COMMON) } > STATE
 /DISCARD/ : { *(.comment*) *(.ARM.attributes*) }
}
ASSERT(SIZEOF(.data)==0,"No implicit initialized data")
ASSERT(SIZEOF(.bss)==96,"Unexpected diagnostic state")
