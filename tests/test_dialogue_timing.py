"""Offline pacing contracts; these do not assert how a generated voice sounds."""
import copy
import importlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
SCRIPTS=ROOT/'skills/colab-video-studio/scripts'
sys.path.insert(0,str(SCRIPTS))
import workflow

SHORT='要不要问问他，那张老人照片的事？'
BASE=('integrated_multimodal_description: [Shot 1] A student considers his phone. '
      'Keep the same identity, room and camera.\noverall_soundscape: quiet room\nnon_diegetic_music: N/A')

def studio_plan():
 kinds=['action','framing','style','artifacts','audio']
 return dict(schema_version=1,project_id='pacing-fixture',request={'kind':'stylized','text':'A naturally paced short thought'},
  budget={'max_total_attempts':2,'max_attempts_per_shot':1},delivery={'width':128,'height':128,'fps':24},settings={'backend':'h3'},
  assets={},characters=[],shots=[dict(id='s01',duration_seconds=12,width=128,height=128,seed=1,characters=[],inputs={},audio='native',prompt=BASE,
   start_state={'phone':'held'},end_state={'phone':'held'},criteria=[dict(id=k,kind=k,requirement=k) for k in kinds],
   qa={'event_windows':[dict(criterion='action',start=0,end=1,fps=8)]},
   dialogue_timing={'utterances':[{'speaker':'Yang','text':SHORT,'voice_mode':'inner'}]})])

class CompilerRegression(unittest.TestCase):
 def test_long_explicit_clip_does_not_become_short_lines_speaking_duration(self):
  with tempfile.TemporaryDirectory() as d:
   p=studio_plan();workflow.write_json(Path(d)/'plan.json',p);j=workflow.compile_job(d,'s01')
  self.assertIn('dialogue_timing_result',j['shot'],'Shared compiler silently ignores structured speech timing')
  t=j['shot']['dialogue_timing_result'];self.assertLess(t['utterances'][0]['speech_seconds'],4)
  self.assertEqual(j['shot']['duration_seconds'],12)
  self.assertEqual(j['shot']['prompt'].count(SHORT),1)
  self.assertIn('silent',j['shot']['prompt'])

 def test_existing_jobs_without_timing_keep_their_prompt_and_duration(self):
  with tempfile.TemporaryDirectory() as d:
   p=studio_plan();del p['shots'][0]['dialogue_timing'];workflow.write_json(Path(d)/'plan.json',p);j=workflow.compile_job(d,'s01')
  self.assertEqual(j['shot']['prompt'],BASE);self.assertEqual(j['shot']['duration_seconds'],12)


