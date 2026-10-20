#!/usr/bin/env python3
"""Offline USB-controller selection evidence; no USB APIs or commands."""
import argparse,json,struct,hashlib
from pathlib import Path
from unicorn import *
from unicorn.arm_const import *
p=argparse.ArgumentParser();p.add_argument('payload');p.add_argument('--output',required=True);a=p.parse_args();b=Path(a.payload).read_bytes();sha=hashlib.sha256(b).hexdigest();assert sha=='a8a064a5b0e308b9cf193ebdf23d352ddff092d88db71531729ca1864a86d990'
STOP=0x3fffc
u=Uc(UC_ARCH_ARM,UC_MODE_THUMB);u.ctl_set_cpu_model(UC_CPU_ARM_CORTEX_M7);u.mem_map(0,0x40000);u.mem_write(0,b[:0x2356c]);u.mem_map(0x20000000,0x40000)
def run(pc):
 u.reg_write(UC_ARM_REG_SP,0x20035f00);u.reg_write(UC_ARM_REG_LR,STOP|1);u.emu_start(pc|1,STOP,count=10000);assert u.reg_read(UC_ARM_REG_PC)==STOP
mapping=[]
for selector in [2,3]:
 u.reg_write(UC_ARM_REG_R0,selector);run(0x13638);v=u.reg_read(UC_ARM_REG_R0);assert v==[0x40434000,0x40438000][selector-2];mapping.append({'selector':selector,'returned_phy_base':hex(v)})
# Capture clock/PHY requests without executing any peripheral setup.
calls=[]
def call(uc,pc,size,user):
 calls.append({'entry':hex(pc),'args':[hex(uc.reg_read(reg)) for reg in [UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2]]})
for pc in [0x8dc0,0x8dbc,0x13688]:
 u.mem_write(pc,bytes.fromhex('00207047'));u.hook_add(UC_HOOK_CODE,call,begin=pc,end=pc)
run(0xf040);assert len(calls)==3 and calls[-1]['args'][0]=='0x2'
# Application USB class initialization also requests selector 2. Exit via its
# ordinary failure branch after recording the request; no controller code runs.
u.mem_write(0xf040,bytes.fromhex('7047'));u.mem_write(0x13872,bytes.fromhex('01207047'))
u.hook_add(UC_HOOK_CODE,call,begin=0x13872,end=0x13872);u.ctl_remove_cache(0,0x40000)
run(0xf1cc);assert calls[-1]['entry']=='0x13872' and calls[-1]['args'][0]=='0x2'
result={'status':'PASS_OFFLINE_USB1_SELECTION_EVIDENCE','device_access':False,'playback':False,'payload_sha256':sha,'normal_boot_path':['0xe642 calls 0xccc6','0xccc6 tails to 0xf1cc','0xf1cc calls 0xf040 PHY/clock setup and passes selector 2 to 0x13872 class init'],
 'actual_saved_phy_selector_results':mapping,'intercepted_setup_calls':calls,'conclusion':'The public application selects PHY1 (0x40434000), matching NXP USB1 used by the RT1170 ROM downloader. This strengthens the same-connector hypothesis; it does not establish electrical routing, ROM entry or ROM security acceptance on the physical unit.',
 'boot_pin_comparison':{'nxp_rom_boot_mode_pads':['GPIO_LPSR_02','GPIO_LPSR_03'],'inferred_application_preset_pad':'GPIO_EMC_B1_39','inferred_application_power_pad':'GPIO_EMC_B2_03','conclusion':'The identified application button GPIOs differ from the ROM boot-mode pads. No direct ROM-entry button mechanism was established; alternate board wiring and missing-loader logic remain unknown.'},
 'alternate_routes':[
 {'route':'Existing NUX blue-mode updater','shortest_likely_upload_route':True,'state':'Transport framing known; modified-image acceptance and failed-application recovery unproven. No reason established that full standalone replacement is easier than the existing stock-AMP patch.'},
 {'route':'NXP ROM RAM-only run','state':'Chip feature documented; same USB1 selection now supported by application code. Still needs entry without already running new code, permitted RAM loading/execution and verified return-to-stock.'},
 {'route':'Install an SDK USB DFU loader','state':'Requires installing new code first; does not supply a sealed entry or recovery route for the untouched stock unit.'},
 {'route':'ROM dual-image/fallback configuration','state':'Not a drop-in rollback mechanism. NXP example involves flash layout and fuse configuration; no such setup has been established for this plug, and none was changed.'}
 ],
 'sources':[
 {'url':'https://raw.githubusercontent.com/nxp-mcuxpresso/legacy-mcux-sdk/main/devices/MIMXRT1176/MIMXRT1176_cm7.h','finding':'PHY1=0x40434000; USB_OTG1=0x40430000; PHY2=0x40438000.'},
 {'url':'https://www.nxp.com/docs/en/data-sheet/IMXRT1170CEC.pdf','finding':'Boot-mode pads are GPIO_LPSR_02 and GPIO_LPSR_03; fuse configuration affects boot selection.'},
 {'url':'https://community.nxp.com/pwmxy87654/attachments/pwmxy87654/imxrt/26861/1/MIMXRT1170HDUG.pdf','finding':'ROM serial downloader polls USB1 and UART1; watchdog behavior depends on fuse policy.'},
 {'url':'https://community.nxp.com/t5/i-MX-RT-Crossover-MCUs/RT1170-dual-image-support-wi-ROM-API-s-explained-for-real/td-p/1951473','finding':'NXP support describes an EVK demonstration using flash provisioning and fuse-selected image offsets. It is not evidence of a NUX fallback slot.'}
 ],'physical_recovery_proven':False,'ram_only_launch_proven':False,'blue_mode_needed_now':False}
Path(a.output).write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({'status':result['status'],'selected_phy':'PHY1','rom_entry_still_unproven':True}))
