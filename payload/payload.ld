/* Link address is chosen by build.sh (-Wl,--defsym=TP_BASE=...) */
ENTRY(tp_probe_wrap)
SECTIONS
{
    . = TP_BASE;
    .text : { *(.text.stubs) *(.text .text.*) }
    .data : ALIGN(4) { *(.data .data.*) *(.rodata .rodata.*) *(.sdata .sdata.*) *(.bss .bss.* COMMON) }
    /DISCARD/ : { *(.comment) *(.eh_frame*) *(.note*) *(.gnu*) }
}
