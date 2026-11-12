"""Bounded offline TLS emulation. Never launches WoW or calls host Windows APIs."""

import argparse
import hashlib
import json
from pathlib import Path
import struct
import time

import pefile
import unicorn as u
from unicorn import x86_const as x

try:
    from .audit_exe import TARGET_SHA256
except ImportError:
    from audit_exe import TARGET_SHA256


REGISTERS = (
    (x.UC_X86_REG_RAX, 0x78), (x.UC_X86_REG_RCX, 0x80), (x.UC_X86_REG_RDX, 0x88),
    (x.UC_X86_REG_RBX, 0x90), (x.UC_X86_REG_RSP, 0x98), (x.UC_X86_REG_RBP, 0xA0),
    (x.UC_X86_REG_RSI, 0xA8), (x.UC_X86_REG_RDI, 0xB0), (x.UC_X86_REG_R8, 0xB8),
    (x.UC_X86_REG_R9, 0xC0), (x.UC_X86_REG_R10, 0xC8), (x.UC_X86_REG_R11, 0xD0),
    (x.UC_X86_REG_R12, 0xD8), (x.UC_X86_REG_R13, 0xE0), (x.UC_X86_REG_R14, 0xE8),
    (x.UC_X86_REG_R15, 0xF0), (x.UC_X86_REG_RIP, 0xF8),
)


def qword(uc, address, value):
    uc.mem_write(address, struct.pack("<Q", value))


def read_qword(uc, address):
    return struct.unpack("<Q", uc.mem_read(address, 8))[0]


def save_context(uc, address, fault):
    uc.mem_write(address, bytes(0x4D0))
    for register, offset in REGISTERS:
        qword(uc, address + offset, uc.reg_read(register))
    qword(uc, address + 0xF8, fault)
    uc.mem_write(address + 0x30, struct.pack("<I", 0x100003))
    uc.mem_write(address + 0x44, struct.pack("<I", uc.reg_read(x.UC_X86_REG_EFLAGS)))


def restore_context(uc, address):
    for register, offset in REGISTERS:
        uc.reg_write(register, read_qword(uc, address + offset))
    uc.reg_write(x.UC_X86_REG_EFLAGS, struct.unpack("<I", uc.mem_read(address + 0x44, 4))[0])


