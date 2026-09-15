import tempfile
import threading
import unittest
from pathlib import Path
from installtrace import core
from installtrace.collect import collect_files, Cancelled, normalized_roots
from installtrace.demo import samples

class ComparisonTests(unittest.TestCase):
    def setUp(self): self.a,self.b,self.c = samples()
    def test_expected_diffs(self):
        changes = core.compare(self.a,self.b)['changes']
        self.assertEqual(len(changes), 5)
        self.assertEqual(sum(c['kind']=='added' for c in changes),4)
    def test_identical(self): self.assertEqual(core.compare(self.a,self.a)['changes'],[])
    def test_leftovers(self):
        changes = core.leftovers(self.a,self.b,self.c)['changes']
        self.assertEqual([(c['category'],c['key']) for c in changes], [('services','exampleupdater')])
    def test_unrelated_post_uninstall_change_excluded(self):
        self.c['sections']['tasks']['records']['other']={'value':1}
        self.assertEqual(len(core.leftovers(self.a,self.b,self.c)['changes']),1)
    def test_incomplete_scan_not_deletion(self):
        self.c['sections']['files'].update(status='unavailable',records={})
        self.assertEqual(core.compare(self.a,self.c)['changes'][0]['kind'],'uncertain')
    def test_incomplete_baseline_not_addition(self):
        self.a['sections']['services']['status']='partial'
        row=next(c for c in core.compare(self.a,self.b)['changes'] if c['category']=='services')
        self.assertEqual(row['kind'],'uncertain')
    def test_machine_guard(self):
        self.b['machine']['hostname']='OTHER'
        with self.assertRaises(ValueError): core.compare(self.a,self.b)
    def test_scope_guard(self):
        self.b['scope']['hash_mb']=0
        with self.assertRaises(ValueError): core.compare(self.a,self.b)
    def test_bad_schema(self):
        with self.assertRaises(ValueError): core.validate({'schema':99})
    def test_roundtrip_unicode(self):
        self.a['sections']['files']['records']['සිංහල']={'size':1}
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'snapshot.json'; core.save(p,self.a)
            self.assertEqual(core.load(p),self.a)
    def test_report_escapes_untrusted_data(self):
        self.b['sections']['files']['records']['<script>alert(1)</script>']={'size':1}
        rendered=core.report_html(core.compare(self.a,self.b))
        self.assertNotIn('<script>',rendered); self.assertIn('&lt;script&gt;',rendered)

class FileTests(unittest.TestCase):
    def test_real_file_content_change(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'a.txt'; p.write_text('before')
            a=collect_files([d],100,threading.Event(),lambda _:None)
            p.write_text('after')
            b=collect_files([d],100,threading.Event(),lambda _:None)
            self.assertNotEqual(next(iter(a['records'].values()))['sha256'],next(iter(b['records'].values()))['sha256'])
    def test_absent_root_is_empty(self):
        with tempfile.TemporaryDirectory() as d:
            result=collect_files([str(Path(d)/'absent')],0,threading.Event(),lambda _:None)
            self.assertEqual(result['status'],'complete'); self.assertEqual(result['records'],{})
    def test_cancellation(self):
        cancel=threading.Event(); cancel.set()
        with self.assertRaises(Cancelled): collect_files(['anything'],0,cancel,lambda _:None)
    def test_hash_limit(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d)/'a').write_text('12345')
            result=collect_files([d],2,threading.Event(),lambda _:None)
            self.assertEqual(next(iter(result['records'].values()))['hash_status'],'metadata-only')
    def test_nested_scope_deduplicated(self):
        with tempfile.TemporaryDirectory() as d:
            import os
            self.assertEqual(normalized_roots([d,str(Path(d)/'child')]),[os.path.normcase(d)])

if __name__=='__main__': unittest.main()
