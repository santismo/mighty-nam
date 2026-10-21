"""Execute NAMLNK17's actual startup call patch and stock I2C helpers offline.

The low-level I2C byte/ACK primitives use a register model. No USB/audio or
electrical validation. Failed reads execute the stock NACK path, rather than
pretending its always-zero return value proves a successful transaction.
"""
import argparse, hashlib, json, struct
from pathlib import Path
from unicorn import *
from unicorn.arm_const import *
from preset_image import build, SOURCE, FLASH

REGS = (UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3)
DEFAULTS = bytes.fromhex('37 ac 1c 03 22 82 30 30 30 30 00 55 00 00 18 18 18 18 04 05 0a')
EXPECTED = DEFAULTS[:10] + b'\x22' + DEFAULTS[11:]
STOP = 0x40000

class Startup:
    def __init__(self, image, symbols, plan, fill=0, failed_read=None, failed_write=None):
        self.u = u = Uc(UC_ARCH_ARM, UC_MODE_THUMB | UC_MODE_MCLASS)
        u.mem_map(0, 0x100000); u.mem_write(0, image[:0x100000])
        u.mem_protect(0, 0x100000, UC_PROT_READ | UC_PROT_EXEC)
        u.mem_map(0x20000000, 0x400000); u.mem_write(0x20000000, bytes([fill])*0x400000)
        u.mem_map(0x40000000, 0x1000000); u.mem_map(0xe0000000, 0x100000)
        self.symbols, self.plan, self.image = symbols, plan, image
        self.failed_read, self.failed_write = failed_read, failed_write
        self.registers = bytearray(DEFAULTS); self.calls = []; self.mmio = []; self.bus = []
        self.operation = None; self.codec_phase = False; self.high_code_executed = False
        u.hook_add(UC_HOOK_CODE, self.code)
        u.hook_add(UC_HOOK_MEM_WRITE, self.write, begin=0x40000000, end=0xffffffff)
        self.call(0x2025c)
        assert bytes(u.mem_read(0x20000284, 21)) == DEFAULTS

    def write(self, u, access, address, size, value, unused):
        self.mmio.append((address, size, value))

    def return_value(self, value=0):
        self.u.reg_write(UC_ARM_REG_R0, value)
        self.u.reg_write(UC_ARM_REG_PC, self.u.reg_read(UC_ARM_REG_LR))

    def code(self, u, pc, size, unused):
        if self.codec_phase and pc >= 0x20000000:
            self.high_code_executed = True
            raise AssertionError('Codec startup tried to execute uncopied bank code')
        if pc in (0xda34, 0xdb06):
            args = tuple(u.reg_read(r) for r in REGS)
            self.operation = ('write' if pc == 0xda34 else 'read', *args)
            self.calls.append(self.operation + (bytes(u.mem_read(args[2], args[3])).hex(),))
            self.bus = []
            return  # Execute the actual stock helper.
        if pc in (0xbe34, 0xd888, 0xd8c0, 0x87a0, 0xede4):
            self.return_value(); return
        if pc == 0xd972:
            self.bus.append(u.reg_read(UC_ARM_REG_R0) & 255)
            self.return_value(); return
        if pc == 0xd8e4:
            kind, device, reg, ptr, count = self.operation
            failed = self.failed_read if kind == 'read' else self.failed_write
            self.return_value(0 if reg == failed else 1); return
        if pc == 0xd9be:
            assert self.operation[0] == 'read'
            self.return_value(self.registers[self.operation[2]]); return
        if pc == 0xd8a4:
            kind, device, reg, ptr, count = self.operation
            if kind == 'write' and count and reg != self.failed_write:
                assert self.bus == [device, reg, u.mem_read(ptr, 1)[0]]
                self.registers[reg] = self.bus[2]
            self.return_value()

    def call(self, address, args=()):
        for reg, value in zip(REGS, args): self.u.reg_write(reg, value)
        self.u.reg_write(UC_ARM_REG_SP, 0x20080000); self.u.reg_write(UC_ARM_REG_LR, STOP | 1)
        self.u.emu_start(address | 1, STOP, count=5000000)
        assert self.u.reg_read(UC_ARM_REG_PC) == STOP, 'Instruction limit'
        return self.u.reg_read(UC_ARM_REG_R0)

    def codec(self):
        self.calls.clear(); self.mmio.clear(); self.codec_phase = True
        self.call(0x116c0); self.codec_phase = False
        assert len(self.calls) == 42
        assert [x[2] for x in self.calls[:21]] == list(range(21))
        assert [x[2] for x in self.calls[21:]] == list(range(21))
        return bytes(int(x[-1], 16) for x in self.calls[:21])

    def status(self):
        bank = self.plan['copied_code']; size = bank['bytes']
        self.u.mem_write(int(bank['destination'], 16), self.image[SOURCE-FLASH:SOURCE-FLASH+size])
        return self.call(self.symbols['mpp_codec_filter_page'])

    def audio_setup(self):
        self.mmio.clear(); self.call(0x10b68); self.call(0x11984)
        return self.mmio, bytes(self.u.mem_read(0x20016aa0, 128))

