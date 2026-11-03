"""Authored action windows reach real provider inputs; no generated-motion claims."""
import copy
from contextlib import nullcontext
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
import wave
import zipfile

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / 'skills/colab-video-studio/scripts'
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(ROOT / 'scripts'))
import dialogue_timing as timing
import workflow
import backends
import colab_video_bootstrap as bootstrap
from test_dialogue_timing import BASE, studio_plan
from test_shared_dialogue_integration import fixture as audio_fixture
from test_reference_resolver import catalog

spec = importlib.util.spec_from_file_location('omni_timing_test', ROOT / 'scripts/colab_omni_runtime/common.py')
omni = importlib.util.module_from_spec(spec)
spec.loader.exec_module(omni)


def beat(start, end, description, **kwargs):
    return dict(start_seconds=start, end_seconds=end, description=description, **kwargs)


# Content/time targets are authored test fixtures, not physical measurements.
CASES = {
    'reflex': [beat(.4, .7, 'On touching the hot handle, she snaps her hand away at once.')],
    'drop-impact': [beat(0, .6, 'Released from the hand, the key drops briskly onto the table and bounces once.')],
    'normal-walk': [beat(0, 3, 'He takes two ordinary unhurried steps to the chair, without creeping or rushing.')],
    'normal-transfer': [beat(.2, 2.2, 'At an everyday pace, she passes the cup into his waiting hand and lets go once he holds it.')],
    'slow-manipulation': [beat(0, 4, 'She slowly turns the delicate screw a quarter turn, deliberately keeping steady pressure.')],
    'quiet-surprise': [
        beat(0, 1.2, 'He continues an ordinary step, unaware of the weak board; no anticipatory flinch or preparatory crouch.'),
        beat(1.2, 1.65, 'The board suddenly snaps. Only his left leg plunges to the thigh; his hands strike the edge and his right leg stays supported, abruptly arresting the drop.'),
        beat(1.65, 4.3, 'Now braced, he winces, stabilizes his weight and cautiously starts freeing the trapped leg.')],
    'intentional-slow-motion': [beat(.5, 4, 'The released ball falls into the water; the impact and rising splash are shown in deliberate slow motion.', playback='slow_motion')],
}


def native_graph():
    graph = json.loads((ROOT / 'workflows/comfyui_h3/pika-h3-ref2va-int8.api.json').read_text())
    graph['11']['inputs']['prompt'] = (
        'subject_definitions: <Subject 1> is the adult in <Picture 1>.\n'
        'summary: [reference generation] [Shot 1] An adult beside a table.\n'
        'retention_analysis: Keep identity and clothing.\n'
        'detailed_description: [Shot 1] Fixed medium-wide composition in a quiet room.\n'
        'overall_soundscape: Room ambience and sounds from the described actions.\n'
        'non_diegetic_music: N/A')
    return graph


def omni_job():
    return dict(shot_id='timing-test', preset='h3-omni-int8', reference_images=['actor.png'],
                prompt=native_graph()['11']['inputs']['prompt'], duration_seconds=5,
                width=128, height=128, seed=19)


