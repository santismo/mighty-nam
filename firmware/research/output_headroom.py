"""Independent host specification of the NAMLNK06 final stereo guard."""
import math, struct
CEILING = 0.875
TARGET = float.fromhex('0x1.bffffcp-1')
def f32(x):
 return struct.unpack('<f',struct.pack('<f',x))[0]
def protect(left,right):
 samples=left+right
 if not all(math.isfinite(x) for x in samples):return [0.]*8,[0.]*8,True
 peak=max(map(abs,samples))
 if peak<=CEILING:return left[:],right[:],False
 gain=f32(TARGET/peak)
 bits=struct.unpack('<I',struct.pack('<f',gain))[0]
 gain=struct.unpack('<f',struct.pack('<I',max(0,bits-1)))[0]
 return [f32(x*gain) for x in left],[f32(x*gain) for x in right],False
