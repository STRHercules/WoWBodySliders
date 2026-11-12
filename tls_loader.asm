; Invoked from the original first TLS callback's epilogue, before it is rewritten.
option casemap:none
.code
PUBLIC TlsLoader
TlsLoader PROC
    pushfq
    push rax
    push rcx
    push rdx
    push rbx
    push rbp
    push rsi
    push rdi
    push r8
    push r9
    push r10
    push r11
    push r12
    push r13
    push r14
    push r15
    cld
    mov rax, rsp
    and rsp, -16
    sub rsp, 90h
    mov [rsp+80h], rax
    movdqu xmmword ptr [rsp+20h], xmm0
    movdqu xmmword ptr [rsp+30h], xmm1
    movdqu xmmword ptr [rsp+40h], xmm2
    movdqu xmmword ptr [rsp+50h], xmm3
    movdqu xmmword ptr [rsp+60h], xmm4
    movdqu xmmword ptr [rsp+70h], xmm5
    mov rax, gs:[60h]
    mov rax, [rax+18h]
    lea r13, [rax+20h]
    mov r14, [r13]
    mov r15d, 64
NextModule:
    cmp r14, r13
    je Done
    dec r15d
    jz Done
    cmp word ptr [r14+48h], 24
    jne AdvanceModule
    mov rsi, [r14+50h]
    lea rdi, KernelName
    mov ecx, 12
CompareModule:
    movzx eax, word ptr [rsi]
    or eax, 20h
    cmp ax, word ptr [rdi]
    jne AdvanceModule
    add rsi, 2
    add rdi, 2
    loop CompareModule
    mov rbx, [r14+20h]
    mov eax, [rbx+3Ch]
    mov r8d, [rbx+rax+88h]
    mov r9d, [rbx+rax+8Ch]
    test r8d, r8d
    jz Done
    add r9d, r8d
    lea rdx, [rbx+r8]
    mov ecx, [rdx+18h]
    mov r10d, [rdx+20h]
    add r10, rbx
    mov r11d, [rdx+24h]
    add r11, rbx
    mov ebp, [rdx+1Ch]
    add rbp, rbx
NextExport:
    test ecx, ecx
    jz Done
    dec ecx
    mov esi, [r10+rcx*4]
    add rsi, rbx
    lea rdi, ApiName
CompareExport:
    mov al, [rsi]
    cmp al, [rdi]
    jne NextExport
    inc rsi
    inc rdi
    test al, al
    jnz CompareExport
    movzx eax, word ptr [r11+rcx*2]
    mov eax, [rbp+rax*4]
    test eax, eax
    jz Done
    cmp eax, r8d
    jb CallLoader
    cmp eax, r9d
    jb Done
CallLoader:
    add rax, rbx
    lea rcx, DllName
    xor edx, edx
    mov r8d, 0A00h ; Application directory and System32.
    call rax
    jmp Done
AdvanceModule:
    mov r14, [r14]
    jmp NextModule
Done:
    movdqu xmm0, xmmword ptr [rsp+20h]
    movdqu xmm1, xmmword ptr [rsp+30h]
    movdqu xmm2, xmmword ptr [rsp+40h]
    movdqu xmm3, xmmword ptr [rsp+50h]
    movdqu xmm4, xmmword ptr [rsp+60h]
    movdqu xmm5, xmmword ptr [rsp+70h]
    mov rsp, [rsp+80h]
    pop r15
    pop r14
    pop r13
    pop r12
    pop r11
    pop r10
    pop r9
    pop r8
    pop rdi
    pop rsi
    pop rbp
    pop rbx
    pop rdx
    pop rcx
    pop rax
    popfq
    ; Original whole epilogue at RVA 4DBF, including its return.
    add rsp, 170h
    pop rbp
    ret
TlsLoader ENDP
KernelName dw 'k','e','r','n','e','l','3','2','.','d','l','l'
ApiName db 'LoadLibraryExW',0
DllName dw 'B','o','d','y','S','l','i','d','e','r','S','h','a','d','o','w','l','a','n','d','s','.','d','l','l',0
END
