#!/usr/bin/env python3
"""Offline speech budgets and native H3/Pika API compilation; stdlib only.

Rates are editable planning assumptions, not measured language/model constants.
A measured utterance duration takes precedence and includes its internal pauses.
"""
from __future__ import annotations
import argparse
import copy
import json
import math
from pathlib import Path
import re
import unicodedata

H3_CONSTRAINTS = dict(min_seconds=5, max_seconds=15, step_seconds=1, fps=24,
                      frame_step=17, frame_offset=5)
DEFAULT_POLICY = dict(han_units_per_second=5.0, latin_words_per_second=2.8,
    comma_pause_seconds=0.12, sentence_pause_seconds=0.25, ellipsis_pause_seconds=0.35,
    turn_gap_seconds=0.2, lead_seconds=0.25, tail_seconds=0.35)
MODES = {
    'spoken': 'Audible in-scene speech with matching mouth articulation.',
    'inner': 'Private interior voice; the visible character remains silent without speech articulation; others do not hear it.',
    'offscreen': 'An in-scene offscreen speaker; visible listeners remain silent.',
    'telephone': 'Voice from the telephone earpiece; the visible listener remains silent.',
    'narration': 'Voice-over narration; visible people do not articulate this line.',
}


def number(value, name, *, positive=False):
    if type(value) not in (int, float) or not math.isfinite(value) or value < 0 or (positive and value == 0):
        raise ValueError(f'{name} must be finite and '+('positive' if positive else 'nonnegative'))
    return float(value)


def _han(c):
    return 0x3400 <= ord(c) <= 0x9fff or 0x20000 <= ord(c) <= 0x323af or 0xf900 <= ord(c) <= 0xfaff


def estimate_utterance(line, policy):
    text = line.get('text')
    if not isinstance(text, str) or not text.strip() or '<d>' in text or '</d>' in text:
        raise ValueError('Utterance text must contain only the nonempty intended spoken words')
    mode = line.get('voice_mode', 'spoken')
    if mode not in MODES:
        raise ValueError(f'Unsupported voice_mode: {mode}')
    if not isinstance(line.get('speaker'), str) or not line['speaker'].strip():
        raise ValueError('Each utterance needs a speaker')
    rate = number(line.get('rate_multiplier', 1), 'rate_multiplier', positive=True)
    measured = line.get('measured_utterance_seconds')
    warnings = []
    han = sum(_han(c) for c in text)
    latin = len(re.findall(r"[A-Za-z]+(?:['’-][A-Za-z]+)*", text))
    numerals = len(re.findall(r'\d+(?:[.,]\d+)*', text))
    unknown = [c for c in text if unicodedata.category(c).startswith('L') and not _han(c) and not ('A' <= c <= 'Z' or 'a' <= c <= 'z')]
    # Remove ellipses and numeric punctuation before counting phrase pauses.
    ellipses = len(re.findall(r'…+|\.{3,}', text))
    punctuation = re.sub(r'…+|\.{3,}|\d+(?:[.,]\d+)*', '', text)
    pause = (sum(c in ',，、;；:：' for c in punctuation) * policy['comma_pause_seconds']
             + len(re.findall(r'[.!?。！？]+', punctuation)) * policy['sentence_pause_seconds']
             + ellipses * policy['ellipsis_pause_seconds'])
    if measured is not None:
        speech = number(measured, 'measured_utterance_seconds', positive=True)
        articulation = None
        pause = 0.0  # Already included in the measurement; never count twice.
        basis = 'measured utterance including internal pauses'
    else:
        if unknown:
            raise ValueError('Unsupported writing system: supply measured_utterance_seconds for this line')
        if not han + latin + numerals:
            raise ValueError('No speech units: use a non-speech action/reaction budget instead')
        articulation = han / (policy['han_units_per_second'] * rate) + (latin + numerals) / (policy['latin_words_per_second'] * rate)
        speech = articulation + pause
        basis = 'editable Han-character/Latin-word planning estimate'
        if numerals:
            warnings.append('Numerals/abbreviations need spoken-form text or a measured utterance for precise timing')
    language = line.get('language', 'Chinese' if han else 'English')
    if not isinstance(language, str) or not language.strip() or any(c in language for c in '[]<>\n'):
        raise ValueError('language must be a nonempty language label')
    delivery = line.get('delivery', '')
    if not isinstance(delivery, str):
        raise ValueError('delivery must be text')
    return dict(speaker=line['speaker'], text=text, language=language, voice_mode=mode, delivery=delivery,
        rate_multiplier=rate, units=dict(han=han, latin_words=latin, numeric_tokens=numerals),
        articulation_seconds=articulation, punctuation_pause_seconds=pause,
        speech_seconds=speech, basis=basis, warnings=warnings)


