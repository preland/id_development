/* Where the pieces land. 1 MiB is where a multiboot loader puts a kernel and
   below it is real-mode and firmware territory. */
ENTRY(start)
PHDRS {
    text PT_LOAD FLAGS(7);
    note PT_NOTE FLAGS(4);
}
SECTIONS {
    . = 1M;
    /* The note has to be in a PT_NOTE segment, because that is where a loader
       looks for the entry point before it has loaded anything. */
    .note.Xen : { KEEP(*(.note.Xen)) } :text :note
    .boot   : { KEEP(*(.multiboot)) } :text
    .text   : { *(.text .text.*) } :text
    .rodata : { *(.rodata .rodata.*) } :text
    .data   : { *(.data .data.*) } :text
    .bss    : { *(COMMON) *(.bss .bss.*) } :text
    . = ALIGN(4096);
    /* Everything above the image is the arena the runtime hands out. The
       identity map covers the first gigabyte, so this is what bounds it. */
    heap_base = .;
    heap_limit = 0x40000000;
}
