#!/bin/sh
# Builds payload.bin (flat image linked at TP_BASE) + payload.sym (symbol offsets) with devkitPPC.
set -e
cd "$(dirname "$0")"
BASE=${1:-0x80003200}
GCC=${DEVKITPPC:-/opt/devkitpro/devkitPPC}/bin/powerpc-eabi
${GCC}-gcc -mcpu=750 -Os -ffreestanding -nostdlib -fno-pic -msdata=none -mno-eabi -fno-asynchronous-unwind-tables \
  -Wall -Wextra -c taiko_pad.c -o taiko_pad.o
${GCC}-ld -T payload.ld --defsym=TP_BASE=$BASE -o taiko_pad.elf taiko_pad.o
${GCC}-objcopy -O binary taiko_pad.elf payload.bin
${GCC}-nm taiko_pad.elf | awk '{print $3, $1}' | grep -E '^(tp_|TP_)' > payload.sym
echo "built payload.bin ($(wc -c < payload.bin) bytes) at $BASE"
cat payload.sym
