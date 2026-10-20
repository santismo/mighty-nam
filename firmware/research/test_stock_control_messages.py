"""Run saved stock control messages against the exact installed NAMLNK01 ELF.
Only a CPU emulator and saved files. No physical MIDI, audio or flash writer.
"""
import argparse, json, struct, hashlib
from pathlib import Path
import candidate_vm as v
from test_link_firmware import LinkMachine
from link_image import build
from unicorn.arm_const import UC_ARM_REG_PC, UC_ARM_REG_LR
from unicorn import UC_PROT_READ

parser = argparse.ArgumentParser(description=__doc__)
for name in ["payload", "elf", "output"]: parser.add_argument(name, type=Path)
args = parser.parse_args()
stock, elf = args.payload, args.elf
v.configure(stock, True, candidate_bundle=build(stock.read_bytes(), elf))

class ControlMachine(LinkMachine):
    def code(self, u, pc, size, unused):
        if self.phase == "probe":
            if pc in {0xbfa4, 0xc0b0, 0xc034, 0xba50}:
                raise AssertionError(f"Persistent-write entry reached: {pc:#x}")
            if pc == 0xae80:
                data, n, channel = [u.reg_read(r) for r in v.R[:3]]
                assert 1 <= n <= 256
                self.messages.append((bytes(u.mem_read(data, n)), channel))
                u.reg_write(UC_ARM_REG_PC, u.reg_read(UC_ARM_REG_LR))
                return
            if pc in {0xbbcc, 0xbc00}:
                # Actual MIDI notifications terminate at the simulated transport.
                u.reg_write(UC_ARM_REG_PC, u.reg_read(UC_ARM_REG_LR))
                return
        super().code(u, pc, size, unused)

m = ControlMachine()
# Include stock control descriptors/default presets, not only DSP initialization.
m.u.mem_map(0x30040000, (len(v.stock)+4095)&~4095, UC_PROT_READ)
m.u.mem_write(0x30040000, v.candidate)
m.stubs.difference_update({0x10b08, 0xb198})
m.boot(unity_fades=False)
m.phase = "probe"
m.run(0xb974)
cases = []
def send(label, data):
    state = bytes(m.u.mem_read(v.state_start, v.state_end-v.state_start))
    result = m.ingress([bytes(data)], channel=0)
    if data[0] == 176:
        # CC ingress queues values; the ordinary foreground service applies them.
        m.run(0xb954)
    assert bytes(m.u.mem_read(v.state_start, v.state_end-v.state_start)) == state
    m.guards()
    row = {"name":label, "sent":bytes(data).hex(),
           "replies":[{"bytes":reply.hex(),"channel":ch} for reply,ch in result],
           "preset":bytes(m.u.mem_read(m.preset,128)).hex()}
    cases.append(row)
    print(json.dumps(row), flush=True)

send("current preset", [240,67,88,112,12,2,247])
send("read order", [240,67,88,112,13,2,247])
send("drive bypass type 5", [176,2,0x45])
assert m.u.mem_read(m.preset+2,1) == b'\x45'
send("drive tone", [176,18,37])
assert m.u.mem_read(m.preset+21,1) == b'\x25'
send("cab type 10", [176,9,10])
assert m.u.mem_read(m.preset+9,1) == b'\x0a'
send("EQ bypass", [176,4,0x42])
assert m.u.mem_read(m.preset+4,1) == b'\x42'
send("order", [240,67,88,112,13,1,9,5,3,1,2,9,4,6,8,7,247])
send("current preset after", [240,67,88,112,12,2,247])
assert bytes(m.u.mem_read(m.preset+90,9)) == bytes([5,3,1,2,9,4,6,8,7])
args.output.write_text(json.dumps({
    "status":"PASS_CPU_ONLY_STOCK_COMMANDS", "elf_sha256":hashlib.sha256(elf.read_bytes()).hexdigest(),
    "cases":cases, "physical_device_access":False,
    "audio_processing_chain_exercised":False}, indent=2)+"\n")
