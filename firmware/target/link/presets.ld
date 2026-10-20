ENTRY(mpp_stock_amp_init)
EXTERN(mpp_probe_audio mpp_probe_version mpp_probe_query mpp_stock_amp_process mpp_stock_preset_select mpp_bank_service)
MEMORY {
 CODE (rx) : ORIGIN = 0x1a0a4, LENGTH = 0x13e4
 AUDIO_BODY (rx) : ORIGIN = 0x14c04, LENGTH = 0x304
 STATE (rw) : ORIGIN = 0x202e4020, LENGTH = 0x23fe0
 BANKCODE (rx) : ORIGIN = 0x20308000, LENGTH = 0xc000
}
SECTIONS {
 .banktext : AT(0x303a0000) {
  __bank_start = .;
  *(.banktext*)
  *preset_bank.o(.text* .rodata*)
  *preset_runtime.o(.text* .rodata*)
  *effect_profiler.o(.text* .rodata*)
  . = ALIGN(4); __bank_end = .;
 } > BANKCODE
 __bank_load = LOADADDR(.banktext);
 .retired_audio : { *(.retired_audio*) } > AUDIO_BODY
 .text : { *(.text*) *(.rodata*) } > CODE
 .ARM.exidx : { *(.ARM.exidx*) } > AUDIO_BODY
 .data : { *(.data*) } > STATE
 .bss (NOLOAD) : { *(.bss*) *(COMMON) } > STATE
 /DISCARD/ : { *(.comment*) *(.ARM.attributes*) }
}
ASSERT(SIZEOF(.data)==0,"No hidden initialized data")
ASSERT(SIZEOF(.bss)<=0x23fe0,"Preset state collides with copied code")
ASSERT(SIZEOF(.banktext)<=0xc000,"Preset code exceeds audited retired resource")
