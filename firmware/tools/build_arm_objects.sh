#!/bin/sh
# Compile only. Does not link a firmware image, open USB, or invoke an updater.
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
COMPILER=${CXX_ARM:-clang++}
for SOURCE in src/engine.cpp target/audio_module.cpp target/board/audio_transport.cpp target/board/codec_control.cpp target/board/startup_memory.cpp; do
  NAME=$(basename "$SOURCE" .cpp)
  "$COMPILER" --target=arm-none-eabi -mcpu=cortex-m7 -mthumb -mfpu=fpv5-d16 -mfloat-abi=hard \
    -std=c++20 -O3 -ffreestanding -fno-exceptions -fno-rtti -fdata-sections -ffunction-sections \
    -I "$ROOT/include" -I "$ROOT/target" -c "$ROOT/$SOURCE" -o "$ROOT/artifacts/${NAME}_cortex_m7.o"
done
"$COMPILER" --target=arm-none-eabi -mcpu=cortex-m7 -mthumb -c "$ROOT/target/board/startup_thumb.S" -o "$ROOT/artifacts/startup_thumb_cortex_m7.o"
printf '%s\n' 'ARM relocatable objects built. Not bootable firmware; no USB access.'
