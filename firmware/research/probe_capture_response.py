"""Silent host-reference impulse probes; response shape is not device latency.

Subtract a matched zero-input run to remove DC/bias and initial-state output.
Report relative onset, largest excursion and energy centroid independently;
none is advertised as a uniform delay for a nonlinear guitar capture.
"""
import argparse,hashlib,json,math
from pathlib import Path
from a2_oracle import Engine,library


def analyze(values):
    assert all(math.isfinite(x) for x in values)
    peak=max(map(abs,values));assert peak>0
    energy=sum(x*x for x in values)
    return dict(first_above_minus60dB_sample=next(i for i,x in enumerate(values) if abs(x)>=peak*.001),
        largest_excursion_sample=max(range(len(values)),key=lambda i:abs(values[i])),
        energy_centroid_samples=sum(i*x*x for i,x in enumerate(values))/energy,
        peak=peak)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('library',type=Path);p.add_argument('report',type=Path)
    p.add_argument('models',type=Path,nargs='+');a=p.parse_args()
    # Validate timing analysis against known exact zero- and 37-sample probes.
    for delay in (0,37):
        for amplitude in (.1,-.1):
            check=analyze([0.]*delay+[amplitude]+[0.]*100)
            assert check['first_above_minus60dB_sample']==check['largest_excursion_sample']==delay
            assert abs(check['energy_centroid_samples']-delay)<1e-10
    lib=library(a.library);rows=[]
    for path in a.models:
        for amplitude in (.001,.01,.1):
            baseline=Engine(lib,path);probe=Engine(lib,path)
            try:
                for _ in range(48):baseline.run([0.]*1000);probe.run([0.]*1000)
                y=probe.run([amplitude]+[0.]*1023);z=baseline.run([0.]*1024)
                for _ in range(3):y+=probe.run([0.]*1024);z+=baseline.run([0.]*1024)
                row=dict(model=path.name,model_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                    impulse_amplitude=amplitude,**analyze([x-w for x,w in zip(y,z)]))
                rows.append(row);print(json.dumps(row),flush=True)
            finally:baseline.close();probe.close()
    report=dict(status='PASS_HOST_CAPTURE_RESPONSE_PROBES',sample_rate=48000,
        warmup_samples=48000,response_samples=4096,cases=rows,exact_analysis_fixtures=4,
        library_sha256=hashlib.sha256(a.library.read_bytes()).hexdigest(),
        device_access=False,host_audio_access=False,
        limits=['Official Core host reference only; no firmware audio driver, ADC/DAC or stock effects.',
          'Relative -60 dB threshold is an analysis choice, not a perceptual or electrical onset guarantee.',
          'Peak and centroid describe level-dependent response shape; not uniform buffering delay.',
          'No capture modification, automatic phase correction or time advance.'])
    a.report.write_text(json.dumps(report,indent=2)+'\n')


if __name__=='__main__':main()
