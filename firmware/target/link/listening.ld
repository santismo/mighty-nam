ENTRY(mpp_stock_amp_init)
EXTERN(mpp_probe_audio mpp_probe_version mpp_probe_query mpp_stock_amp_process)
MEMORY {
 CODE (rx) : ORIGIN = 0x1a0a4, LENGTH = 0x13e4
 AUDIO_BODY (rx) : ORIGIN = 0x14c04, LENGTH = 0x304
 STATE (rw) : ORIGIN = 0x202e4020, LENGTH = 0x37fc0
}
SECTIONS {
 .retired_audio : { *(.retired_audio*) } > AUDIO_BODY
 .text : { *(.text*) *(.rodata*) } > CODE
 .ARM.exidx : { *(.ARM.exidx*) } > AUDIO_BODY
 .data : { *(.data*) } > STATE
 .bss (NOLOAD) : { *(.bss*) *(COMMON) } > STATE
 /DISCARD/ : { *(.comment*) *(.ARM.attributes*) }
}
ASSERT(SIZEOF(.data)==0,"No hidden initialized data")
ASSERT(SIZEOF(.bss)<=0x37fc0,"Receiver exceeds the retired amp arena")