def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ['payload', 'baseline_build', 'candidate_build', 'report']: p.add_argument(name, type=Path)
    p.add_argument('--candidate-identity',choices=['NAMLNK17','NAMLNK18'],default='NAMLNK17')
    a = p.parse_args(); stock = a.payload.read_bytes()
    elf = a.candidate_build/'nam-link-offline.elf'
    image, symbols, plan = build(stock, elf)
    assert plan['identity'] == a.candidate_identity
    baseline_elf = a.baseline_build/'nam-link-offline.elf'
    assert hashlib.sha256(baseline_elf.read_bytes()).hexdigest() == '7d3b7475d30d0a61367b5ca1b569bd8d83116f530487bb4a89822eca76e1e0f1'
    baseline = build(stock, baseline_elf)
    changed = ['stock_chain_firmware.o'] + (['preset_runtime.o','listening.o'] if a.candidate_identity == 'NAMLNK18' else [])
    unchanged = [x.name for x in a.baseline_build.glob('*.o') if x.name not in changed]
    for name in unchanged: assert (a.baseline_build/name).read_bytes() == (a.candidate_build/name).read_bytes(), name
    rows = []
    for fill in (0, 0xa5, 0xff):
        original = Startup(*baseline, fill); assert original.codec() == DEFAULTS
        candidate = Startup(image, symbols, plan, fill); assert candidate.codec() == EXPECTED
        assert candidate.mmio == original.mmio
        assert bytes(candidate.u.mem_read(0x200002ae, 21)) == EXPECTED
        assert candidate.status() == 0xc10f220a
        assert candidate.audio_setup() == original.audio_setup()
        # Repeat initialization with retained custom RAM; still exactly one changed register.
        assert candidate.codec() == EXPECTED and candidate.status() == 0xc10f220a
        rows.append(dict(fill=fill, cold_and_warm=True, status='c10f220a'))
    failures = []
    for kind in ('read', 'write'):
        for reg in (10, 20):
            candidate = Startup(image, symbols, plan, failed_read=reg if kind=='read' else None,
                                failed_write=reg if kind=='write' else None)
            candidate.codec(); status = candidate.status()
            if kind == 'read': assert (status >> (8 if reg==10 else 0)) & 255 == 255
            if reg == 10: assert status != 0xc10f220a
            failures.append(dict(kind=kind, register=reg, status=hex(status)))
    # Wrong address, width, device and unexpected ADC bits must pass through untouched.
    c = Startup(image, symbols, plan); c.codec(); negatives = 0
    for device, reg, ptr, width, value in [(0x22,10,0x2000028e,1,0), (0x20,10,0x2000028f,1,0),
                                         (0x20,10,0x2000028e,0,0), (0x20,10,0x2000028e,1,1)]:
        c.u.mem_write(ptr, bytes([value])); c.call(symbols['mpp_codec_startup_write'], [device,reg,ptr,width])
        assert c.u.mem_read(ptr,1)[0] == value; negatives += 1
    # Query via the actual SysEx parser, and ensure ordinary amp init does not erase evidence.
    from test_preset_runtime import PresetMachine, v
    v.configure(a.payload, True, candidate_bundle=(image,symbols,plan)); v.elf_path=elf
    m=PresetMachine()
    m.put(symbols['mpp_codec_startup_seen'],0x434f4431)
    for address,value in [(0x2000028e,0x22),(0x200002b8,0x22),(0x200002c2,0x0a)]: m.u.mem_write(address,bytes([value]))
    m.call(symbols['mpp_stock_amp_init'],[])
    for channel in (0,1): assert m.page(117,channel)==(0,0xc10f220a)
    m.guards()
    report=dict(status='PASS_'+a.candidate_identity+'_CODEC_STARTUP',elf_sha256=hashlib.sha256(elf.read_bytes()).hexdigest(),
                baseline_elf_sha256=hashlib.sha256(baseline_elf.read_bytes()).hexdigest(), unchanged_objects=unchanged,
                changed_registers=[10], previous_value=0, new_value=34, cold_and_warm=rows, failed_transactions=failures,
                wrong_call_passthrough_cases=negatives, real_stock_I2C_helpers=True, startup_before_bank_copy=True,
                identical_codec_GPIO_SAI_DMA=True, cached_readback_survives_amp_init=True, status_page=117,
                read_only_protocol_both_channels=True, physical_codec_identification_verified=False,
                physical_latency_measured=False, device_access=False, host_audio_access=False,
                limits=['Byte primitives are a simulated I2C device; electrical ACK and silicon behavior need physical validation.',
                        'A failed write of a value already held by the model cannot be inferred from matching readback.'])
    a.report.write_text(json.dumps(report,indent=2)+'\n'); print(report['status'])

if __name__=='__main__': main()
