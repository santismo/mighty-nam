/* OFFLINE ONLY. Candidate device RAM; no flash load address or boot copy. */
ENTRY(mpp_loop_init)
MEMORY {
    LOOP_CODE (rx) : ORIGIN = 0x20314020, LENGTH = 0x3fc0
    LOOP_STATE (rw) : ORIGIN = 0x20318020, LENGTH = 0x1fc0
}
SECTIONS {
    .text : { *(.text*) *(.rodata*) } > LOOP_CODE
    .data : { *(.data*) } > LOOP_STATE
    .bss (NOLOAD) : { *(.bss*) *(COMMON) } > LOOP_STATE
    /DISCARD/ : { *(.ARM.exidx*) *(.ARM.extab*) *(.comment*) }
}
