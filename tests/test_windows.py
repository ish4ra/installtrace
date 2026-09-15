"""Windows integration checks: only temporary files are changed."""
import os
import tempfile
import unittest
from pathlib import Path
from installtrace.collect import capture
from installtrace.core import compare

@unittest.skipUnless(os.name == 'nt', 'Windows integration requires Windows')
class WindowsSmoke(unittest.TestCase):
    def test_capture_and_compare(self):
        with tempfile.TemporaryDirectory() as d:
            before=capture([d],1)
            (Path(d)/'installtrace-smoke.txt').write_text('fixture',encoding='utf-8')
            after=capture([d],1)
            self.assertEqual(before['sections']['services']['status'],'complete',before['sections']['services']['errors'])
            self.assertEqual(before['sections']['tasks']['status'],'complete',before['sections']['tasks']['errors'])
            rows=[r for r in compare(before,after)['changes'] if r['category']=='files']
            self.assertEqual(len(rows),1); self.assertEqual(rows[0]['kind'],'added')

if __name__=='__main__': unittest.main()
