/* Uses only the unused tail inside the already audited retired-AMP code span.
 * Canonical A2 ELF ends 0x1b2d0. State leaves its 32-byte upper guard untouched.
 * No startup entry or hardware image: the caller must test this offline overlay.
 */
ENTRY(mpp_capture_irq)
MEMORY { CODE (rx) : ORIGIN = 0x1b2d0, LENGTH = 0x1b8
         STATE (rw) : ORIGIN = 0x202f88a0, LENGTH = 0x100 }
SECTIONS {
 .text : { *(.text*) *(.rodata*) } > CODE
 .ARM.exidx : { *(.ARM.exidx*) } > CODE
 .data : { *(.data*) } > STATE
 .bss (NOLOAD) : { *(.bss*) *(COMMON) } > STATE
 /DISCARD/ : { *(.comment*) *(.ARM.attributes*) }
}
ASSERT(SIZEOF(.data)==0,"Unexpected initialized data")
