"""Silent release-gate fault checks. Uses only temporary synthetic files."""
import hashlib,json,tempfile,unittest
from pathlib import Path
from updater import verify
class ReleaseGate(unittest.TestCase):
 def test_file_and_target_mismatches(self):
  with tempfile.TemporaryDirectory() as folder:
   root=Path(folder);image=root/'image.bin';restore=root/'restore.bin';manifest=root/'release.json'
   image.write_bytes(b'custom image');restore.write_bytes(b'factory restore')
   entry=lambda p:{'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
   good={'schema':'nam-plug-release-1','target':'NUX-MP3','firmware':dict(entry(image),identity='NAMTEST1'),'restore':entry(restore),'loader':{'vid':0x9527,'pid':0xc157,'identifier':'20220615'}}
   manifest.write_text(json.dumps(good));self.assertFalse(verify(manifest,image,restore)['device_access'])
   for path,data in [(image,b'Custom image'),(restore,b'Factory restore')]:
    original=path.read_bytes();path.write_bytes(data)
    with self.assertRaises(ValueError):verify(manifest,image,restore)
    path.write_bytes(original)
   for field,value in [('target','NUX-MP2'),('schema','unknown')]:
    wrong=dict(good);wrong[field]=value;manifest.write_text(json.dumps(wrong))
    with self.assertRaises(ValueError):verify(manifest,image,restore)
   wrong=json.loads(json.dumps(good));wrong['loader']['identifier']='unknown';manifest.write_text(json.dumps(wrong))
   with self.assertRaises(ValueError):verify(manifest,image,restore)
if __name__=='__main__':unittest.main()
