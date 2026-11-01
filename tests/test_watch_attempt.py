import sys
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import subprocess

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'skills/colab-video-studio/scripts'))
import watch_attempt
from workflow import write_json

class WatchTests(unittest.TestCase):
    def test_deadline_never_submits_or_stops(self):
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp);(p/'attempts/a').mkdir(parents=True)
            clock=[0];calls=[]
            def observe(*args,**kwargs):calls.append(kwargs['timeout']);return {'phase':'sampling'}
            def sleep(seconds):clock[0]+=seconds
            result=watch_attempt.watch(p,'a',duration=3,interval=2,poll_timeout=10,observer=observe,monotonic=lambda:clock[0],sleep=sleep)
            self.assertEqual(calls,[3,1]);self.assertEqual(result['state'],'monitoring_deadline');self.assertFalse(result['runtime_released'])

    def test_transport_failure_stops_polling_without_retry(self):
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp);(p/'attempts/a').mkdir(parents=True)
            def fail(*a,**kw):raise subprocess.TimeoutExpired('colab',1)
            result=watch_attempt.watch(p,'a',observer=fail)
            self.assertEqual(result['state'],'needs_reconcile')

    def test_progress_identity_checked_and_stale_file_not_reused(self):
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp);d=p/'attempts/a';d.mkdir(parents=True)
            write_json(d/'receipt.json',{'session':'s','remote_directory':'/content/a','job_digest':'ours'})
            def download(args,**kwargs):
                self.assertEqual(args[3],'download');self.assertEqual(kwargs['timeout'],2)
                write_json(Path(args[-1]),{'attempt_id':'wrong','job_digest':'ours'})
            with patch.object(watch_attempt.subprocess,'run',side_effect=download):
                with self.assertRaisesRegex(ValueError,'identity'):watch_attempt.observe(p,'a',timeout=2)
            self.assertEqual(list(d.glob('watch-progress.*.json')), [])