class ActionTimingContracts(unittest.TestCase):
    def test_authored_variety_and_mixed_phases_survive_actual_native_graph(self):
        for name, beats in CASES.items():
            with self.subTest(case=name):
                graph = native_graph()
                original = copy.deepcopy(graph)
                compiled, report = timing.compile_api(graph, dict(action_beats=beats))
                prompt = compiled['11']['inputs']['prompt']
                dynamic = prompt.split('detailed_description:', 1)[1].split('overall_soundscape:', 1)[0]
                self.assertEqual(graph, original)
                self.assertEqual(len(report['action_beats']), len(beats))
                for source, actual in zip(beats, report['action_beats']):
                    self.assertEqual((actual['start_seconds'], actual['end_seconds']),
                                     (source['start_seconds'], source['end_seconds']))
                    self.assertEqual(actual['description'], source['description'])
                    self.assertEqual(dynamic.count(source['description']), 1)
                    self.assertIn(f"From about {float(source['start_seconds'])}s to {float(source['end_seconds'])}s:", dynamic)
                self.assertEqual(prompt.count('[Shot 1]'), original['11']['inputs']['prompt'].count('[Shot 1]'))
                self.assertNotIn('<d>', prompt)
                for key in graph:
                    if key != '11':
                        self.assertEqual(compiled[key], graph[key])
                for key in graph['11']['inputs']:
                    if key not in ('length', 'prompt'):
                        self.assertEqual(compiled['11']['inputs'][key], graph['11']['inputs'][key])
                self.assertEqual(compiled['11']['inputs']['length'], report['native_frames'])
                if name == 'intentional-slow-motion':
                    self.assertEqual(report['action_beats'][0]['playback'], 'slow_motion')
                    self.assertNotIn('not slowed playback', dynamic)
                else:
                    self.assertTrue(all(b['playback'] == 'real_time' for b in report['action_beats']))

    def test_clip_padding_camera_and_dialogue_do_not_retime_fast_event(self):
        base = BASE.replace('Keep the same identity, room and camera.', 'A slow camera push-in; quiet contemplative mood.')
        spec = dict(action_beats=CASES['reflex'], utterances=[dict(speaker='Narrator', text='The day continues.',
                    voice_mode='narration', measured_utterance_seconds=3.2)])
        reports = [timing.plan_timing(dict(spec, clip_seconds=seconds)) for seconds in (5, 12, 15)]
        for report in reports:
            prompt = timing.pacing_prompt(base, report)
            self.assertEqual(report['action_beats'], reports[0]['action_beats'])
            self.assertEqual(report['utterances'], reports[0]['utterances'])
            self.assertEqual(prompt.count('The day continues.'), 1)
            self.assertIn('A slow camera push-in; quiet contemplative mood.', prompt)
        longer = copy.deepcopy(spec)
        longer['utterances'][0]['measured_utterance_seconds'] = 10
        report = timing.plan_timing(longer)
        self.assertGreater(report['requested_duration_seconds'], 10)
        self.assertEqual(report['action_beats'], reports[0]['action_beats'])

    def test_action_end_is_latest_parallel_endpoint_not_sum_or_speech_lead(self):
        beats = [beat(0, 6, 'A walks normally.'), beat(1, 4, 'B slowly opens the case.')]
        report = timing.plan_timing(dict(action_beats=beats))
        self.assertEqual(report['action_end_seconds'], 6)
        self.assertEqual(report['required_content_seconds'], 6.35)
        self.assertEqual(report['requested_duration_seconds'], 7)
        self.assertEqual(report['action_beats'][0]['start_seconds'], 0)
        self.assertEqual(timing.plan_timing(dict(action_beats=beats, action_end_seconds=8))['action_end_seconds'], 8)

    def test_invalid_or_overlong_windows_fail_instead_of_squeezing(self):
        bad = [None, {}, [None], [beat(-1, 1, 'Move.')], [beat(1, 1, 'Move.')],
               [beat(2, 1, 'Move.')], [beat(0, True, 'Move.')], [beat(0, float('inf'), 'Move.')],
               [beat(float('nan'), 1, 'Move.')], [beat(0, 1, '')], [beat(0, 1, 'Move.', rate=2)],
               [beat(0, 1, 'Move.', playback='fast')], [beat(1, 2, 'A.'), beat(0, 1, 'B.')],
               [beat(0, 1, '<d>Hi</d>')], [beat(0, 1, '@{character:unresolved/view/front} moves.')],
               [beat(0, 16, 'Move.')]]
        for value in bad:
            with self.subTest(value=value), self.assertRaises(ValueError):
                timing.plan_timing(dict(action_beats=value))
        with self.assertRaisesRegex(ValueError, 'too short'):
            timing.plan_timing(dict(action_beats=[beat(2, 6, 'Move.')], clip_seconds=5))
        report = timing.plan_timing(dict(action_beats=CASES['reflex']))
        prompt = timing.pacing_prompt(BASE, report)
        with self.assertRaisesRegex(ValueError, 'already contains action timing'):
            timing.pacing_prompt(prompt, report)

    def test_plain_slow_action_and_explicit_slow_motion_can_share_one_shot(self):
        beats = [beat(0, 1, 'She slowly opens her hand.'),
                 beat(1, 3, 'The released petal drifts down.', playback='slow_motion'),
                 beat(3, 4, 'She turns away at ordinary speed.')]
        report = timing.plan_timing(dict(action_beats=beats))
        prompt = timing.pacing_prompt(BASE, report)
        self.assertEqual([b['playback'] for b in report['action_beats']], ['real_time', 'slow_motion', 'real_time'])
        self.assertEqual(prompt.count('Intentional slow-motion presentation in this window only'), 1)
        self.assertEqual(prompt.count('not slowed playback'), 2)

    def test_submillisecond_target_not_rounded_to_zero_length_text(self):
        report = timing.plan_timing(dict(action_beats=[beat(1.0001, 1.0002, 'A tiny flash.')]))
        self.assertIn('1.0001s to 1.0002s', timing.pacing_prompt(BASE, report))

    def test_absent_beats_preserve_legacy_prompt_and_duration(self):
        spec = dict(action_end_seconds=3)
        report = timing.plan_timing(spec)
        self.assertEqual(timing.pacing_prompt(BASE, report), BASE)
        self.assertEqual(report['requested_duration_seconds'], 5)
        self.assertEqual(omni.graph_for_job(omni_job())['11']['inputs']['prompt'], omni_job()['prompt'])


