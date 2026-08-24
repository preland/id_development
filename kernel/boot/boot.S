/* The boot stub: multiboot2 header, and the walk from where a 32-bit
 * bootloader leaves the machine to where compiled `id` can run.
 *
 * This is assembly and not `id`, and it always will be. Every instruction here
 * either cannot be a function call (a far jump between CPU modes) or has to run
 * before a stack exists. Nothing about it is a C runtime: it sets up paging and
 * a stack and jumps to id_main, and there is no libc anywhere in the program.
 *
 * The boot protocol is PVH, declared by an ELF note. QEMU's -kernel takes a
 * 64-bit ELF that way and enters at `start` in 32-bit protected mode with
 * paging off; its Multiboot support is Multiboot 1 and ELF32 only, which a
 * kernel holding 64-bit code cannot be. A multiboot2 header is here as well so
 * that a real bootloader can load the same image.
 *
 * From there the steps are the usual ones: a stack, an identity map of the
 * first gigabyte with 2 MiB pages, PAE on, long mode enabled in EFER, paging
 * on, a GDT with a 64-bit code segment, and a far jump into it.
 */

/* The PVH entry point, as an ELF note: name "Xen", type
   XEN_ELFNOTE_PHYS32_ENTRY, and a 32-bit address to start at. */
.section .note.Xen, "a"
.align 4
    .long 4
    .long 4
    .long 18
    .asciz "Xen"
.align 4
    .long start
.align 4

.set MB2_MAGIC,    0xE85250D6
.set MB2_ARCH,     0
.set MB2_LEN,      (mb2_end - mb2_start)
.set MB2_CHECK,    -(MB2_MAGIC + MB2_ARCH + MB2_LEN)

.section .multiboot, "a"
.align 8
mb2_start:
    .long MB2_MAGIC
    .long MB2_ARCH
    .long MB2_LEN
    .long MB2_CHECK
    /* end tag */
    .short 0
    .short 0
    .long 8
mb2_end:

.section .bss, "aw", @nobits
.align 4096
pml4:   .skip 4096
pdpt:   .skip 4096
/* Four page directories, because four gigabytes have to be mapped rather than
   one: the framebuffer a PCI device exposes sits far above the first, and a
   pixel written to an address with no page behind it is a page fault rather
   than a pixel. */
pd:     .skip 4096 * 4
.align 16
stack_bottom:
    .skip 65536
stack_top:

.section .rodata
gdt64:
    .quad 0                                  /* null */
gdt64_code = . - gdt64
    .quad (1<<43) | (1<<44) | (1<<47) | (1<<53)   /* code, present, 64-bit */
gdt64_ptr:
    .short . - gdt64 - 1
    .quad gdt64

.section .text
.code32
.global start
start:
    movl $stack_top, %esp

    /* pml4[0] -> pdpt, pdpt[0] -> pd, and pd[i] -> a 2 MiB identity page */
    movl $pdpt, %eax
    orl  $0x3, %eax
    movl %eax, pml4

    /* pdpt[0..3] -> the four page directories */
    xorl %ecx, %ecx
2:  movl $4096, %eax
    mul  %ecx
    addl $pd, %eax
    orl  $0x3, %eax
    movl %eax, pdpt(,%ecx,8)
    movl $0, pdpt+4(,%ecx,8)
    incl %ecx
    cmpl $4, %ecx
    jne  2b

    /* and 2048 two-megabyte pages, identity mapped: four gigabytes */
    xorl %ecx, %ecx
1:  movl $0x200000, %eax
    mul  %ecx                    /* edx:eax = 2MiB * ecx */
    orl  $0x83, %eax             /* present, writable, 2 MiB page */
    movl %eax, pd(,%ecx,8)
    movl %edx, pd+4(,%ecx,8)
    incl %ecx
    cmpl $2048, %ecx
    jne  1b

    /* PAE */
    movl %cr4, %eax
    orl  $(1<<5), %eax
    movl %eax, %cr4

    movl $pml4, %eax
    movl %eax, %cr3

    /* EFER.LME */
    movl $0xC0000080, %ecx
    rdmsr
    orl  $(1<<8), %eax
    wrmsr

    /* paging + protection */
    movl %cr0, %eax
    orl  $(1<<31), %eax
    movl %eax, %cr0

    lgdt gdt64_ptr
    ljmp $gdt64_code, $long_mode

.code64
long_mode:
    xorl %eax, %eax
    movw %ax, %ds
    movw %ax, %es
    movw %ax, %ss
    movw %ax, %fs
    movw %ax, %gs

    movq $stack_top, %rsp
    call id_main
hang:
    cli
    hlt
    jmp hang
