/* Deliberately artificial emulator addresses. NOT a device RAM allocation. */
ENTRY(lp_init)
MEMORY {
    TEST_CODE (rx) : ORIGIN = 0x10000000, LENGTH = 64K
    TEST_STATE (rw) : ORIGIN = 0x21000000, LENGTH = 64K
}
SECTIONS {
    .text : { *(.text*) *(.rodata*) } > TEST_CODE
    .data : { *(.data*) } > TEST_STATE
    .bss (NOLOAD) : { *(.bss*) *(COMMON) } > TEST_STATE
    /DISCARD/ : { *(.ARM.exidx*) *(.ARM.extab*) *(.comment*) }
}
