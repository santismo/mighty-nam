#!/usr/bin/env python3
"""Generate the two-action Bluefy launcher; sign with Apple's `shortcuts sign`."""
import argparse, plistlib, subprocess
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('output',type=Path);a=p.parse_args()
a.output.mkdir(parents=True,exist_ok=True)
url='bluefy://open?url=https%3A%2F%2Fsantismo.github.io%2Fmighty-nam-controller%2F'
workflow={'WFWorkflowName':'mighty nam','WFWorkflowClientVersion':'2302.0.4.2','WFWorkflowMinimumClientVersion':900,
 'WFWorkflowIcon':{'WFWorkflowIconStartColor':460140287,'WFWorkflowIconGlyphNumber':61440},
 'WFWorkflowTypes':[],'WFWorkflowInputContentItemClasses':[], 'WFWorkflowImportQuestions':[],
 'WFWorkflowActions':[
  {'WFWorkflowActionIdentifier':'is.workflow.actions.url','WFWorkflowActionParameters':{'WFURLActionURL':url}},
  {'WFWorkflowActionIdentifier':'is.workflow.actions.openurl','WFWorkflowActionParameters':{}}]}
source=a.output/'mighty nam.unsigned.shortcut';source.write_bytes(plistlib.dumps(workflow,sort_keys=False))
subprocess.run(['shortcuts','sign','--mode','anyone','--input',str(source),'--output',str(a.output/'mighty nam.shortcut')],check=True)
print('Signed mighty nam.shortcut for public sharing; no contact information requested.')
