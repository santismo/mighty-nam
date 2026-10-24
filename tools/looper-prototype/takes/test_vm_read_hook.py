"""Small Unicorn IT/load observer regression; synthetic Thumb code only."""
import json,struct
from unicorn import Uc,UcError,UC_ARCH_ARM,UC_MODE_THUMB,UC_HOOK_MEM_READ,UC_HOOK_MEM_WRITE
from unicorn.arm_const import UC_CPU_ARM_CORTEX_A15,UC_ARM_REG_LR,UC_ARM_REG_R0,UC_ARM_REG_R8
# ldr/cmp/iteee/mov/ldr/clz/lsr/bx, followed by a literal. The
# caller compares the result and loads a pointer. No stock code or devices.
allowed=bytes.fromhex('04488168022911bf0020c068b0fa80f040097047')
caller=bytes.fromhex('00280dd0dff8108098f80000')
store=bytes.fromhex("4ff440500221022911bf0020c160012000217047")
def trial(hook=None,code=allowed):
 u=Uc(UC_ARCH_ARM,UC_MODE_THUMB);u.ctl_set_cpu_model(UC_CPU_ARM_CORTEX_A15)
 u.mem_map(0x1000,0x4000);u.mem_write(0x1000,code+struct.pack('<I',0x3000))
 u.mem_write(0x1100,caller);u.mem_write(0x1118,struct.pack('<I',0x4000))
 u.mem_write(0x3008,struct.pack('<II',2,0));u.mem_write(0x4000,b'\x07')
 u.reg_write(UC_ARM_REG_R8,0x6000);u.reg_write(UC_ARM_REG_LR,0x1101)
 if hook:u.hook_add(hook,lambda *args:None,begin=0x3000,end=0x30ff)
 try:u.emu_start(0x1001,0x110c,count=30)
 except UcError:return False
 return u.reg_read(UC_ARM_REG_R0)==7 and u.reg_read(UC_ARM_REG_R8)==0x4000
assert trial() and trial(code=store), 'Unobserved synthetic Thumb programs failed'
print(json.dumps(dict(status='PASS_VM_OBSERVER_REGRESSION',
    read_hook_changes_IT_execution=not trial(UC_HOOK_MEM_READ),
    write_hook_changes_IT_execution=not trial(UC_HOOK_MEM_WRITE,store),
    unobserved_programs_pass=True,synthetic_code_only=True)))
