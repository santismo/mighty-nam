ENTRY(mpp_loop_startup)
MEMORY {
 BOOT (rx) : ORIGIN = 0x1d760, LENGTH = 0xd0
 CODE (rx) : ORIGIN = 0x20314020, LENGTH = 0x3fc0
 STATE (rw) : ORIGIN = 0x20318020, LENGTH = 0x1fc0
}
SECTIONS {
 .loop_startup : { *(.loop_startup*) } > BOOT
 .text : AT(0x303a0000) { __loop_code_start = .; *(.text*) *(.rodata*) . = ALIGN(4); __loop_code_end = .; } > CODE
 __loop_code_load = LOADADDR(.text);
 .data : { *(.data*) } > STATE
 .bss (NOLOAD) : { __loop_bss_start = .; *(.bss*) *(COMMON) . = ALIGN(4); __loop_bss_end = .; } > STATE
 /DISCARD/ : { *(.ARM.exidx*) *(.ARM.extab*) *(.comment*) }
}
ASSERT(SIZEOF(.data)==0,"Initialized loop globals require explicit startup support")
ASSERT(SIZEOF(.text)<=0x4000,"Loop code overlaps global settings storage")
