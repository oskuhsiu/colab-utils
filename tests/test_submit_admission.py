"""Offline submission admission and at-most-once transport contracts."""
import copy
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'skills/colab-video-studio/scripts'))
import workflow as w
import studio
from test_workflow_state import plan


class SubmissionAdmissionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.plan = plan()
        self.save()
    def tearDown(self):
        self.temp.cleanup()
    def save(self):
        w.write_json(self.root / 'plan.json', self.plan)
    def reserve(self, shot='s1'):
        return studio.reserve_and_pack(self.root, shot)
    def assert_blocked_without_transport(self, attempts):
        with patch.object(studio, 'colab') as transport:
            for directory in attempts:
                with self.assertRaisesRegex(ValueError, 'budget is below existing reservations'):
                    studio.submit(self.root, directory.name, 'test-session')
                self.assertEqual(w.read_json(directory / 'receipt.json')['state'], 'reserved')
            transport.assert_not_called()
    def test_lower_total_budget_blocks_reserved_work_before_upload(self):
        second_shot = copy.deepcopy(self.plan['shots'][0])
        second_shot['id'] = 's2'
        self.plan['shots'].append(second_shot)
        self.save()
        attempts = [self.reserve('s1'), self.reserve('s2')]
        self.plan['budget']['max_total_attempts'] = 1
        self.save()
        self.assert_blocked_without_transport(attempts)
    def test_lower_per_shot_budget_blocks_reserved_work_before_upload(self):
        attempts = [self.reserve(), self.reserve()]
        self.plan['budget']['max_attempts_per_shot'] = 1
        self.save()
        self.assert_blocked_without_transport(attempts)
    def test_budget_is_rechecked_after_upload_before_exec(self):
        first, second = self.reserve(), self.reserve()
        calls = []
        def transport(arguments, log=None):
            calls.append(arguments[0])
            self.plan['budget']['max_total_attempts'] = 1
            self.save()
        with patch.object(studio, 'colab', side_effect=transport):
            with self.assertRaisesRegex(ValueError, 'budget is below existing reservations'):
                studio.submit(self.root, first.name, 'test-session')
        self.assertEqual(calls, ['upload'])
        self.assertEqual(w.read_json(first / 'receipt.json')['state'], 'needs_reconcile')
        self.assertEqual(w.read_json(second / 'receipt.json')['state'], 'reserved')
    def test_concurrent_duplicate_submit_has_only_one_upload_and_exec(self):
        directory = self.reserve()
        uploading, release = threading.Event(), threading.Event()
        calls, errors = [], []
        def transport(arguments, log=None):
            calls.append(arguments[0])
            if arguments[0] == 'upload':
                uploading.set()
                if not release.wait(5):
                    raise RuntimeError('Test transport did not release')
        def submit():
            try:
                studio.submit(self.root, directory.name, 'test-session')
            except Exception as exc:
                errors.append(exc)
        with patch.object(studio, 'colab', side_effect=transport), patch.object(studio, 'fetch', return_value={}):
            worker = threading.Thread(target=submit)
            worker.start()
            self.assertTrue(uploading.wait(5))
            try:
                with self.assertRaisesRegex(ValueError, 'Only an unsubmitted reserved attempt'):
                    studio.submit(self.root, directory.name, 'test-session')
            finally:
                release.set()
                worker.join(5)
            self.assertFalse(worker.is_alive())
        self.assertFalse(errors)
        self.assertEqual(calls, ['upload', 'exec'])
        receipt = w.read_json(directory / 'receipt.json')
        self.assertEqual(receipt['submission_budget'], self.plan['budget'])
        self.assertEqual(receipt['execution_budget'], self.plan['budget'])
    def test_uncertain_execution_is_not_retried(self):
        directory = self.reserve()
        calls = []
        def transport(arguments, log=None):
            calls.append(arguments[0])
            if arguments[0] == 'exec':
                raise RuntimeError('Transport lost after dispatch')
        with patch.object(studio, 'colab', side_effect=transport):
            with self.assertRaisesRegex(RuntimeError, 'Transport lost'):
                studio.submit(self.root, directory.name, 'test-session')
            with self.assertRaisesRegex(ValueError, 'Only an unsubmitted reserved attempt'):
                studio.submit(self.root, directory.name, 'test-session')
        self.assertEqual(calls, ['upload', 'exec'])
        self.assertEqual(w.read_json(directory / 'receipt.json')['state'], 'needs_reconcile')
    def test_policy_increase_does_not_change_generation_identity(self):
        directory = self.reserve()
        job_digest = w.read_json(directory / 'job.json')['job_digest']
        self.plan['budget']['max_total_attempts'] = 4
        self.save()
        with patch.object(studio, 'colab') as transport, patch.object(studio, 'fetch', return_value={}):
            studio.submit(self.root, directory.name, 'test-session')
        self.assertEqual(transport.call_count, 2)
        self.assertEqual(w.read_json(directory / 'job.json')['job_digest'], job_digest)
        self.assertEqual(w.read_json(directory / 'receipt.json')['execution_budget']['max_total_attempts'], 4)

if __name__ == '__main__':
    unittest.main()