class TimingContracts(unittest.TestCase):
 def setUp(self):
  self.t=importlib.import_module('dialogue_timing')
 def spec(self,text=SHORT,**values):return dict(utterances=[dict(speaker='Yang',text=text,voice_mode='inner')],**values)
 def test_real_short_line_uses_minimum_clip_without_filling_it(self):
  short=self.t.plan_timing(self.spec());long=self.t.plan_timing(self.spec(clip_seconds=12))
  self.assertEqual(short['requested_duration_seconds'],5);self.assertEqual(short['native_frames'],124)
  self.assertAlmostEqual(short['utterances'][0]['speech_seconds'],long['utterances'][0]['speech_seconds'])
  self.assertLess(short['speech_total_seconds'],4);self.assertGreater(long['remaining_silent_seconds'],8)
 def test_real_medium_and_long_speech_fit_without_filling_long_clip(self):
  examples=[('同学们，有什么疑问，或者遇到古怪的事，可以问我。没有的话，今天的安全讲课到此为止。',12),
            ('没时间了。那东西就在教室门外，不到五米，可能已经盯上我了。我会保持通讯。如果断了，就说明我死了。遗书，请转交给我父母。我要开始行动了。',15)]
  for text,original_clip in examples:
   with self.subTest(text=text):
    auto=self.t.plan_timing(self.spec(text));fixed=self.t.plan_timing(self.spec(text,clip_seconds=original_clip))
    self.assertEqual(auto['speech_total_seconds'],fixed['speech_total_seconds'])
    self.assertLess(auto['requested_duration_seconds'],original_clip)
    self.assertIn(text,self.t.pacing_prompt(BASE,auto))
    self.assertLessEqual(auto['utterances'][0]['end_seconds'],auto['requested_duration_seconds'])
 def test_actions_run_in_parallel_and_turns_reactions_are_explicit(self):
  s=self.spec(action_end_seconds=8,reaction_seconds=.5)
  s['utterances']=[dict(speaker='A',text='好。',pause_after_seconds=.8),dict(speaker='B',text='是。')]
  p=self.t.plan_timing(s);a,b=p['utterances']
  self.assertAlmostEqual(b['start_seconds']-a['end_seconds'],1.0)
  self.assertAlmostEqual(p['required_content_seconds'],8.35);self.assertEqual(p['requested_duration_seconds'],9)
  s['utterances'][1]['not_before_seconds']=10
  self.assertEqual(self.t.plan_timing(s)['utterances'][1]['start_seconds'],10)
 def test_measured_utterance_includes_pauses_and_overrides_text_estimate(self):
  s=self.spec('等一下……真的，沒事嗎？');s['utterances'][0]['measured_utterance_seconds']=2.5
  p=self.t.plan_timing(s);self.assertEqual(p['speech_total_seconds'],2.5);self.assertEqual(p['utterances'][0]['punctuation_pause_seconds'],0)
 def test_rate_is_configurable_without_changing_model_limits(self):
  s=self.spec(policy={'han_units_per_second':4});slow=self.t.plan_timing(s);fast=self.t.plan_timing(self.spec(policy={'han_units_per_second':6}))
  self.assertGreater(slow['speech_total_seconds'],fast['speech_total_seconds']);self.assertEqual(slow['constraints'],fast['constraints'])
 def test_long_dialogue_is_rejected_instead_of_truncated_or_compressed(self):
  with self.assertRaisesRegex(ValueError,'split/re-stage'):self.t.plan_timing(self.spec('這'*90))
  s=self.spec();s['utterances'][0]['measured_utterance_seconds']=14.1
  p=self.t.plan_timing(s);self.assertEqual(p['requested_duration_seconds'],15);self.assertEqual(p['native_frames'],362)
  s['utterances'][0]['measured_utterance_seconds']=14.5
  with self.assertRaisesRegex(ValueError,'split/re-stage'):self.t.plan_timing(s)
 def test_bad_numbers_and_too_short_explicit_duration_fail(self):
  for value in [0,True,float('nan'),float('inf')]:
   with self.subTest(value=value),self.assertRaises(ValueError):self.t.plan_timing(self.spec(policy={'han_units_per_second':value}))
  with self.assertRaises(ValueError):self.t.plan_timing(self.spec(clip_seconds=3))
  with self.assertRaises(ValueError):self.t.plan_timing({'utterances':[None]})
 def test_mixed_language_and_numeric_precision_warning(self):
  p=self.t.plan_timing(self.spec('打開API，wait 2 seconds.'))
  self.assertEqual(p['utterances'][0]['units'],{'han':2,'latin_words':3,'numeric_tokens':1})
  self.assertTrue(p['utterances'][0]['warnings'])
 def test_non_han_latin_script_requires_measurement(self):
  s=self.spec('مرحبا')
  with self.assertRaisesRegex(ValueError,'measured'):self.t.plan_timing(s)
  s['utterances'][0].update(measured_utterance_seconds=1,language='Arabic')
  self.assertEqual(self.t.plan_timing(s)['speech_total_seconds'],1)
 def test_unicode_latin_normalization_and_word_boundaries(self):
  import unicodedata
  text="café Müller l’été co-operate Straße"
  composed=self.t.plan_timing(self.spec(text))
  decomposed=self.t.plan_timing(self.spec(unicodedata.normalize('NFD', text)))
  self.assertEqual(composed['utterances'][0]['units']['latin_words'],5)
  self.assertEqual(composed['speech_total_seconds'],decomposed['speech_total_seconds'])
  self.assertEqual(decomposed['utterances'][0]['text'],unicodedata.normalize('NFD', text))
 def test_unsupported_script_can_use_honest_manual_target(self):
  s=self.spec('مرحبا');line=s['utterances'][0]
  line.update(planned_utterance_seconds=1.3,timing_note='Unmeasured rehearsal target',language='Arabic')
  p=self.t.plan_timing(s)
  self.assertEqual(p['speech_total_seconds'],1.3)
  self.assertIn('not measured',p['utterances'][0]['basis'])
  self.assertTrue(p['utterances'][0]['warnings'])
  line['measured_utterance_seconds']=1.3
  with self.assertRaisesRegex(ValueError,'not both'):self.t.plan_timing(s)
  del line['measured_utterance_seconds'];del line['timing_note']
  with self.assertRaisesRegex(ValueError,'timing_note'):self.t.plan_timing(s)
 def test_explicit_overlap_uses_latest_end_not_last_line_or_sum(self):
  s=dict(timing_mode='explicit',reaction_seconds=.5,utterances=[
   dict(speaker='A',text='A sentence.',start_seconds=.5,measured_utterance_seconds=4),
   dict(speaker='B',text='Yes!',start_seconds=1,measured_utterance_seconds=1)])
  p=self.t.plan_timing(s);a,b=p['utterances']
  self.assertEqual(b['start_seconds'],1)
  self.assertLess(b['start_seconds'],a['end_seconds'])
  self.assertEqual(a['turn_gap_seconds_after'],0)
  self.assertAlmostEqual(p['required_content_seconds'],5.35)
  self.assertEqual(p['requested_duration_seconds'],6)
  self.assertIn('intentionally overlap',self.t.pacing_prompt(BASE,p))
 def test_explicit_zero_start_does_not_inherit_sequential_lead(self):
  p=self.t.plan_timing(dict(timing_mode='explicit',utterances=[dict(speaker='A',text='Hi',start_seconds=0,measured_utterance_seconds=.1)]))
  self.assertAlmostEqual(p['required_content_seconds'],.45)
 def test_explicit_timing_rejects_ambiguous_or_missing_start(self):
  s=self.spec();s['utterances'][0]['start_seconds']=0
  with self.assertRaisesRegex(ValueError,'timing_mode explicit'):self.t.plan_timing(s)
  s['timing_mode']='explicit';s['utterances'][0]['not_before_seconds']=1
  with self.assertRaisesRegex(ValueError,'without not_before'):self.t.plan_timing(s)
  del s['utterances'][0]['not_before_seconds'];del s['utterances'][0]['start_seconds']
  with self.assertRaisesRegex(ValueError,'every line'):self.t.plan_timing(s)
  s['timing_mode']='automatic'
  with self.assertRaisesRegex(ValueError,'sequential or explicit'):self.t.plan_timing(s)
 def test_silent_mouthed_inner_preserves_one_inner_voice_and_mouth_intent(self):
  s=self.spec();s['utterances'][0]['voice_mode']='silent_mouthed_inner'
  p=self.t.plan_timing(s);prompt=self.t.pacing_prompt(BASE,p)
  self.assertEqual(prompt.count(SHORT),1)
  self.assertIn('silently mouths',prompt)
  self.assertIn('no second in-scene spoken voice',prompt)
  self.assertIn('actual model speech can deviate',p['limitations'])
 def test_api_compiler_preserves_models_sampling_references_and_input(self):
  graph=json.loads((ROOT/'workflows/comfyui_h3/pika-h3-ref2va-int8.api.json').read_text());graph['11']['inputs']['prompt']=graph['11']['inputs']['prompt'].replace('No text or dialogue.','No generated text.');original=copy.deepcopy(graph)
  compiled,p=self.t.compile_api(graph,self.spec())
  self.assertEqual(graph,original);self.assertEqual(compiled['11']['inputs']['length'],124)
  self.assertEqual(compiled['11']['inputs']['prompt'].count(SHORT),1);self.assertIn('[Chinese]',compiled['11']['inputs']['prompt'])
  for key in graph:
   if key!='11':self.assertEqual(compiled[key],graph[key])
  for key in graph['11']['inputs']:
   if key not in ('length','prompt'):self.assertEqual(compiled['11']['inputs'][key],graph['11']['inputs'][key])
 def test_conflicting_existing_dialogue_is_not_silently_duplicated(self):
  with self.assertRaisesRegex(ValueError,'already contains'):self.t.pacing_prompt(BASE.replace('A student','<d>[Chinese] 好</d> A student'),self.t.plan_timing(self.spec()))
 def test_public_native_compile_entry_creates_reviewable_immutable_revision(self):
  with tempfile.TemporaryDirectory() as d:
   d=Path(d);inp=d/'timing.json';inp.write_text(json.dumps(self.spec()));out=d/'shot.api.json';report=d/'timing-report.json';base=d/'base.api.json';g=json.loads((ROOT/'workflows/comfyui_h3/pika-h3-ref2va-int8.api.json').read_text());g['11']['inputs']['prompt']=g['11']['inputs']['prompt'].replace('No text or dialogue.','No generated text.');base.write_text(json.dumps(g))
   cmd=[sys.executable,str(SCRIPTS/'dialogue_timing.py'),'compile-api','--input',str(inp),'--workflow',str(base),'--output',str(out),'--report',str(report)]
   run=subprocess.run(cmd,capture_output=True,text=True);self.assertEqual(run.returncode,0,run.stderr)
   self.assertEqual(json.loads(out.read_text())['11']['inputs']['length'],124);self.assertLess(json.loads(report.read_text())['speech_total_seconds'],4)
   content=out.read_bytes();rerun=subprocess.run(cmd,capture_output=True,text=True);self.assertNotEqual(rerun.returncode,0);self.assertEqual(out.read_bytes(),content)
 def test_studio_auto_duration_is_compiled_at_normal_prepare_entry(self):
  with tempfile.TemporaryDirectory() as d:
   p=studio_plan();p['shots'][0]['duration_seconds']='auto';workflow.write_json(Path(d)/'plan.json',p);j=workflow.compile_job(d,'s01')
   self.assertEqual(j['shot']['duration_seconds'],5);self.assertEqual(j['shot']['model_frames'],124)

 def test_silent_starter_cannot_contradict_planned_dialogue(self):
  graph=json.loads((ROOT/'workflows/comfyui_h3/pika-h3-ref2va-int8.api.json').read_text())
  with self.assertRaisesRegex(ValueError,'forbids speech'):self.t.compile_api(graph,self.spec())

if __name__=='__main__':unittest.main()
