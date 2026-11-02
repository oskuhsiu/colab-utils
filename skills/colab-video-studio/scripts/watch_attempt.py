#!/usr/bin/env python3
"""Bounded read-only progress watcher. Not a cost guard or runtime release service.

Run alongside a supervised Studio submit. Each poll has a transport deadline.
Timeout, wrong identity, or missing progress ends monitoring without resubmitting.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import subprocess
import sys
import time
import uuid

from workflow import identifier, read_json, write_json


def observe(project, attempt, timeout=30):
    directory = Path(project).resolve() / 'attempts' / identifier(attempt)
    receipt = read_json(directory / 'receipt.json')
    if not receipt.get('session') or not receipt.get('remote_directory'):
        raise ValueError('Attempt has no recorded submission; watcher never submits work')
    session = identifier(receipt['session'])
    # Download to a separate file so failed polls cannot masquerade as fresh data.
    destination = directory / ('watch-progress.' + uuid.uuid4().hex + '.json')
    destination.unlink(missing_ok=True)
    try:
        subprocess.run(['colab','--auth','oauth2','download','-s',session,
                        receipt['remote_directory'] + '/result/progress.json',str(destination)],
                       check=True, capture_output=True, text=True, timeout=timeout)
        progress = read_json(destination)
        if progress.get('attempt_id') != attempt or progress.get('job_digest') != receipt['job_digest']:
            raise ValueError('Progress identity does not match the recorded attempt')
        return progress
    finally:
        destination.unlink(missing_ok=True)


def watch(project, attempt, *, duration=300, interval=10, poll_timeout=30,
          observer=observe, monotonic=time.monotonic, sleep=time.sleep):
    for name, value in [('duration',duration),('interval',interval),('poll_timeout',poll_timeout)]:
        if type(value) not in (int,float) or not math.isfinite(value) or value <= 0:
            raise ValueError(name + ' must be finite and positive')
    directory=Path(project).resolve()/'attempts'/identifier(attempt)
    if not directory.is_dir():
        raise ValueError('Attempt directory does not exist')
    start=monotonic();observations=0
    while True:
        remaining=duration-(monotonic()-start)
        if remaining <= 0:
            result = {'state':'monitoring_deadline','observations':observations,'runtime_released':False}
            write_json(directory/'watch-state.json',result)
            return result
        try:
            progress=observer(project,attempt,timeout=min(poll_timeout,remaining))
        except (OSError,ValueError,KeyError,subprocess.SubprocessError) as exc:
            result={'state':'needs_reconcile','error_type':type(exc).__name__,
                    'observations':observations,'runtime_released':False}
            write_json(directory/'watch-state.json',result)
            return result
        observations+=1
        result={'observed_utc':datetime.now(timezone.utc).isoformat(),
                'state':progress.get('phase','unknown'),'progress':progress,
                'observations':observations,'runtime_released':False}
        write_json(directory/'watch-state.json',result)
        print(json.dumps(result,ensure_ascii=False),flush=True)
        if result['state'] in ('generated','failed'):
            return result
        remaining=duration-(monotonic()-start)
        if remaining > 0:sleep(min(interval,remaining))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--project',type=Path,required=True);p.add_argument('--attempt',required=True)
    p.add_argument('--duration',type=float,default=300);p.add_argument('--interval',type=float,default=10)
    p.add_argument('--poll-timeout',type=float,default=30)
    args=p.parse_args()
    try:result=watch(args.project,args.attempt,duration=args.duration,interval=args.interval,poll_timeout=args.poll_timeout)
    except (ValueError,OSError) as exc:p.exit(1,str(exc)+'\n')
    print(json.dumps(result,ensure_ascii=False))
    if result['state'] != 'generated':p.exit(2,'Monitoring ended; reconcile/fetch the original attempt and check the runtime. No stop or release was performed.\n')

if __name__=='__main__':main()
