"""Offline stock delay/reverb sleep-and-reset experiment, never a release.

The proposed sleep/reset policy is driven by Python. All DSP, type-change
fades, overlay loads and history clears execute the saved ARM firmware.
This deliberately does not claim a compiled hook, audible quality, cycle
budget or preserved spillover. No USB or host audio API is used.
"""
import argparse, hashlib, json, math, struct, time
from pathlib import Path
from unicorn import UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2
from test_preset_runtime import PresetMachine, build, preset_fixture, v

L, R, OL, OR = 0x20032000, 0x20032040, 0x20032080, 0x200320c0
GROUPS = {7: (0x20003a08, 0x2c, 0x12c48, 0x12d6a, 5),
          8: (0x200041d8, 0x28, 0x12eb2, 0x12fd8, 6)}


def snapshot(m):
    return m.u.context_save(), [(base, bytes(m.u.mem_read(base, size))) for base, size in
        [(0x20000000, 0x40000), (0x20200000, 0x140000), (0x24000, 0x1c000)]]


def restore(m, saved):
    context, memory = saved
    for base, blob in memory: m.u.mem_write(base, blob)
    m.u.context_restore(context)
    m.u.ctl_remove_cache(0x24000, 0x40000)


def run(m, entry, xs, stereo=True):
    m.floats(L, xs); m.floats(R, [-x * .7 for x in xs] if stereo else xs)
    m.floats(OL, [1234.5] * 8); m.floats(OR, [-1234.5] * 8)
    m.call(entry, [L, R, OL, OR]); ys = m.read(OL) + m.read(OR)
    assert all(math.isfinite(x) and abs(x) < 100 for x in ys), 'Invalid DSP output'
    return ys


def signal(block):
    return [.08 * math.sin(2 * math.pi * 110 * (block * 8 + i) / 48000)
            + .03 * math.sin(2 * math.pi * 659.25 * (block * 8 + i) / 48000) for i in range(8)]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ['payload', 'elf', 'model', 'report']: p.add_argument(name, type=Path)
    p.add_argument('--stage', type=int, choices=[7, 8], nargs='+', default=[7, 8])
    p.add_argument('--types', type=int, nargs='+')
    a = p.parse_args(); started = time.monotonic()
    v.configure(a.payload, True, candidate_bundle=build(a.payload.read_bytes(), a.elf)); v.elf_path = a.elf
    rows = []
    for stage in a.stage:
        base, request, callback, loader, maximum = GROUPS[stage]
        for typ in a.types or range(1, maximum + 1):
            assert 1 <= typ <= maximum
            for setting in ('ordinary', 'long'):
                m = PresetMachine(path=a.model); m.arm()
                data = preset_fixture([stage], {stage: typ}); data[3] |= 64
                data[61:65] = bytes([50, 45, 50, 40] if setting == 'ordinary' else [90, 85, 90, 85])
                data[70:74] = bytes([40, 35, 40, 35] if setting == 'ordinary' else [85, 85, 85, 85])
                m.u.mem_write(m.preset, bytes(data))
                for i in range(300): m.process(i, [0.] * 8)
                assert bytes(m.u.mem_read(base, 2)) == bytes([typ, typ]), ('Type not loaded', stage, typ)
                for i in range(6000): run(m, callback, signal(i))
                data[stage] |= 64; m.u.mem_write(m.preset, bytes(data))
                residual = 0.
                for i in range(1200):
                    xs = signal(6000+i); ys = run(m, callback, xs)
                    if i >= 1168:
                        dry = list(struct.unpack('<8f', struct.pack('<8f', *xs)))
                        right = list(struct.unpack('<8f', struct.pack('<8f', *[-x*.7 for x in xs])))
                        residual = max(residual, max(abs(x-y) for x,y in zip(ys,dry+right)))
                saved = snapshot(m)
                data[stage] &= 63; m.u.mem_write(m.preset, bytes(data))
                frozen = []
                for i in range(1500): frozen += run(m, callback, [0.] * 8)
                restore(m, saved); m.u.mem_write(m.preset, bytes(data))
                # Reuse the original asynchronous type-change handshake.
                # desired=current type, current=0 (invalid sentinel), fade
                # completed, loader idle. First callback outputs dry and queues
                # a reload; the real foreground loader clears and initializes.
                m.u.mem_write(base, bytes([typ, 0])); m.put(base+0xc, 127); m.put(base+request, 0)
                pending = run(m, callback, [0.] * 8)
                assert m.get(base+request) == 1 and pending == [0.] * 16
                operations = []
                def memory_op(u, pc, size, _):
                    operations.append(dict(pc=hex(pc),destination=hex(u.reg_read(UC_ARM_REG_R0)),
                        bytes=u.reg_read(UC_ARM_REG_R1 if pc==0x5530 else UC_ARM_REG_R2)))
                hooks = [m.u.hook_add(UC_HOOK_CODE, memory_op, begin=x, end=x) for x in (0x5530, 0x5488)]
                m.call(loader, [])
                for h in hooks: m.u.hook_del(h)
                assert m.get(base+request) == 2
                assert any(x['pc']=='0x5530' and x['bytes']==0x40000 for x in operations)
                reset = []
                for i in range(1500): reset += run(m, callback, [0.] * 8)
                assert bytes(m.u.mem_read(base, 2)) == bytes([typ, typ])
                peak = max(map(abs, reset))
                settled_peak = max(map(abs, reset[1200*16:]))
                # New guitar input must still produce a nonzero finite output.
                response = []
                for i in range(300): response += run(m, callback, signal(i))
                assert max(map(abs, response)) > 1e-3
                m.guards(); assert not m.words()[4]
                rows.append(dict(stage=stage,type=typ,setting=setting,
                    output_residual_at_200ms=residual,
                    naive_frozen_wake_peak=max(map(abs,frozen)),
                    reset_wake_silence_peak=peak,reset_wake_after_200ms_peak=settled_peak,
                    quiet_after_existing_settling=settled_peak<=1e-6,
                    new_input_peak=max(map(abs,response)),
                    foreground_memory_operations=operations,
                    actual_type_loaded=True,guards_pass=True))
                print(json.dumps({k:v for k,v in rows[-1].items() if k!='foreground_memory_operations'}),flush=True)
                a.report.write_text(json.dumps(dict(status='IN_PROGRESS',cases=rows),indent=2)+'\n')
    result=dict(status='COMPLETE_OFFLINE_TAIL_RESET_SCREEN',cases=rows,seconds=time.monotonic()-started,
        all_fixtures_quiet_after_settling=all(x['quiet_after_existing_settling'] for x in rows),
        elf_sha256=hashlib.sha256(a.elf.read_bytes()).hexdigest(),
        stock_sha256=hashlib.sha256(a.payload.read_bytes()).hexdigest(),
        model_sha256=hashlib.sha256(a.model.read_bytes()).hexdigest(),
        device_access=False,host_audio_access=False,firmware_changed=False,
        limitations=['Python drives the proposed policy; no compiled dispatcher change.',
          'Explicit hard-bypass/reset semantics: tails are discarded, not preserved spillover.',
          'Only the listed parameter fixtures, finite input and 250 ms wake windows.',
          'Reset clears 256 KiB and copies overlays in foreground; hardware load/clicks unmeasured.',
          'Gate not included; no claim of fixed latency reduction or measured CPU speedup.'])
    a.report.write_text(json.dumps(result,indent=2)+'\n')


if __name__ == '__main__': main()
