"""Build an isolated offline wah experiment; never stages an update container.

The normal public builder and its firmware keep their tested wah unchanged.
"""
import argparse,hashlib,json,subprocess,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
sys.path.insert(0,str(ROOT/'firmware/ports/v3'))
from prepare import prepare

def main():
 p=argparse.ArgumentParser();p.add_argument('output',type=Path);a=p.parse_args();out=a.output.resolve()
 generated=prepare(out/'generated');target=generated/'target/link'
 h=target/'fx_blocks.hpp';text=h.read_text().replace('#include <stdint.h>','#include <stdint.h>\n#include "wah.hpp"')
 text=text.replace('struct Engine {','struct Engine {\n mighty_wah::State wah;');h.write_text(text)
 (target/'wah.hpp').write_bytes((HERE/'wah.hpp').read_bytes())
 source=target/'fx_blocks.cpp';text=source.read_text().replace('void Engine::reset(){','void Engine::reset(){\n wah.reset();')
 start=text.index('  }else if(mode==2){');end=text.index('  }else if(mode==3',start)
 text=text[:start]+text[end:]
 at=' if(!c[1]&&wet==0)return;'
 early='''
 if(mode==2){
  const float target=c[1]?c[4]*.01f:0;
  const float sensitivity=.25f+.006375f*c[8]*c[8],resonance=.35f+.013f*c[9];
  for(unsigned i=0;i<count;++i){
   float original[2]={l[i],r[i]},x[2]={l[i],r[i]};
   if(!__builtin_isfinite(x[0])||!__builtin_isfinite(x[1])){reset();l[i]=r[i]=0;continue;}
   wah.process(x,sensitivity,resonance);wet+=clamp(target-wet,-1.f/256,1.f/256);
   for(unsigned ch=0;ch<2;++ch){float y=original[ch]+wet*(x[ch]-original[ch]);
    if(!__builtin_isfinite(y)){reset();y=0;}if(ch)r[i]=y;else l[i]=y;}
  }return;
 }
'''
 assert text.count(at)==1;text=text.replace(at,at+early);source.write_text(text)
 # Only the isolated FX translation unit uses size-oriented optimization.
 # NAM kernels retain the production flags; regression tests cover pitch.
 builder=generated/'tools/build_link_firmware.py';bt=builder.read_text()
 bt=bt.replace("subprocess.run(['clang++',*flags,optimize", "if 'fx_blocks.cpp' in source:optimize='-Os'\n subprocess.run(['clang++',*flags,optimize")
 builder.write_text(bt)
 # Keep the exact production feature set and eight-frame scheduler.
 flags='stock-chain m7-conv fast-bypass m7-dense prime-state irq-timing listening early-output output-buffer preset-bank performance tuner fx-blocks cut-eq responsive-controls nam-pointer adc-short-delay global-buffer driver-timing active-chain usb-nam-controls pitch-quality bluetooth-audio'.split()
 subprocess.run([sys.executable,str(generated/'tools/build_link_firmware.py'),str(out/'build'),*['--'+f for f in flags]],check=True)
 path=out/'build/build.json';meta=json.loads(path.read_text());meta.update(status='OFFLINE_WAH_PROTOTYPE_NOT_FOR_INSTALLATION',research_only=True,stock_base='V3.0.5 Original',experiment='DaisySP linked-stereo auto-wah',physical_deadlines_verified=False,host_audio_access=False)
 path.write_text(json.dumps(meta,indent=2)+'\n')
 (out/'prototype.json').write_text(json.dumps(dict(source_sha256=hashlib.sha256((HERE/'wah.hpp').read_bytes()).hexdigest(),elf_sha256=meta['elf_sha256'],device_access=False,flash_container_created=False),indent=2)+'\n')
 print(meta['status'],meta['regions'])

if __name__=='__main__':main()
