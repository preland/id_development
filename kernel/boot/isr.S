/* Interrupt stubs.
 *
 * An interrupt handler cannot be an `id` function. The CPU enters it with a
 * frame `id` has no way to name, it must leave with `iretq` rather than `ret`,
 * and half the vectors push an error code and half do not -- so the entry
 * point is assembly whose only job is to make every vector look the same and
 * then call something that can be written in `id`.
 *
 * That something is `kpanic`, which is an ordinary `id` function taking three
 * `word`s. Everything a fault report needs to say -- which fault, what the
 * error code was, where it happened -- it says from there, in the language,
 * through the same serial console the rest of the kernel uses.
 *
 * `isr_table` is the array of stub addresses, which is how the `id` side fills
 * the descriptor table without needing a symbol per vector: it takes the base
 * address once and reads the rest with peek64.
 */

.section .text

/* The vectors that push an error code, per the SDM: 8, 10-14, 17, 21, 29, 30.
   Every other one gets a zero pushed in its place, so the frame below the
   vector number is the same shape whichever way we got here. */
.macro ISR_NOERR n
isr\n:
    pushq $0
    pushq $\n
    jmp isr_common
.endm

.macro ISR_ERR n
isr\n:
    pushq $\n
    jmp isr_common
.endm

ISR_NOERR 0
ISR_NOERR 1
ISR_NOERR 2
ISR_NOERR 3
ISR_NOERR 4
ISR_NOERR 5
ISR_NOERR 6
ISR_NOERR 7
ISR_ERR   8
ISR_NOERR 9
ISR_ERR   10
ISR_ERR   11
ISR_ERR   12
ISR_ERR   13
ISR_ERR   14
ISR_NOERR 15
ISR_NOERR 16
ISR_ERR   17
ISR_NOERR 18
ISR_NOERR 19
ISR_NOERR 20
ISR_ERR   21
ISR_NOERR 22
ISR_NOERR 23
ISR_NOERR 24
ISR_NOERR 25
ISR_NOERR 26
ISR_NOERR 27
ISR_NOERR 28
ISR_ERR   29
ISR_ERR   30
ISR_NOERR 31

/* Stack here: vector, error code, then the frame the CPU pushed -- rip, cs,
   rflags, rsp, ss. The three arguments are read out before anything is
   aligned, because aligning moves rsp and the offsets with it. Nothing
   returns, so no register is saved: a fault report is the end of the run. */
isr_common:
    movq 0(%rsp), %rdi          /* vector */
    movq 8(%rsp), %rsi          /* error code */
    movq 16(%rsp), %rdx         /* rip */
    andq $-16, %rsp             /* the ABI wants 16-byte alignment at a call */
    call id_kpanic
1:  cli
    hlt
    jmp 1b

.section .rodata
.align 8
.global isr_table
isr_table:
    .quad isr0,  isr1,  isr2,  isr3,  isr4,  isr5,  isr6,  isr7
    .quad isr8,  isr9,  isr10, isr11, isr12, isr13, isr14, isr15
    .quad isr16, isr17, isr18, isr19, isr20, isr21, isr22, isr23
    .quad isr24, isr25, isr26, isr27, isr28, isr29, isr30, isr31
