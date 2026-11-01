"""Exact catalog bindings reach real compiler inputs; no model calls."""
import copy
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'skills/colab-video-studio/scripts'))
import reference_resolver as refs
import workflow
from test_dialogue_timing import studio_plan


def catalog():
    return dict(characters=[dict(id='mei', name='梅', aliases=['Mei'], identity_assets=['mei-front'],
                                references={'coat': {'front': 'mei-front', 'side': 'mei-side'}}, voice_id='mei-voice')],
                scenes=[dict(id='room', name='教室', references={'night': {'wide': 'room-wide'}})],
                props=[dict(id='key', name='鑰匙', references={'closed': {'front': 'key-front'}})],
                voices=[dict(id='mei-voice', name='梅聲線', description='A low, clear adult voice')],
                assets={name: dict(path='assets/'+name+'.png', role='identity' if name.startswith('mei') else 'scene',
                                   source='original', status='ready', derived_from=['mei-front'] if name == 'mei-side' else [])
                        for name in ('mei-front', 'mei-side', 'room-wide', 'key-front')})


class ResolverTests(unittest.TestCase):
    def test_exact_ids_alias_collision_and_no_variant_fallback(self):
        plan = catalog()
        self.assertEqual(refs.lookup(plan, 'character', '@梅')['id'], 'mei')
        self.assertEqual(refs.lookup(plan, 'character', '@Mei')['id'], 'mei')
        self.assertEqual(refs.image_reference(plan, '@{character:mei/coat/side}')['asset_id'], 'mei-side')
        plan['characters'].append(dict(id='other', aliases=['Mei', 'mei']))
        self.assertEqual(refs.lookup(plan, 'character', 'mei')['id'], 'mei')
        with self.assertRaisesRegex(ValueError, 'Ambiguous'):
            refs.lookup(plan, 'character', '@Mei')
        with self.assertRaisesRegex(ValueError, 'Ambiguous'):
            refs.lookup(plan, 'character', '@mei')
        for query in ('@{character:mei/coat/back}', '@{scene:room/day/wide}'):
            with self.assertRaisesRegex(ValueError, 'no fallback'):
                refs.image_reference(plan, query)
        with self.assertRaisesRegex(ValueError, 'Missing'):
            refs.lookup(plan, 'character', 'me')

    def test_order_and_picture_tokens_use_only_actual_inputs(self):
        plan = catalog()
        shot = dict(inputs={'references': ['@{scene:教室/night/wide}', '@{character:梅/coat/side}', '@{prop:key/closed/front}']},
                    prompt='@{character:mei/coat/side} takes @{prop:鑰匙/closed/front} in @{scene:room/night/wide}.')
        before = copy.deepcopy(shot)
        actual = refs.resolve_shot(plan, shot, dict(backend='h3', task_mode='ref2va'))
        self.assertEqual(shot, before)
        self.assertEqual(actual['inputs']['references'], ['room-wide', 'mei-side', 'key-front'])
        self.assertEqual(actual['prompt'], '<Picture 2> takes <Picture 3> in <Picture 1>.')
        self.assertEqual(actual['characters'], ['mei'])
        shot['prompt'] = '@{character:mei/coat/front}'
        with self.assertRaisesRegex(ValueError, 'actual image input'):
            refs.resolve_shot(plan, shot, dict(backend='h3', task_mode='ref2va'))
        shot['prompt'] = '@{prop:key/closed/front}'
        shot['inputs']['references'].append('key-front')
        with self.assertRaisesRegex(ValueError, 'exactly one'):
            refs.resolve_shot(plan, shot, dict(backend='h3', task_mode='ref2va'))

    def test_keyframe_order_and_unsupported_tokens_fail_closed(self):
        plan = catalog()
        shot = dict(inputs={'last_frame': '@{scene:room/night/wide}', 'first_frame': '@{character:mei/coat/front}'},
                    prompt='@{scene:room/night/wide} then @{character:mei/coat/front}')
        resolved = refs.resolve_shot(plan, shot, dict(backend='h3', task_mode='fl2va'))
        self.assertEqual(resolved['prompt'], '<Picture 2> then <Picture 1>')
        with self.assertRaisesRegex(ValueError, 'only by the H3'):
            refs.resolve_shot(plan, shot, dict(backend='wan22-ti2v'))
        shot['prompt'] = '@{unknown:room}'
        with self.assertRaisesRegex(ValueError, 'Malformed'):
            refs.resolve_shot(plan, shot, dict(backend='h3', task_mode='fl2va'))

    def test_compiler_keeps_lineage_and_native_voice_intent_without_catalog_bloat(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            plan = studio_plan()
            plan.update(catalog())
            for asset in plan['assets'].values():
                path = root / asset['path']; path.parent.mkdir(exist_ok=True); path.write_bytes(b'fixture-image')
            shot = plan['shots'][0]
            shot['inputs'] = {'first_frame': '@{character:Mei/coat/side}'}
            shot['prompt'] = 'Official alignment. ' + shot['prompt'].replace('A student', '@{character:mei/coat/side}')
            shot['dialogue_timing']['utterances'] = [{'speaker_ref': '@梅', 'text': '好。'}]
            shot['criteria'] += [dict(id=kind, kind=kind, requirement=kind) for kind in ('identity', 'wardrobe')]
            workflow.write_json(root / 'plan.json', plan)
            first = workflow.compile_job(root, 's01')
            self.assertEqual(first['shot']['inputs'], {'first_frame': 'mei-side'})
            self.assertEqual(set(first['assets']), {'mei-front', 'mei-side'})
            self.assertNotIn('references', first['characters'][0])
            self.assertIn('Voice identity intent: A low, clear adult voice.', first['shot']['prompt'])
            self.assertEqual(first['shot']['dialogue_timing_result']['utterances'][0]['voice_id'], 'mei-voice')
            plan['characters'][0]['aliases'].append('Unused alias')
            plan['characters'][0]['references']['coat']['unused'] = 'unused-file'
            plan['scenes'].append(dict(id='unused-scene', references={}))
            workflow.write_json(root / 'plan.json', plan)
            self.assertEqual(first['job_digest'], workflow.compile_job(root, 's01')['job_digest'])
            plan['assets']['mei-side']['derived_from'] = []
            workflow.write_json(root / 'plan.json', plan)
            with self.assertRaisesRegex(ValueError, 'identity baseline'):
                workflow.compile_job(root, 's01')

    def test_voice_must_exist_and_never_silently_overrides_manual_speaker(self):
        plan = catalog()
        self.assertEqual(refs.voice_binding(plan, '@梅')['voice_id'], 'mei-voice')
        shot = dict(inputs={}, prompt='Scene', dialogue_timing={'utterances': [{'speaker_ref': 'mei', 'speaker': 'Other', 'text': 'Hi'}]})
        with self.assertRaisesRegex(ValueError, 'do not specify both'):
            refs.resolve_shot(plan, shot, {})
        plan['characters'][0]['voice_id'] = 'missing'
        with self.assertRaisesRegex(ValueError, 'Missing voice'):
            refs.voice_binding(plan, 'mei')

    def test_pr1_generation_digest_is_verified_before_semantic_comparison(self):
        for omit_inputs in (False, True):
            with self.subTest(omit_inputs=omit_inputs), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                plan = studio_plan()
                if omit_inputs:
                    plan['shots'][0].pop('inputs')
                workflow.write_json(root / 'plan.json', plan)
                old = workflow.compile_job(root, 's01')
                self.assertEqual('inputs' not in old['shot'], omit_inputs)
                # PR1's exact digest projection: no version tag, timing metadata
                # retained, and optional shot.inputs was allowed to be absent.
                old.pop('generation_digest_version')
                old['generation_digest'] = old['job_digest'] = workflow.generation_digest(old)
                attempt = root / 'attempts' / 'old'
                workflow.write_json(attempt / 'job.json', old)
                self.assertEqual(workflow.verify_current(root, attempt), old)
                old['shot']['dialogue_timing']['utterances'][0]['text'] = 'tampered'
                workflow.write_json(attempt / 'job.json', old)
                with self.assertRaisesRegex(ValueError, 'snapshot changed'):
                    workflow.verify_current(root, attempt)


if __name__ == '__main__':
    unittest.main()