def plan_timing(spec, *, constraints=None):
    """Keep speech targets independent of an explicit long clip or model minimum.

    action_end_seconds is a parallel scene-clock requirement. Sequential actions
    before speech use not_before_seconds; reaction_seconds follows the last line.
    """
    if not isinstance(spec, dict):
        raise ValueError('dialogue_timing must be an object')
    allowed = {'utterances', 'policy', 'action_end_seconds', 'reaction_seconds', 'clip_seconds', 'constraints'}
    if set(spec) - allowed:
        raise ValueError('Unknown timing fields: '+', '.join(sorted(set(spec)-allowed)))
    policy = dict(DEFAULT_POLICY)
    overrides = spec.get('policy', {})
    if not isinstance(overrides, dict) or set(overrides) - set(policy):
        raise ValueError('Unknown speech policy setting')
    policy.update(overrides)
    for name, value in policy.items():
        policy[name] = number(value, name, positive=name.endswith('per_second'))
    limits = dict(H3_CONSTRAINTS)
    if constraints is not None and spec.get('constraints') not in (None, constraints):
        raise ValueError('Timing constraints conflict with the selected model')
    supplied_limits = constraints if constraints is not None else spec.get('constraints', {})
    if not isinstance(supplied_limits, dict):
        raise ValueError('constraints must be an object')
    limits.update(supplied_limits)
    if set(limits) != set(H3_CONSTRAINTS):
        raise ValueError('Unknown model timing constraint')
    for name in ('min_seconds', 'max_seconds', 'step_seconds', 'fps', 'frame_step'):
        limits[name] = number(limits[name], name, positive=True)
    limits['frame_offset'] = number(limits['frame_offset'], 'frame_offset')
    if limits['min_seconds'] > limits['max_seconds'] or any(int(limits[k]) != limits[k] for k in ('fps','frame_step','frame_offset')):
        raise ValueError('Invalid model duration/frame constraints')
    lines = spec.get('utterances', [])
    if not isinstance(lines, list) or any(not isinstance(line, dict) for line in lines):
        raise ValueError('utterances must be an ordered list')
    cursor = policy['lead_seconds'] if lines else 0.0
    utterances = []
    for index, line in enumerate(lines):
        if not isinstance(line, dict):
            raise ValueError('Each utterance must be an object')
        allowed_line = {'speaker','text','language','voice_mode','delivery','rate_multiplier','measured_utterance_seconds','not_before_seconds','pause_after_seconds'}
        if set(line) - allowed_line:
            raise ValueError('Unknown utterance fields: '+', '.join(sorted(set(line)-allowed_line)))
        item = estimate_utterance(line, policy)
        earliest = number(line.get('not_before_seconds', 0), 'not_before_seconds')
        start = max(cursor, earliest)
        item.update(start_seconds=start, end_seconds=start+item['speech_seconds'],
                    pause_after_seconds=number(line.get('pause_after_seconds',0), 'pause_after_seconds'),
                    wait_before_seconds=max(0, earliest-cursor))
        item['turn_gap_seconds_after'] = (policy['turn_gap_seconds'] if index+1 < len(lines) and line['speaker'] != lines[index+1].get('speaker') else 0.0)
        utterances.append(item)
        cursor = item['end_seconds'] + item['pause_after_seconds'] + item['turn_gap_seconds_after']
    action_end = number(spec.get('action_end_seconds',0), 'action_end_seconds')
    reaction = number(spec.get('reaction_seconds',0), 'reaction_seconds')
    content_end = max(action_end, cursor+reaction)
    required = content_end + policy['tail_seconds']
    requested = spec.get('clip_seconds')
    if requested is None:
        requested = max(limits['min_seconds'], math.ceil((required-1e-9)/limits['step_seconds'])*limits['step_seconds'])
    else:
        requested = number(requested, 'clip_seconds', positive=True)
        if abs(requested/limits['step_seconds']-round(requested/limits['step_seconds'])) > 1e-7:
            raise ValueError('Explicit clip_seconds must match the selected model duration step')
    if requested > limits['max_seconds'] or required > limits['max_seconds']+1e-7:
        raise ValueError(f'Content needs {required:.3f}s before model rounding (max {limits["max_seconds"]:g}s); split/re-stage the interaction or revise explicit timing, preserving complete speech')
    if requested < limits['min_seconds'] or requested+1e-7 < required:
        raise ValueError('Clip is too short for complete speech/actions/reaction/tail; do not squeeze the utterances')
    frames = int(limits['frame_offset'] + limits['frame_step'] * max(0, math.ceil((requested*limits['fps']-limits['frame_offset']-1e-9)/limits['frame_step'])))
    native = frames/limits['fps']
    return dict(schema_version=1, policy=policy, constraints=limits, utterances=utterances,
        speech_total_seconds=sum(x['speech_seconds'] for x in utterances),
        action_end_seconds=action_end, reaction_seconds=reaction, required_content_seconds=required,
        requested_duration_seconds=requested, native_frames=frames, native_seconds=native,
        remaining_silent_seconds=max(0,native-content_end),
        limitations='Planning targets and prompt intent only; actual model speech can deviate. Verify naturalness by listening and complete-word ASR/tail checks on future output.')


