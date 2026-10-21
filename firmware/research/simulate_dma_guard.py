"""Conditional publication-window model, NOT a physical timing proof."""
import argparse,json,itertools
from pathlib import Path

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('report',type=Path);a=p.parse_args()
 # Historical whole-IRQ counter/period estimate, not clock calibration. A
 # serial word is one of four 32-bit lanes per frame, 32 per eight-frame IRQ.
 word=166025.33/32;safe=rejected=0
 for occupancy,prior,phase,snapshot,copy in itertools.product(range(9,33),(False,True),(0,.25,.5,.999),(0,512,1024,2047),(0,512,1024,2048)):
  slack=occupancy-8+(16 if prior else 0)
  if slack<=4:rejected+=1;continue
  # Worst phase may consume one word immediately after the FIFO read. A
  # nonnegative bus-service delay can only postpone this modeled first read.
  deadline=(slack-phase)*word
  end=snapshot+copy
  assert end<4096 and end<deadline
  safe+=1
 # Negative control: a stalled copy exceeds its budget. At the first DMA
 # burst some words are new and others still hold the complete early fallback.
 deadline=4*word;store_span=50000
 first_burst=[int(i*store_span/32<deadline) for i in range(16)]
 assert any(first_burst) and not all(first_burst)
 report=dict(status='PASS_CONDITIONAL_DMA_GUARD_MODEL',within_budget_safe_cases=safe,guard_rejected_cases=rejected,
  negative_control=dict(copy_cycles=store_span,first_burst_contains_mixed_blocks=True,post_copy_detection_cannot_undo=True),
  assumptions=['32 ascending stores; snapshot <2048 cycles and whole masked transaction <4096',
   'Observed DMA/FIFO state represents an idle request boundary; no unobserved in-flight fetch',
   'Counter-to-serial-clock relationship remains compatible with the historical period estimate',
   'No second IRQ interval elapses between entry and publication; coherent memory and DSB visibility'],
  physical_deadline_proven=False,device_access=False,host_audio_access=False)
 a.report.write_text(json.dumps(report,indent=2)+'\n');print(report['status'],safe,rejected)
if __name__=='__main__':main()
