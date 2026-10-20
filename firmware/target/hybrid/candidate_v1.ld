/* CANDIDATE ADDRESSES FOR OFFLINE EXPERIMENTS ONLY.
   ITCM gap: zero-filled bytes in the saved V1.5.6 payload.
   State: start of the stock amp's 0x38000-byte arena, retired by test patches.
   Loader copy bounds and exhaustive lifetime/ownership remain unproven.
   This is not a bootable or updater-ready image. */
ENTRY(mpp_stock_amp_process)
EXTERN(mpp_stock_amp_init)
MEMORY {
  CANDIDATE_CODE (rx) : ORIGIN = 0x00024000, LENGTH = 16K
  CANDIDATE_STATE (rw) : ORIGIN = 0x202e4000, LENGTH = 8K
}
SECTIONS {
  .text : { *(.text*) *(.rodata*) } > CANDIDATE_CODE
  .ARM.exidx : { *(.ARM.exidx*) } > CANDIDATE_CODE
  .data : { *(.data*) } > CANDIDATE_STATE
  .bss (NOLOAD) : { *(.bss*) *(COMMON) } > CANDIDATE_STATE
  /DISCARD/ : { *(.comment*) *(.ARM.attributes*) }
}
ASSERT(SIZEOF(.data)==0,"Candidate lab requires explicit reset; no copied .data")
ASSERT(SIZEOF(.bss)<=0x2000,"Candidate state exceeds reserved test window")