def pacing_prompt(base_prompt, timing):
    if not timing['utterances']:
        return base_prompt
    if '<d>' in base_prompt or '[Dialogue pacing]' in base_prompt:
        raise ValueError('Base prompt already contains dialogue/timing; move spoken lines to utterances to avoid conflicting or repeated timing')
    if re.search(r'\bno\s+(?:(?:text|subtitles)\s+or\s+)?(?:dialogue|speech)\b', base_prompt, re.I):
        raise ValueError("Base prompt forbids speech; replace the silent starter example with this shot's visual/action-only prompt")
    match = re.search(r'(?m)^\s*overall_soundscape\s*:', base_prompt)
    if not match:
        raise ValueError('A native H3 prompt needs overall_soundscape before adding speech timing')
    lines = ['[Dialogue pacing] Speech follows the soft cadence targets below, independent of video length. Complete each phrase naturally; remaining action, listening and reactions are silent.']
    for item in timing['utterances']:
        lines.append(f"At about {item['start_seconds']:.2f}s, {item['speaker']} delivers this line in about {item['speech_seconds']:.2f}s including internal phrase pauses. {MODES[item['voice_mode']]} {item['delivery']} <d>[{item['language']}] {item['text']}</d>")
        if item['pause_after_seconds']:
            lines.append(f"Then allow {item['pause_after_seconds']:.2f}s of intentional silent pause/reaction.")
    return base_prompt[:match.start()].rstrip()+'\n\n'+'\n'.join(lines)+'\n\n'+base_prompt[match.start():].lstrip()


def compile_api(graph, spec):
    """Copy a native H3/Pika graph; modify only conditioning prompt and length."""
    result = copy.deepcopy(graph)
    nodes = [n for n in result.values() if n.get('class_type') in {'MiniMaxH3ReferenceToVideo','MiniMaxH3ImageToVideo'}]
    if len(nodes) != 1:
        raise ValueError('Expected exactly one native H3 conditioning node')
    if any(n.get('class_type')=='CreateVideo' and n['inputs'].get('fps') != 24 for n in result.values()):
        raise ValueError('Native H3 timing requires CreateVideo at24fps')
    timing = plan_timing(spec, constraints=H3_CONSTRAINTS)
    inputs = nodes[0]['inputs']
    inputs['prompt'] = pacing_prompt(inputs['prompt'],timing)
    inputs['length'] = timing['native_frames']
    return result, timing


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='action',required=True)
    for action in ('plan','compile-api'):
        p = sub.add_parser(action)
        p.add_argument('--input',type=Path,required=True,help='Structured timing JSON')
        if action=='compile-api':
            p.add_argument('--workflow',type=Path,required=True)
            p.add_argument('--output',type=Path,required=True)
            p.add_argument('--report',type=Path,required=True)
    args=parser.parse_args();spec=json.loads(args.input.read_text(encoding='utf-8'))
    if args.action=='plan':
        print(json.dumps(plan_timing(spec),ensure_ascii=False,indent=2));return
    if args.output.resolve() in {args.workflow.resolve(),args.input.resolve()} or args.report.resolve() in {args.workflow.resolve(),args.input.resolve(),args.output.resolve()}:
        parser.error('Keep input, compiled graph and timing report at distinct paths')
    graph,timing=compile_api(json.loads(args.workflow.read_text(encoding='utf-8')),spec)
    for path in (args.output,args.report):
        if path.exists():parser.error('Preserve existing output; choose a new revision: '+str(path))
    for path,value in ((args.output,graph),(args.report,timing)):
        path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'workflow':str(args.output),'timing_report':str(args.report),'requested_seconds':timing['requested_duration_seconds'],'native_seconds':timing['native_seconds']},ensure_ascii=False))

if __name__=='__main__':main()