def probe(data, system_directory, max_exceptions=256, seconds=20):
    digest = hashlib.sha256(data).hexdigest()
    if digest != TARGET_SHA256:
        raise ValueError("Unsupported executable SHA-256")
    if not 0 <= max_exceptions <= 10000 or not 1 <= seconds <= 60:
        raise ValueError("Expected 0..10000 exceptions and 1..60 seconds")
    pe = pefile.PE(data=data, fast_load=True)
    modules = []
    try:
        pe.parse_data_directories(directories=[pefile.DIRECTORY_ENTRY["IMAGE_DIRECTORY_ENTRY_TLS"]])
        base, image_size = pe.OPTIONAL_HEADER.ImageBase, pe.OPTIONAL_HEADER.SizeOfImage
        callbacks = pe.DIRECTORY_ENTRY_TLS.struct.AddressOfCallBacks
        if not base <= callbacks < base + image_size - 256:
            raise ValueError("TLS callback array outside mapped image")
        uc = u.Uc(u.UC_ARCH_X86, u.UC_MODE_64)
        uc.mem_map(base, image_size)
        uc.mem_write(base, pe.get_memory_mapped_image())
        stack, env, stop = 0x10000000, 0x70000000, 0x50000000
        uc.mem_map(stack, 0x100000)
        uc.mem_map(env, 0x10000)
        uc.mem_map(stop, 0x1000)
        exports, identities = {}, []
        modules.append(("Wow.exe", base, pe))
        for index, name in enumerate(("ntdll.dll", "kernel32.dll", "kernelbase.dll")):
            source = (Path(system_directory) / name).read_bytes()
            module = pefile.PE(data=source, fast_load=True)
            modules.append((name, 0x200000000 + index * 0x10000000, module))
            if module.FILE_HEADER.Machine != 0x8664:
                raise ValueError("System module must be x64: " + name)
            module.parse_data_directories(directories=[0])
            module_base = modules[-1][1]
            uc.mem_map(module_base, (module.OPTIONAL_HEADER.SizeOfImage + 4095) & ~4095)
            # Mapped only for export metadata; hooks stop before executing system code.
            uc.mem_write(module_base, module.get_memory_mapped_image())
            identities.append(dict(name=name, sha256=hashlib.sha256(source).hexdigest()))
            for symbol in module.DIRECTORY_ENTRY_EXPORT.symbols:
                exports.setdefault(module_base + symbol.address, (name, symbol))
        teb, peb, ldr, entry = env, env + 0x1000, env + 0x2000, env + 0x3000
        for address, value in ((teb + 0x60, peb), (teb + 0x30, teb),
                               (teb + 8, stack + 0x100000), (teb + 0x10, stack),
                               (peb + 0x10, base), (peb + 0x18, ldr), (ldr + 0x20, entry + 0x10)):
            qword(uc, address, value)
        for index, (name, address, module) in enumerate(modules):
            item = entry + index * 0x100
            qword(uc, item + 0x10, entry + (index + 1) * 0x100 + 0x10
                  if index + 1 < len(modules) else ldr + 0x20)
            qword(uc, item + 0x18, entry + (index - 1) * 0x100 + 0x10 if index else ldr + 0x20)
            qword(uc, item + 0x30, address)
            uc.mem_write(item + 0x40, struct.pack("<I", module.OPTIONAL_HEADER.SizeOfImage))
            text, buffer = name.encode("utf-16-le"), env + 0x4000 + index * 0x100
            uc.mem_write(buffer, text)
            uc.mem_write(item + 0x58, struct.pack("<HHIQ", len(text), len(text) + 2, 0, buffer))
        uc.reg_write(x.UC_X86_REG_GS_BASE, teb)
        result = dict(schema=1, sha256=digest, system_modules=identities, unicorn_version=u.__version__,
                      api_events=[], callbacks=[], exceptions=[], stop_reason="not started",
                      limitations=["Synthetic Windows loader environment; not a game launch.",
                                   "Only VirtualProtect success and VEH registration are modeled.",
                                   "Exception CONTEXT preserves integer registers and flags only.",
                                   "System-module bytes are export metadata and are never executed.",
                                   "No decrypted image, model hook or callable engine ABI is established."])
        state = dict(handler=None, blocked=None)

        def external(uc, address, size, user):
            if address == stop:
                uc.emu_stop()
                return
            found = exports.get(address)
            if not found:
                state["blocked"] = "unrecognized system code address"
                uc.emu_stop()
                return
            dll, symbol = found
            name = symbol.name.decode("ascii") if symbol.name else "ordinal:" + str(symbol.ordinal)
            arguments = [uc.reg_read(reg) for reg in
                         (x.UC_X86_REG_RCX, x.UC_X86_REG_RDX, x.UC_X86_REG_R8, x.UC_X86_REG_R9)]
            result["api_events"].append(dict(dll=dll, name=name, arguments=arguments))
            if symbol.forwarder or name not in ("VirtualProtect", "RtlAddVectoredExceptionHandler"):
                state["blocked"] = "unmodeled system API: " + dll + "!" + name
                uc.emu_stop()
                return
            if name == "VirtualProtect":
                # Memory permissions are synthetic; no host API call is made.
                uc.mem_write(arguments[3], struct.pack("<I", 0x20))
            else:
                if not base <= arguments[1] < base + image_size:
                    state["blocked"] = "exception handler outside target"
                    uc.emu_stop()
                    return
                state["handler"] = arguments[1]
                result["handler_rva"] = arguments[1] - base
            rsp = uc.reg_read(x.UC_X86_REG_RSP)
            uc.reg_write(x.UC_X86_REG_RAX, 1)
            uc.reg_write(x.UC_X86_REG_RIP, read_qword(uc, rsp))
            uc.reg_write(x.UC_X86_REG_RSP, rsp + 8)

        uc.hook_add(u.UC_HOOK_CODE, external, begin=stop, end=stop)
        for _, address, module in modules[1:]:
            uc.hook_add(u.UC_HOOK_CODE, external, begin=address,
                        end=address + module.OPTIONAL_HEADER.SizeOfImage - 1)
        deadline = time.monotonic() + seconds

        def run(address):
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return "wall-clock limit"
            try:
                uc.emu_start(address, stop, timeout=max(1, int(remaining * 1000000)), count=10000000)
            except u.UcError as error:
                return "emulator: " + str(error)
            return state["blocked"] or ("returned" if uc.reg_read(x.UC_X86_REG_RIP) == stop
                                        else "instruction/time limit or halted instruction")

        initial = []
        for index in range(32):
            address = read_qword(uc, callbacks + index * 8)
            if not address:
                break
            initial.append(address - base)
        result["initial_callback_rvas"] = initial
        for index in range(32):
            address = read_qword(uc, callbacks + index * 8)
            if not address:
                result["stop_reason"] = "TLS callback list completed in synthetic environment"
                break
            if not base <= address < base + image_size:
                result["stop_reason"] = "callback outside target"
                break
            result["callbacks"].append(dict(index=index, rva=address - base))
            uc.reg_write(x.UC_X86_REG_RSP, stack + 0xFF008)
            qword(uc, stack + 0xFF008, stop)
            for reg, value in ((x.UC_X86_REG_RCX, base), (x.UC_X86_REG_RDX, 1), (x.UC_X86_REG_R8, 0)):
                uc.reg_write(reg, value)
            reason = run(address)
            while uc.reg_read(x.UC_X86_REG_RIP) != stop and not state["blocked"]:
                rip, flags = uc.reg_read(x.UC_X86_REG_RIP), uc.reg_read(x.UC_X86_REG_EFLAGS)
                if time.monotonic() >= deadline:
                    reason = "wall-clock limit"
                    break
                if len(result["exceptions"]) >= max_exceptions:
                    reason = "exception limit"
                    break
                if not base < rip < base + image_size or not state["handler"]:
                    break
                if flags & 0x100:
                    code, fault = 0x80000004, rip
                elif bytes(uc.mem_read(rip - 1, 1)) == b"\xF4":
                    code, fault = 0xC0000096, rip - 1
                else:
                    break
                record, context, pointers = env + 0x8000, env + 0x9000, env + 0xA000
                uc.mem_write(record, bytes(0xA0))
                uc.mem_write(record, struct.pack("<I", code))
                qword(uc, record + 0x10, fault)
                save_context(uc, context, fault)
                qword(uc, pointers, record)
                qword(uc, pointers + 8, context)
                uc.reg_write(x.UC_X86_REG_RSP, stack + 0x80008)
                qword(uc, stack + 0x80008, stop)
                uc.reg_write(x.UC_X86_REG_RCX, pointers)
                uc.reg_write(x.UC_X86_REG_EFLAGS, 0x202)
                reason = run(state["handler"])
                accepted = (uc.reg_read(x.UC_X86_REG_RIP) == stop
                            and uc.reg_read(x.UC_X86_REG_RAX) & 0xFFFFFFFF == 0xFFFFFFFF)
                result["exceptions"].append(dict(code=code, fault_rva=fault - base, handled=accepted))
                if not accepted:
                    reason = "handler did not return EXCEPTION_CONTINUE_EXECUTION: " + reason
                    break
                restore_context(uc, context)
                reason = run(uc.reg_read(x.UC_X86_REG_RIP))
            result["callbacks"][-1]["result"] = reason
            result["stop_reason"] = reason
            if reason != "returned":
                break
        result["final_callback_rvas"] = []
        for index in range(32):
            address = read_qword(uc, callbacks + index * 8)
            if not address:
                break
            result["final_callback_rvas"].append(address - base)
        rip = uc.reg_read(x.UC_X86_REG_RIP)
        result["stop_rva"] = rip - base if base <= rip < base + image_size else None
        return result
    finally:
        for _, _, module in modules:
            if module is not pe:
                module.close()
        pe.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("executable", type=Path)
    parser.add_argument("--system-directory", type=Path, default=Path("C:/Windows/System32"))
    parser.add_argument("--max-exceptions", type=int, default=256)
    parser.add_argument("--seconds", type=int, default=20)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        report = probe(args.executable.read_bytes(), args.system_directory, args.max_exceptions, args.seconds)
        with args.output.open("x", encoding="utf-8") as stream:
            json.dump(report, stream, indent=2)
            stream.write("\n")
        print(report["stop_reason"])
    except (OSError, ValueError, pefile.PEFormatError, u.UcError) as error:
        parser.exit(1, str(error) + "\n")


if __name__ == "__main__":
    main()
