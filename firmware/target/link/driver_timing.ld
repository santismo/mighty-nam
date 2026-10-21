ENTRY(mpp_stock_amp_init)
EXTERN(mpp_probe_audio mpp_probe_version mpp_probe_query mpp_stock_amp_process mpp_stock_preset_select mpp_bank_service)
MEMORY {
 CODE (rx) : ORIGIN = 0x1a0a4, LENGTH = 0x13e4
 AUDIO_BODY (rx) : ORIGIN = 0x14c04, LENGTH = 0x304
 STATE (rw) : ORIGIN = 0x202e4020, LENGTH = 0x2bfe0
 BANKCODE (rx) : ORIGIN = 0x20310000, LENGTH = 0x4000
}
SECTIONS {
 .banktext : AT(0x303a0000) {
  __bank_start = .;
  *(.banktext*)
  *cut_eq.o(.text* .rodata*)
  *cut_eq_runtime.o(.text* .rodata*)
  *fx_blocks.o(.text* .rodata*)
  *fx_runtime.o(.text* .rodata*)
  *reply_transport.o(.text* .rodata*)
  *preset_bank.o(.text* .rodata*)
  *global_buffer.o(.text* .rodata*)
  *preset_runtime.o(.text* .rodata*)
  *effect_profiler.o(.text* .rodata*)
  *tuner.o(.text* .rodata*)
  *(.driver_capture*)
  . = ALIGN(4); __bank_end = .;
 } > BANKCODE
 __bank_load = LOADADDR(.banktext);
 .retired_audio : { *(.retired_audio*) } > AUDIO_BODY
 .text : { *(.text*)
  . = 0x1b200; /* kernels at 0x1b200, exactly NAMLNK16/18 */
  *(.rodata*) *(.codec_startup) *(.driver_query*)
 } > CODE
 .ARM.exidx : { *(.ARM.exidx*) } > AUDIO_BODY
 .data : { *(.data*) } > STATE
 .bss (NOLOAD) : { *(.bss*) *(COMMON) } > STATE
 /DISCARD/ : { *(.comment*) *(.ARM.attributes*) }
}
ASSERT(SIZEOF(.data)==0,"No hidden initialized data")
ASSERT(SIZEOF(.bss)<=0x2bfe0,"Preset state collides with copied code")
ASSERT(SIZEOF(.banktext)<=0x4000,"Preset code exceeds audited retired resource")
