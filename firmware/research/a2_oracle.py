"""ctypes helpers for the offline official-Core reference and compact implementation."""
import ctypes as c,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from a2_model import extract
F=c.POINTER(c.c_float)
def library(path):
 l=c.CDLL(str(Path(path).resolve()));l.a2_ref_create.argtypes=[c.c_char_p];l.a2_ref_create.restype=c.c_void_p
 l.a2_small_create.argtypes=[F,c.c_uint];l.a2_small_create.restype=c.c_void_p
 for mode in ['ref','small']:
  getattr(l,'a2_'+mode+'_process').argtypes=[c.c_void_p,F,F,c.c_uint]
  getattr(l,'a2_'+mode+'_destroy').argtypes=[c.c_void_p]
 l.a2_small_reset.argtypes=[c.c_void_p];l.a2_small_size.restype=c.c_uint
 return l
class Engine:
 def __init__(self,lib,path,mode='ref'):
  self.lib,self.mode=lib,mode
  if mode=='ref':self.p=lib.a2_ref_create(str(Path(path).resolve()).encode())
  else:
   j=extract(json.loads(Path(path).read_text()));w=(c.c_float*len(j['weights']))(*j['weights']);self.p=lib.a2_small_create(w,len(w))
  if not self.p:raise ValueError('Failed model construction')
 def run(self,x):
  n=len(x);a=(c.c_float*n)(*x);b=(c.c_float*n)();getattr(self.lib,'a2_'+self.mode+'_process')(self.p,a,b,n);return list(b)
 def close(self):
  if self.p:getattr(self.lib,'a2_'+self.mode+'_destroy')(self.p);self.p=None
 def __del__(self):self.close()
