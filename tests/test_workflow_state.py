"""Offline state and real FFmpeg regressions; no model, account or paid calls."""
import copy
import multiprocessing
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'skills/colab-video-studio/scripts'))
import workflow as w
import media
import editing


def plan():
    kinds = ['action', 'framing', 'style', 'artifacts', 'audio']
    return dict(schema_version=1, project_id='state-test',
        request={'kind': 'stylized', 'text': 'A red square'},
        budget={'max_total_attempts': 2, 'max_attempts_per_shot': 2},
        delivery={'width': 128, 'height': 128, 'fps': 24},
        settings={'backend': 'wan22-ti2v'}, assets={}, characters=[],
        shots=[dict(id='s1', duration_seconds=1, width=128, height=128, seed=1,
            prompt='A static red square', inputs={}, audio='none',
            start_state={'square': 'red'}, end_state={'square': 'red'},
            criteria=[dict(id=k, kind=k, requirement=k) for k in kinds],
            qa={'event_windows': [{'criterion': 'action', 'start': 0.25, 'end': 0.75, 'fps': 8}]})])


def hold_lock(path, connection):
    with w.reservation_lock(path):
        connection.send('locked')
        connection.recv()


def reserve_once(root, connection):
    try:
        w.reserve(root, 's1')
        connection.send('reserved')
    except ValueError:
        connection.send('budget exhausted')


class IdentityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.plan = plan()
        self.save()
    def tearDown(self):
        self.temp.cleanup()
    def save(self):
        w.write_json(self.root / 'plan.json', self.plan)
    def test_budget_and_qa_are_not_generation_identity(self):
        first = w.compile_job(self.root, 's1')
        self.plan['budget']['max_total_attempts'] = 4
        self.plan['shots'][0]['qa']['regions'] = [{'id': 'hands', 'box': [0, 0, 32, 32]}]
        self.plan['shots'][0]['criteria'][0]['requirement'] = 'Inspect the full action'
        self.save()
        revised = w.compile_job(self.root, 's1')
        self.assertEqual(first['job_digest'], revised['job_digest'])
        self.assertNotEqual(w.review_spec(first), w.review_spec(revised))
        self.plan['shots'][0]['prompt'] += ' blue background'
        self.save()
        self.assertNotEqual(first['job_digest'], w.compile_job(self.root, 's1')['job_digest'])
    def test_legacy_attempt_is_compared_without_rewriting_receipts(self):
        directory = self.root / 'attempts' / 'legacy'
        job = w.compile_job(self.root, 's1')
        job.pop('generation_digest')
        job.pop('job_digest')
        job['job_digest'] = w.digest(job)
        w.write_json(directory / 'job.json', job)
        self.plan['budget']['max_total_attempts'] += 1
        self.save()
        self.assertEqual(w.verify_current(self.root, directory), job)
        self.assertEqual(w.read_json(directory / 'job.json'), job)
    def test_budget_still_enforced_under_lock(self):
        w.reserve(self.root, 's1')
        w.reserve(self.root, 's1')
        with self.assertRaisesRegex(ValueError, 'budget exhausted'):
            w.reserve(self.root, 's1')
    def test_concurrent_reservations_cannot_exceed_budget(self):
        self.plan['budget'] = {'max_total_attempts': 1, 'max_attempts_per_shot': 1}
        self.save()
        pipes = [multiprocessing.Pipe() for _ in range(2)]
        processes = [multiprocessing.Process(target=reserve_once, args=(self.root, child))
                     for _, child in pipes]
        for process in processes:
            process.start()
        results = []
        for parent, _ in pipes:
            self.assertTrue(parent.poll(5))
            results.append(parent.recv())
        for process in processes:
            process.join(5)
            self.assertFalse(process.is_alive())
        self.assertCountEqual(results, ['reserved', 'budget exhausted'])
    @unittest.skipIf(sys.platform == 'win32', 'POSIX lock contract')
    def test_process_death_releases_existing_lock_file(self):
        path = self.root / 'lock'
        parent, child = multiprocessing.Pipe()
        process = multiprocessing.Process(target=hold_lock, args=(path, child))
        process.start()
        self.assertTrue(parent.poll(5))
        self.assertEqual(parent.recv(), 'locked')
        process.kill()
        process.join(5)
        self.assertFalse(process.is_alive())
        self.assertTrue(path.exists())
        with w.reservation_lock(path):
            pass


@unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe'), 'FFmpeg tools required')
class MediaStateTests(IdentityTests):
    def setUp(self):
        super().setUp()
        self.directory, self.job = w.reserve(self.root, 's1')
        (self.directory / 'input' / 'assets').mkdir(parents=True)
        (self.directory / 'result').mkdir()
        self.video = self.directory / 'result' / 'video.mp4'
        subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i',
            'color=c=red:s=128x128:r=24:d=1', '-c:v', 'libx264', '-pix_fmt', 'yuv420p', str(self.video)], check=True)
        w.write_json(self.directory / 'result/receipt.json', dict(status='generated',
            attempt_id=self.directory.name, job_digest=self.job['job_digest'], video_sha256=w.sha256(self.video)))
        self.selection = {'s1': self.directory.name}
    # Identity tests are covered separately, not repeated with a reserved fixture.
    test_budget_and_qa_are_not_generation_identity = None
    test_legacy_attempt_is_compared_without_rewriting_receipts = None
    test_budget_still_enforced_under_lock = None
    test_process_death_releases_existing_lock_file = None
    test_concurrent_reservations_cannot_exceed_budget = None
    def review(self, directory=None, verdict='pass'):
        directory = directory or self.directory
        review = w.review_template(directory)
        review['reviewer']['name'] = 'offline-test'
        for criterion in review['criteria']:
            criterion.update(verdict=verdict, evidence=['f000000'], reason='Synthetic review fixture')
        w.write_json(directory / 'review.json', review)
        return review
    def test_qa_refresh_reuses_video_and_invalidates_old_review(self):
        first = media.evidence(self.directory)
        old = self.review()
        video_sha = w.sha256(self.video)
        self.plan['shots'][0]['qa']['regions'] = [{'id': 'detail', 'box': [0, 0, 32, 32]}]
        self.save()
        with self.assertRaisesRegex(ValueError, 'outdated review'):
            w.validate_review(self.directory, old)
        second = media.evidence(self.directory)
        self.assertEqual(video_sha, w.sha256(self.video))
        self.assertNotEqual(first['evidence_version'], second['evidence_version'])
        self.assertTrue(any(x['kind'] == 'crop' for x in second['items']))
        self.assertTrue((self.directory / 'evidence' / first['items'][0]['path']).exists())
        with self.assertRaisesRegex(ValueError, 'stale'):
            w.validate_review(self.directory, old)
        w.validate_review(self.directory, self.review(), require_pass=True)
    def test_failed_extraction_keeps_previous_published_evidence(self):
        media.evidence(self.directory)
        review = self.review()
        before = w.sha256(self.directory / 'evidence/manifest.json')
        with patch.object(media, 'run', side_effect=RuntimeError('interrupted ffmpeg')):
            with self.assertRaises(RuntimeError):
                media.evidence(self.directory)
        self.assertEqual(before, w.sha256(self.directory / 'evidence/manifest.json'))
        self.assertFalse(list((self.directory / 'evidence/versions').glob('.*.tmp')))
        w.validate_review(self.directory, review, require_pass=True)
        media.evidence(self.directory)
    def test_partial_legacy_evidence_directory_can_be_retried(self):
        (self.directory / 'evidence/frames').mkdir(parents=True)
        media.evidence(self.directory)
        w.verify_evidence(self.directory)
    def test_corrective_trim_accepts_failed_raw_but_edited_release_requires_pass(self):
        media.evidence(self.directory)
        self.review(verdict='fail')
        edits = {'s1': {'start': 0.25, 'end': 0.75, 'duration_seconds': 0.5}}
        run = editing.prepare_edits(self.root, self.selection, edits, 'repair')
        segments = editing.inspect_edits(self.root, run)
        self.assertEqual(len(segments), 1)
        segment = run / 'segments/s1'
        self.review(segment, 'unknown')
        with self.assertRaisesRegex(ValueError, 'Failed/unknown'):
            editing.assemble_edits(self.root, run)
        self.review(segment, 'pass')
        report = editing.assemble_edits(self.root, run)
        self.assertEqual(report['status'], 'assembled_from_reviewed_shots')
        self.assertTrue((self.root / 'deliverables/final.mp4').exists())
    def test_unreviewed_raw_can_be_edited_without_inventing_source_approval(self):
        run = editing.prepare_edits(self.root, self.selection,
            {'s1': {'start': 0.25, 'end': 0.75, 'duration_seconds': 0.5}}, 'unreviewed')
        recipe = w.read_json(run / 'recipe.json')
        self.assertIsNone(recipe['segments']['s1']['provenance']['source_review_sha'])
        editing.inspect_edits(self.root, run)
    def test_same_shape_replaced_video_cannot_be_edited_or_inspected(self):
        subprocess.run(['ffmpeg', '-y', '-v', 'error', '-f', 'lavfi', '-i',
            'color=c=blue:s=128x128:r=24:d=1', '-c:v', 'libx264', '-pix_fmt', 'yuv420p', str(self.video)], check=True)
        with self.assertRaisesRegex(ValueError, 'immutable generation'):
            media.evidence(self.directory)
        with self.assertRaisesRegex(ValueError, 'immutable generation'):
            editing.prepare_edits(self.root, self.selection,
                {'s1': {'start': 0.25, 'end': 0.75, 'duration_seconds': 0.5}}, 'tampered')

    def test_explicit_preview_never_creates_final_or_delivery_approval(self):
        with self.assertRaisesRegex(ValueError, 'nonempty reason'):
            media.assemble(self.root, self.selection, preview=True)
        report = media.assemble(self.root, self.selection, preview=True, preview_reason='Check rough cut')
        self.assertFalse(report['quality_approved'])
        self.assertEqual(report['file'], 'preview.mp4')
        self.assertFalse((self.root / 'deliverables/final.mp4').exists())
        self.assertFalse((self.root / 'deliverables/delivery.json').exists())
        with self.assertRaises(FileNotFoundError):
            media.assemble(self.root, self.selection)

if __name__ == '__main__':
    unittest.main()
