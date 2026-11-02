"""Runnable offline example: reference/audio import -> existing Studio -> edit/SRT.

The images and tones are synthetic contract fixtures, not generated people or
speech. No model/API runs, and no listening/visual-content approval is claimed.
"""
import copy
import json
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import wave
import zlib

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / 'skills/colab-video-studio/scripts'
sys.path.insert(0, str(SCRIPTS))
import audio_artifacts
import media
import workflow
from test_dialogue_timing import studio_plan
from test_reference_resolver import catalog


def png(path):
    def chunk(kind, payload):
        return struct.pack('>I', len(payload)) + kind + payload + struct.pack('>I', zlib.crc32(kind + payload) & 0xffffffff)
    path.write_bytes(b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', 128, 128, 8, 2, 0, 0, 0))
                     + chunk(b'IDAT', zlib.compress((b'\0' + b'\xff\0\0' * 128) * 128)) + chunk(b'IEND', b''))


def fixture(root):
    (root / 'assets').mkdir()
    plan = studio_plan()
    plan.update(catalog())
    plan['settings'].update(task_mode='ref2va')
    for asset in plan['assets'].values():
        png(root / asset['path'])
    wav = root / 'assets/dialogue.wav'
    with wave.open(str(wav), 'wb') as stream:
        stream.setparams((1, 2, 8000, 40000, 'NONE', 'not compressed'))
        # A quiet square-wave tone, not speech. Timing labels are test data.
        stream.writeframes(b''.join(struct.pack('<h', 400 if index % 32 < 16 else -400) for index in range(40000)))
    plan['assets']['dialogue'] = dict(path='assets/dialogue.wav', role='audio', status='ready', source='synthetic-test',
                                     audio_artifact='assets/dialogue.json')
    shot = plan['shots'][0]
    shot.update(audio='separate', duration_seconds='auto',
        inputs={'references': ['@{scene:room/night/wide}', '@{character:mei/coat/side}', '@{prop:key/closed/front}'],
                'audio_track': 'dialogue'},
        prompt='subject_definitions: @{character:mei/coat/side} with @{prop:key/closed/front}.\n'
               'summary: [reference generation] [Shot 1] Character waits in @{scene:room/night/wide}.\n'
               'retention_analysis: Keep supplied character, room and key.\n'
               'detailed_description: [Shot 1] A still medium shot.\n'
               'overall_soundscape: Separate supplied audio.\nnon_diegetic_music: N/A',
        dialogue_timing={'utterances': [{'id': 'u1', 'speaker_ref': 'mei', 'text': 'Test line.'}]})
    shot['criteria'] += [dict(id=kind, kind=kind, requirement='Synthetic '+kind) for kind in ('identity', 'wardrobe')]
    shot['qa']['event_windows'] = [dict(criterion='action', start=1, end=2, fps=8)]
    spec = dict(asset_id='dialogue', utterances=[dict(id='u1', character_id='mei', voice_id='mei-voice',
                text='Test line.', start_seconds=1, end_seconds=2)],
                alignment=dict(method='manual', provenance='Synthetic fixture labels, not speech recognition or listening proof.',
                    sentences=[dict(utterance_id='u1', text='Test line.', start_seconds=1, end_seconds=2)], words=[]))
    workflow.write_json(root / 'plan.json', plan)
    workflow.write_json(root / 'import.json', spec)
    return plan, spec


@unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe'), 'FFmpeg/ffprobe required')
class SharedDialogueIntegration(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.plan, self.spec = fixture(self.root)
        self.cli('audio-import', '--file', str(self.root / 'import.json'), '--output', 'assets/dialogue.json')

    def cli(self, command, *args, success=True):
        result = subprocess.run([sys.executable, str(SCRIPTS / 'studio.py'), command, '--project', str(self.root), *args],
                                capture_output=True, text=True)
        if success:
            self.assertEqual(result.returncode, 0, result.stderr)
            return json.loads(result.stdout)
        self.assertNotEqual(result.returncode, 0)
        return result.stderr

    def test_public_import_prepare_pack_edit_and_caption_use_one_audio_clock(self):
        old_manifest = (self.root / 'assets/dialogue.json').read_bytes()
        self.assertIn('FileExistsError', self.cli('audio-import', '--file', str(self.root / 'import.json'),
                                                '--output', 'assets/dialogue.json', success=False))
        self.assertEqual((self.root / 'assets/dialogue.json').read_bytes(), old_manifest)
        self.cli('prepare')
        job = workflow.read_json(self.root / 'jobs/s01.json')
        self.assertEqual(job['shot']['inputs']['references'], ['room-wide', 'mei-side', 'key-front'])
        self.assertEqual(job['shot']['duration_seconds'], 5)
        self.assertIn('<Picture 2>', job['shot']['prompt'])
        self.assertNotIn('Test line.', job['shot']['prompt'])  # separate audio is not native speech prompting
        self.assertEqual(job['shot']['audio_timeline']['audio']['frame_count'], 40000)
        self.assertNotIn('voice_mode', job['shot']['dialogue_timing_result']['utterances'][0])
        self.assertIn('not detected speech', job['shot']['dialogue_timing_result']['utterances'][0]['basis'])
        self.cli('audio-srt', '--shot', 's01', '--output', 'subtitles/source.srt')
        self.assertIn('00:00:01,000 --> 00:00:02,000', (self.root / 'subtitles/source.srt').read_text())
        attempt = self.cli('reserve', '--shot', 's01')['attempt']
        directory = self.root / 'attempts' / attempt
        self.assertEqual(workflow.sha256(directory / 'input/assets/dialogue.wav'), workflow.sha256(self.root / 'assets/dialogue.wav'))
        (directory / 'result').mkdir()
        video = directory / 'result/video.mp4'
        subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', 'color=c=red:s=128x128:r=24:d=5',
                        '-i', str(self.root / 'assets/dialogue.wav'), '-map', '0:v:0', '-map', '1:a:0',
                        '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-t', '5', str(video)], check=True)
        workflow.write_json(directory / 'result/receipt.json', dict(status='generated', fixture='no model was run',
            attempt_id=attempt, job_digest=job['job_digest'], video_sha256=workflow.sha256(video)))
        workflow.write_json(self.root / 'selection.json', {'s01': attempt})
        workflow.write_json(self.root / 'edits.json', {'s01': dict(start=.5, end=4.5, duration_seconds=2)})
        self.cli('edit-prepare', '--selection', str(self.root / 'selection.json'), '--edits', str(self.root / 'edits.json'), '--run', 'cut')
        self.cli('audio-srt', '--shot', 's01', '--run', 'cut', '--output', 'subtitles/cut.srt')
        srt = self.root / 'subtitles/cut.srt'
        self.assertIn('00:00:00,250 --> 00:00:00,750', srt.read_text())
        edited = self.root / 'edits/cut/segments/s01/result/video.mp4'
        self.assertAlmostEqual(float(media.probe(edited)['format']['duration']), 2, places=1)
        captioned = self.root / 'captioned.mp4'
        caption = ROOT / 'skills/ffmpeg-skill/scripts/caption.py'
        result = subprocess.run([sys.executable, str(caption), str(edited), '--srt', str(srt), '--mode', 'mux',
                                 '--min-duration', '0', '--output', str(captioned), '--json'], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        info = media.probe(captioned)
        self.assertEqual({stream['codec_type'] for stream in info['streams']}, {'video', 'audio', 'subtitle'})
        extracted = subprocess.run(['ffmpeg', '-v', 'error', '-i', str(captioned), '-map', '0:s:0', '-f', 'srt', '-'],
                                   check=True, capture_output=True, text=True).stdout
        self.assertIn('00:00:00,250 --> 00:00:00,750', extracted)
        self.assertFalse((self.root / 'deliverables/final.mp4').exists())  # no invented QA release
        frozen = [edited, self.root / 'edits/cut/recipe.json', self.root / 'edits/cut/segments/s01/job.json',
                  self.root / 'edits/cut/segments/s01/receipt.json']
        hashes = [workflow.sha256(path) for path in frozen]
        self.spec['alignment']['sentences'][0].update(start_seconds=1.1, end_seconds=1.9)
        workflow.write_json(self.root / 'assets/dialogue.json', audio_artifacts.create_artifact(self.root, self.plan, self.spec))
        self.cli('audio-srt', '--shot', 's01', '--run', 'cut', '--output', 'subtitles/corrected.srt')
        self.assertIn('00:00:00,300 --> 00:00:00,700', (self.root / 'subtitles/corrected.srt').read_text())
        self.assertEqual(hashes, [workflow.sha256(path) for path in frozen])
        edited_job = workflow.read_json(frozen[2])
        edited_job['shot']['audio_timeline']['utterances'][0]['text'] = 'Tampered frozen metadata'
        workflow.write_json(frozen[2], edited_job)
        self.assertIn('digest', self.cli('audio-srt', '--shot', 's01', '--run', 'cut',
                                       '--output', 'subtitles/tampered.srt', success=False))

    def test_alignment_only_changes_reuse_video_identity_but_stale_speech_fails(self):
        first = workflow.compile_job(self.root, 's01')
        revised_spec = copy.deepcopy(self.spec)
        revised_spec['alignment']['sentences'][0].update(start_seconds=1.1, end_seconds=1.9)
        workflow.write_json(self.root / 'assets/dialogue.json', audio_artifacts.create_artifact(self.root, self.plan, revised_spec))
        self.plan['characters'][0]['aliases'].append('Unused name')
        self.plan['voices'][0]['description'] = 'Editorial prose, not a new recorded voice'
        workflow.write_json(self.root / 'plan.json', self.plan)
        revised = workflow.compile_job(self.root, 's01')
        self.assertEqual(first['job_digest'], revised['job_digest'])
        self.assertNotEqual(first['shot']['audio_timeline']['alignment_digest'], revised['shot']['audio_timeline']['alignment_digest'])
        self.plan['shots'][0]['dialogue_timing']['utterances'][0]['text'] = 'Changed line.'
        workflow.write_json(self.root / 'plan.json', self.plan)
        with self.assertRaisesRegex(ValueError, 'text, speaker or voice'):
            workflow.compile_job(self.root, 's01')
        self.plan['shots'][0].pop('dialogue_timing')
        workflow.write_json(self.root / 'plan.json', self.plan)
        with self.assertRaisesRegex(ValueError, 'requires dialogue_timing'):
            workflow.compile_job(self.root, 's01')

    def test_separate_audio_rejects_unsupported_acting_instead_of_silently_dropping_it(self):
        for field, value in (('voice_mode', 'inner'), ('delivery', 'Fearful whisper'), ('rate_multiplier', 1.2)):
            plan = copy.deepcopy(self.plan)
            plan['shots'][0]['dialogue_timing']['utterances'][0][field] = value
            workflow.write_json(self.root / 'plan.json', plan)
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, 'shot.prompt'):
                workflow.compile_job(self.root, 's01')

    def test_audio_source_race_cannot_publish_a_mixed_snapshot(self):
        original = audio_artifacts.bind_timing
        def mutate_after_measurement(*args):
            result = original(*args)
            path = self.root / 'assets/dialogue.wav'
            data = bytearray(path.read_bytes()); data[-1] ^= 1; path.write_bytes(data)
            return result
        with patch.object(audio_artifacts, 'bind_timing', side_effect=mutate_after_measurement):
            with self.assertRaisesRegex(ValueError, 'between artifact validation and input snapshot'):
                workflow.compile_job(self.root, 's01')

    def test_source_plan_cannot_inject_an_unvalidated_compiled_timeline(self):
        timeline = workflow.compile_job(self.root, 's01')['shot']['audio_timeline']
        shot = self.plan['shots'][0]
        shot.update(audio_timeline=timeline, duration_seconds=5)
        shot.pop('dialogue_timing')
        self.plan['assets']['dialogue'].pop('audio_artifact')
        path = self.root / 'assets/dialogue.wav'
        data = bytearray(path.read_bytes()); data[-1] ^= 1; path.write_bytes(data)
        workflow.write_json(self.root / 'plan.json', self.plan)
        self.assertIn('compiler-owned', self.cli('audio-srt', '--shot', 's01',
                                               '--output', 'subtitles/injected.srt', success=False))


if __name__ == '__main__':
    unittest.main()
