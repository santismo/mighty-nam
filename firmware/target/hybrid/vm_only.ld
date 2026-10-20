/* Synthetic emulator addresses. NOT a physical Mighty Plug Pro memory map.
   This ELF has no vectors, startup, updater header, or device-loading path. */
ENTRY(mpp_hybrid_amp)
EXTERN(mpp_hybrid_reset)
MEMORY {
  VM_CODE (rx) : ORIGIN = 0x08000000, LENGTH = 64K
  VM_STATE (rw) : ORIGIN = 0x21000000, LENGTH = 64K
}
SECTIONS {
  .text : { *(.text*) *(.rodata*) } > VM_CODE
  .ARM.exidx : { *(.ARM.exidx*) } > VM_CODE
  .data : { *(.data*) } > VM_STATE
  .bss (NOLOAD) : { *(.bss*) *(COMMON) } > VM_STATE
  /DISCARD/ : { *(.comment*) *(.ARM.attributes*) }
}
