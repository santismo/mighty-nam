/* OFFLINE LAB ONLY. Six retired AMP init/process pairs occupy this span in
   exact V1.5.6. See research/audit_reclaimed_code.py for bounded xref evidence.
   No use of the zero-filled payload tail. Physical loading is still unproven. */
ENTRY(mpp_stock_amp_process)
EXTERN(mpp_stock_amp_init)
MEMORY {
  RETIRED_AMP_CODE (rx) : ORIGIN = 0x0001a0a4, LENGTH = 0x13e4
  /* Leave the lower canary inside the retired AMP arena, not in a neighbor. */
  CANDIDATE_STATE (rw) : ORIGIN = 0x202e4020, LENGTH = 0x1fe0
}
SECTIONS {
  .text : { *(.text*) *(.rodata*) } > RETIRED_AMP_CODE
  .ARM.exidx : { *(.ARM.exidx*) } > RETIRED_AMP_CODE
  .data : { *(.data*) } > CANDIDATE_STATE
  .bss (NOLOAD) : { *(.bss*) *(COMMON) } > CANDIDATE_STATE
  /DISCARD/ : { *(.comment*) *(.ARM.attributes*) }
}
ASSERT(SIZEOF(.data)==0,"Candidate lab requires explicit reset; no copied .data")
ASSERT(SIZEOF(.bss)<=0x1fe0,"Candidate state exceeds reserved test window")
