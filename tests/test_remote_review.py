"""Offline model-cache and bounded-review regression tests. No GPU or API calls."""
import copy
import json
import hashlib
import shutil
import subprocess
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

SCRIPTS = Path(__file__).resolve().parents[1] / 'skills/colab-video-studio/scripts'
sys.path.insert(0, str(SCRIPTS))
import remote
import backends
import review_opus


class BackendCacheTests(unittest.TestCase):
    def setUp(self):
        remote._VIDEO_BACKEND = None
        remote._VIDEO_BACKEND_KEY = None

    def settings(self):
        return dict(backend='h3', revision='revision1', model_id='model', loras=[
            dict(path='/attempt1/0.safetensors', sha256='a' * 64, scale=.5, kind='style')])

    def test_lora_transport_path_does_not_change_identity(self):
        a = self.settings(); b = copy.deepcopy(a)
        b['loras'][0]['path'] = '/attempt2/0.safetensors'
        self.assertEqual(remote.backend_cache_key(a, {'backends.py': 'x'}),
                         remote.backend_cache_key(b, {'backends.py': 'x'}))
        for field, value in [('sha256', 'b' * 64), ('scale', .6)]:
            c = copy.deepcopy(b); c['loras'][0][field] = value
            self.assertNotEqual(remote.backend_cache_key(a, {}), remote.backend_cache_key(c, {}))
        self.assertNotEqual(remote.backend_cache_key(a, {'backends.py': 'x'}),
                            remote.backend_cache_key(a, {'backends.py': 'y'}))
        c = copy.deepcopy(a); c['revision'] = 'revision2'
        self.assertNotEqual(remote.backend_cache_key(a, {}), remote.backend_cache_key(c, {}))

    def test_cache_requires_verified_content_digest(self):
        a = self.settings(); a['loras'][0].pop('sha256')
        with self.assertRaises(ValueError): remote.backend_cache_key(a, {})

    def test_failed_replacement_cannot_reuse_old_key(self):
        model = object(); loader = mock.Mock(return_value=model)
        self.assertEqual(remote.cached_backend('a', loader), (model, False))
        self.assertEqual(remote.cached_backend('a', loader), (model, True))
        self.assertEqual(loader.call_count, 1)
        with self.assertRaises(RuntimeError):
            remote.cached_backend('b', mock.Mock(side_effect=RuntimeError('load failed')))
        self.assertIsNone(remote._VIDEO_BACKEND_KEY)
        self.assertIsNone(remote._VIDEO_BACKEND)
        self.assertEqual(remote.cached_backend('a', loader), (model, False))
        self.assertEqual(loader.call_count, 2)

    def test_none_backend_is_never_reused(self):
        remote._VIDEO_BACKEND_KEY = 'a'
        with self.assertRaises(RuntimeError): remote.cached_backend('a', lambda: None)
        self.assertIsNone(remote._VIDEO_BACKEND_KEY)

    def test_h3_install_marker_survives_new_namespace(self):
        # A synthetic setup mirrors its installation signature contract without pip.
        source = '''
if globals().get('_INSTALL_SIGNATURE') != 'test-install':
    _INSTALL_SIGNATURE = 'test-install'
    H3_INSTALL_WAS_REUSED = False
else:
    H3_INSTALL_WAS_REUSED = True
pipe = object()
def selected_config():
    return dict(task_mode=H3_TASK_MODE, steps=8, precision=H3_PRECISION)
REVISIONS = {'model': 'revision1'}
'''
        with tempfile.TemporaryDirectory() as tmp:
            setup = Path(tmp) / 'h3_setup.py'; setup.write_text(source)
            settings = dict(backend='h3', model_id='model', loras=[])
            state = {}
            with mock.patch.object(backends, '__file__', str(Path(tmp) / 'backends.py')):
                a = backends.H3Backend(settings, lambda **kw: None, state)
                b = backends.H3Backend(settings, lambda **kw: None, state)
                self.assertFalse(a.namespace['H3_INSTALL_WAS_REUSED'])
                self.assertTrue(b.namespace['H3_INSTALL_WAS_REUSED'])
                setup.write_text(source + '\n# changed dependency recipe\n')
                c = backends.H3Backend(settings, lambda **kw: None, state)
                self.assertFalse(c.namespace['H3_INSTALL_WAS_REUSED'])

    def test_successful_install_is_remembered_after_model_load_failure(self):
        source = """
reused = globals().get('_INSTALL_SIGNATURE') == 'installed'
_INSTALL_SIGNATURE = 'installed'
if H3_TASK_MODE == 'ref2va':
    raise RuntimeError('synthetic model load failure')
pipe = object()
def selected_config():
    return dict(task_mode=H3_TASK_MODE, steps=8, precision=H3_PRECISION)
REVISIONS = {'model': 'revision1'}
"""
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / 'h3_setup.py').write_text(source)
            settings = dict(backend='h3', model_id='model', loras=[], task_mode='ref2va')
            state = {}
            with mock.patch.object(backends, '__file__', str(Path(tmp) / 'backends.py')):
                with self.assertRaisesRegex(RuntimeError, 'model load failure'):
                    backends.H3Backend(settings, lambda **kw: None, state)
                settings['task_mode'] = 'fl2va'
                model = backends.H3Backend(settings, lambda **kw: None, state)
                self.assertTrue(model.namespace['reused'])


class ReviewBatchTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name); evidence = self.root / 'evidence/versions/v1'
        evidence.mkdir(parents=True)
        (evidence / 'media.json').write_text('{}')
        self.items = [dict(id='technical', kind='technical', path='versions/v1/media.json', sha256=hashlib.sha256(b'{}').hexdigest())]
        for index in range(122):
            kind = 'asset' if index < 2 else 'frame'
            path = f'versions/v1/image{index}.jpg'; (self.root / 'evidence' / path).write_bytes(b'jpeg-fixture')
            self.items.append(dict(id=f'image{index}', kind=kind, path=path, seconds=index / 24, sha256=hashlib.sha256(b'jpeg-fixture').hexdigest()))
        self.manifest = dict(items=self.items, coverage={}, review_spec={'criteria': [{'id': 'visual', 'requirement': 'updated'}]})
        self.template = dict(schema_version=1, job_digest='job', video_sha256='video', evidence_sha256='pack',
                             criteria=[dict(id='visual', verdict='unknown', evidence=[], reason='')])
        (self.root / 'job.json').write_text(json.dumps(dict(request={}, characters=[], shot={'criteria': []})))
        self.snapshot = dict(manifest=self.manifest, job=json.loads((self.root / 'job.json').read_text()), evidence_sha256='pack')
        self.patches = [mock.patch.object(review_opus, 'evidence_snapshot', return_value=self.snapshot),
                        mock.patch.object(review_opus, 'snapshot_template', return_value=self.template),
                        mock.patch.object(review_opus, 'require_snapshot_current'),
                        mock.patch.object(review_opus, 'validate_review')]
        for patch in self.patches: patch.start(); self.addCleanup(patch.stop)

    def test_windows_keep_all_frames_and_references(self):
        batches = review_opus.payloads(self.root, 'test-model', 96)
        self.assertEqual(len(batches), 2)
        seen = set()
        for body, template, count in batches:
            self.assertLessEqual(count, 96)
            contexts = [json.loads(b['text']) for b in body['messages'][0]['content'] if b['type'] == 'text']
            context = contexts[-1]
            ids = set(context['batch']['supplied_image_ids'])
            self.assertTrue({'image0', 'image1'}.issubset(ids))
            seen.update(ids)
            self.assertEqual(context['shot']['criteria'][0]['requirement'], 'updated')
        self.assertEqual(seen, {i['id'] for i in self.items if i['kind'] != 'technical'})

    def test_default_call_budget_rejects_before_network(self):
        with mock.patch.object(review_opus, '_send') as send:
            with self.assertRaisesRegex(ValueError, 'exceeding max_batches'):
                review_opus.review(self.root, 'test-model')
            send.assert_not_called()

    def answer(self, verdict='pass', evidence='image2'):
        return ({'model': 'test-model', 'id': 'request', 'usage': {}},
                {'criteria': [{'id': 'visual', 'verdict': verdict, 'evidence': [evidence], 'reason': 'observed'}], 'limitations': ['sampled']})

    def test_unseen_window_evidence_is_rejected(self):
        with mock.patch.dict('os.environ', {'ANTHROPIC_API_KEY': 'synthetic-not-a-key'}), \
             mock.patch.object(review_opus, '_send', return_value=self.answer(evidence='image121')):
            with self.assertRaisesRegex(ValueError, 'not supplied'):
                review_opus.review(self.root, 'test-model', max_batches=2)

    def test_static_criterion_passes_only_if_all_windows_pass(self):
        for second, expected in [('fail', 'fail'), ('unknown', 'unknown'), ('pass', 'pass')]:
            with self.subTest(second=second), \
                 mock.patch.dict('os.environ', {'ANTHROPIC_API_KEY': 'synthetic-not-a-key'}), \
                 mock.patch.object(review_opus, '_send', side_effect=[self.answer(), self.answer(second, 'image121')]) as send:
                result = review_opus.review(self.root, 'test-model', max_batches=2)
                self.assertEqual(result['criteria'][0]['verdict'], expected)
                self.assertEqual(send.call_count, 2)
                self.assertEqual(len(result['reviewer']['batches']), 2)
                self.assertEqual(result['reviewer']['kind'], 'claude_api_sampled_windows')

    def test_local_action_unknown_outside_its_window_requires_unified_review(self):
        with mock.patch.dict('os.environ', {'ANTHROPIC_API_KEY': 'synthetic-not-a-key'}), \
             mock.patch.object(review_opus, '_send', side_effect=[self.answer(), self.answer('unknown', 'image121')]):
            result = review_opus.review(self.root, 'test-model', max_batches=2)
            self.assertEqual(result['criteria'][0]['verdict'], 'unknown')
            self.assertTrue(any('unified' in limit for limit in result['limitations']))

    def test_single_window_review_can_still_pass(self):
        self.manifest['items'] = self.items[:5]
        with mock.patch.dict('os.environ', {'ANTHROPIC_API_KEY': 'synthetic-not-a-key'}), \
             mock.patch.object(review_opus, '_send', return_value=self.answer()):
            result = review_opus.review(self.root, 'test-model')
            self.assertEqual(result['criteria'][0]['verdict'], 'pass')
            self.assertEqual(result['reviewer']['kind'], 'claude_api')

    def test_invalid_capacity_rejected(self):
        for limit in [0, -1, True, 2]:
            with self.subTest(limit=limit), self.assertRaises(ValueError):
                review_opus.payloads(self.root, 'test-model', limit)


@unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe'), 'FFmpeg required')
class EvidenceSnapshotRaceTests(unittest.TestCase):
    """Real MP4, crops, manifests and validators; only external API is mocked."""
    def setUp(self):
        import workflow
        import media
        from test_workflow_state import plan
        self.w, self.media = workflow, media
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.plan = plan()
        self.plan['shots'][0]['qa']['regions'] = [{'id': 'detail', 'box': [0, 0, 32, 32]}]
        self.w.write_json(self.root / 'plan.json', self.plan)
        self.directory, self.job = self.w.reserve(self.root, 's1')
        (self.directory / 'input/assets').mkdir(parents=True)
        (self.directory / 'result').mkdir()
        video = self.directory / 'result/video.mp4'
        subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i',
                        'color=c=red:s=128x128:r=24:d=1', '-vf',
                        'drawbox=x=64:y=0:w=64:h=128:color=blue:t=fill',
                        '-c:v', 'libx264', '-pix_fmt', 'yuv420p', str(video)], check=True)
        self.w.write_json(self.directory / 'result/receipt.json', dict(status='generated',
            attempt_id=self.directory.name, job_digest=self.job['job_digest'], video_sha256=self.w.sha256(video)))
        self.media.evidence(self.directory)

    def refresh(self):
        self.plan['shots'][0]['qa']['regions'][0]['box'] = [64, 0, 32, 32]
        self.w.write_json(self.root / 'plan.json', self.plan)
        self.media.evidence(self.directory)

    def answer(self, body, key):
        context = json.loads(body['messages'][0]['content'][-1]['text'])
        return ({'model': 'synthetic', 'id': 'offline', 'usage': {}}, dict(
            criteria=[dict(id=c['id'], verdict='pass', evidence=['f000000_detail'],
                           reason='Synthetic API response for race verification, not content QA')
                      for c in context['review_template']['criteria']], limitations=['synthetic']))

    def test_real_evidence_baseline_review_validates(self):
        with mock.patch.dict('os.environ', {'ANTHROPIC_API_KEY': 'synthetic'}), \
             mock.patch.object(review_opus, '_send', side_effect=self.answer):
            result = review_opus.review(self.directory, 'synthetic')
        self.assertTrue(self.w.validate_review(self.directory, result, require_pass=True))

    def test_refresh_between_snapshot_and_template_is_rejected_before_api(self):
        original = review_opus.snapshot_template
        def race(snapshot):
            self.refresh()
            return original(snapshot)
        with mock.patch.object(review_opus, 'snapshot_template', side_effect=race), \
             mock.patch.object(review_opus, '_send') as send:
            with self.assertRaisesRegex(ValueError, 'Evidence changed'):
                review_opus.review(self.directory, 'synthetic')
            send.assert_not_called()

    def test_refresh_during_api_response_is_rejected(self):
        def race(body, key):
            answer = self.answer(body, key)
            self.refresh()
            return answer
        with mock.patch.dict('os.environ', {'ANTHROPIC_API_KEY': 'synthetic'}), \
             mock.patch.object(review_opus, '_send', side_effect=race):
            with self.assertRaisesRegex(ValueError, 'Evidence changed'):
                review_opus.review(self.directory, 'synthetic')

    def test_refresh_before_accept_cannot_mark_new_crop_passed(self):
        with mock.patch.dict('os.environ', {'ANTHROPIC_API_KEY': 'synthetic'}), \
             mock.patch.object(review_opus, '_send', side_effect=self.answer):
            result = review_opus.review(self.directory, 'synthetic')
        old_sha = result['evidence_sha256']
        self.w.write_json(self.root / 'response.json', result)
        self.refresh()
        self.assertNotEqual(old_sha, self.w.review_template(self.directory)['evidence_sha256'])
        with self.assertRaisesRegex(ValueError, 'stale'):
            self.w.accept_review(self.directory, self.root / 'response.json')
        self.assertEqual(self.w.read_json(self.directory / 'receipt.json')['state'], 'needs_review')


if __name__ == '__main__':
    unittest.main()