class StudioActionIntegration(unittest.TestCase):
    def compile(self, plan, root):
        workflow.write_json(root / 'plan.json', plan)
        return workflow.compile_job(root, 's01')

    def test_native_and_silent_prepare_emit_actions_and_content_identity(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for audio in ('native', 'none'):
                with self.subTest(audio=audio):
                    plan = studio_plan()
                    shot = plan['shots'][0]
                    shot.update(audio=audio, duration_seconds='auto', dialogue_timing=dict(action_beats=CASES['quiet-surprise']))
                    job = self.compile(plan, root)
                    self.assertEqual(job['shot']['duration_seconds'], 5)
                    self.assertEqual(job['shot']['model_frames'], 124)
                    self.assertIn(CASES['quiet-surprise'][1]['description'], job['shot']['prompt'])
                    shot['dialogue_timing']['action_beats'] = copy.deepcopy(CASES['reflex'])
                    self.assertNotEqual(job['job_digest'], self.compile(plan, root)['job_digest'])

    def test_actual_h3_adapter_passes_compiled_windows_to_provider_unchanged(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            plan = studio_plan()
            plan['shots'][0]['dialogue_timing']['action_beats'] = copy.deepcopy(CASES['reflex'])
            job = self.compile(plan, root)
            captured = {}
            class FakeAudio:
                shape = (2, 12 * 32000)
                def __getitem__(self, key):
                    return self
            def pipe(**kwargs):
                captured.update(kwargs)
                return [None] * kwargs['num_frames'], FakeAudio()
            # Exercise the real render method without construction/model loading.
            backend = backends.H3Backend.__new__(backends.H3Backend)
            backend.pipe = pipe
            backend.settings = job['settings']
            backend.config = dict(task_mode='fl2va', steps=8, precision='nf4_pruned', video_shift=3, audio_shift=6)
            backend.namespace = dict(torch=SimpleNamespace(inference_mode=nullcontext, cuda=SimpleNamespace(synchronize=lambda: None)),
                                     REVISIONS={}, write_video_audio=lambda **kwargs: None)
            backend.render(job['shot'], {}, root / 'stub-output')
            self.assertEqual(captured['prompt'], job['shot']['prompt'])
            self.assertEqual(captured['num_frames'], job['shot']['model_frames'])
            self.assertIn('0.4s to 0.7s', captured['prompt'])

    def test_silent_wan_uses_native_clock_and_plain_prompt_not_h3_fields(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            plan = studio_plan()
            plan['settings']['backend'] = 'wan22-ti2v'
            shot = plan['shots'][0]
            shot.update(audio='none', prompt='A fixed medium shot beside the table.', duration_seconds='auto',
                        dialogue_timing=dict(action_beats=CASES['reflex']))
            job = self.compile(plan, root)
            self.assertEqual(job['shot']['duration_seconds'], 1.0833333333333333)
            self.assertEqual(job['shot']['output_frames'], 26)
            self.assertNotIn('overall_soundscape', job['shot']['prompt'])
            self.assertIn(CASES['reflex'][0]['description'], job['shot']['prompt'])
            shot['dialogue_timing']['utterances'] = [dict(speaker='A', text='Hi.')]
            with self.assertRaisesRegex(ValueError, 'requires native H3'):
                self.compile(plan, root)

    def test_imported_audio_keeps_recorded_timing_while_actions_reach_prompt(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            plan, import_spec = audio_fixture(root)
            import audio_artifacts
            workflow.write_json(root / 'assets/dialogue.json', audio_artifacts.create_artifact(root, plan, import_spec))
            first = self.compile(plan, root)
            plan['shots'][0]['dialogue_timing']['action_beats'] = copy.deepcopy(CASES['reflex'])
            changed = self.compile(plan, root)
            self.assertEqual(first['shot']['audio_timeline'], changed['shot']['audio_timeline'])
            self.assertEqual(first['shot']['dialogue_timing_result']['utterances'], changed['shot']['dialogue_timing_result']['utterances'])
            self.assertEqual(changed['shot']['duration_seconds'], 5)
            self.assertIn(CASES['reflex'][0]['description'], changed['shot']['prompt'])
            self.assertNotIn('<d>', changed['shot']['prompt'])
            self.assertNotEqual(first['job_digest'], changed['job_digest'])

    def test_action_only_timing_cannot_truncate_unmeasured_separate_audio(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            wav = root / 'long.wav'
            with wave.open(str(wav), 'wb') as stream:
                stream.setparams((1, 2, 8000, 80000, 'NONE', 'not compressed'))
                stream.writeframes(b'\0\0' * 80000)  # Real 10 s PCM, no speech claim.
            plan = studio_plan()
            plan['assets']['long-audio'] = dict(path='long.wav', role='audio', status='ready', source='synthetic')
            plan['shots'][0].update(audio='separate', inputs={'audio_track': 'long-audio'},
                                   duration_seconds='auto', dialogue_timing=dict(action_beats=CASES['reflex']))
            with self.assertRaisesRegex(ValueError, 'imported audio_artifact'):
                self.compile(plan, root)

    def test_action_reference_tokens_resolve_against_actual_input_order(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            plan = studio_plan()
            plan.update(catalog())
            for asset in plan['assets'].values():
                path = root / asset['path']; path.parent.mkdir(exist_ok=True); path.write_bytes(b'fixture-image')
            shot = plan['shots'][0]
            shot['inputs'] = {'first_frame': '@{character:mei/coat/side}'}
            shot['prompt'] = 'Official alignment. ' + BASE
            shot['dialogue_timing'] = dict(action_beats=[beat(0, 1, '@{character:mei/coat/side} catches the key quickly.')])
            shot['criteria'] += [dict(id=k, kind=k, requirement=k) for k in ('identity', 'wardrobe')]
            job = self.compile(plan, root)
            self.assertIn('<Picture 1> catches the key quickly.', job['shot']['prompt'])
            self.assertNotIn('@{', job['shot']['prompt'])
            shot['dialogue_timing']['action_beats'][0]['description'] = '@{prop:key/closed/front} drops.'
            with self.assertRaisesRegex(ValueError, 'matching actual image input'):
                self.compile(plan, root)


class OmniActionIntegration(unittest.TestCase):
    def test_compile_job_public_cli_then_real_adapter_and_offline_package(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = omni_job()
            source.update(duration_seconds=12, dialogue_timing=dict(action_beats=CASES['quiet-surprise']))
            path, output, report_path = root / 'source.json', root / 'shot.json', root / 'timing.json'
            path.write_text(json.dumps(source))
            cmd = [sys.executable, str(SCRIPTS / 'dialogue_timing.py'), 'compile-job', '--input', str(path),
                   '--output', str(output), '--report', str(report_path)]
            run = subprocess.run(cmd, capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, run.stderr)
            compiled = json.loads(output.read_text())
            self.assertNotIn('dialogue_timing', compiled)
            self.assertEqual(json.loads(path.read_text()), source)
            self.assertEqual(compiled['duration_seconds'], 12)
            for key in source.keys() - {'prompt', 'duration_seconds', 'dialogue_timing'}:
                self.assertEqual(compiled[key], source[key])
            graph = omni.graph_for_job(compiled)
            self.assertEqual(graph['11']['inputs']['prompt'], compiled['prompt'])
            self.assertEqual(graph['11']['inputs']['length'], json.loads(report_path.read_text())['native_frames'])
            image = root / 'actor.png'; image.write_bytes(b'nonempty input fixture, not decoded or generated')
            package = root / 'package'
            bootstrap.prepare(ROOT / 'scripts/colab_omni_runtime', output, {'actor.png': image}, package)
            bootstrap.inspect_package(package / 'deployment.zip')
            with zipfile.ZipFile(package / 'deployment.zip') as archive:
                self.assertEqual(json.loads(archive.read('workflow.api.json')), graph)
                self.assertEqual(json.loads(archive.read('first-job.json')), compiled)
            before = output.read_bytes()
            self.assertNotEqual(subprocess.run(cmd, capture_output=True).returncode, 0)
            self.assertEqual(output.read_bytes(), before)

    def test_raw_metadata_and_conflicting_duration_cannot_be_silently_dropped(self):
        job = omni_job()
        job['dialogue_timing'] = dict(action_beats=CASES['reflex'])
        with self.assertRaisesRegex(ValueError, 'compile-job'):
            omni.graph_for_job(job)
        job['dialogue_timing']['clip_seconds'] = 12
        with self.assertRaisesRegex(ValueError, 'conflict'):
            timing.compile_omni_job(job)
        job['duration_seconds'] = 'auto'
        compiled, report = timing.compile_omni_job(job)
        self.assertEqual(compiled['duration_seconds'], 12)
        self.assertEqual(report['action_beats'][0]['end_seconds'], .7)
        with self.assertRaisesRegex(ValueError, 'requires an Omni job with'):
            timing.compile_omni_job(compiled)


if __name__ == '__main__':
    unittest.main()
