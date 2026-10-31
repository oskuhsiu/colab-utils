#!/usr/bin/env python3
"""Submit one immutable JSON job once; recover through status.py --fetch."""
import argparse
import json
from pathlib import Path
import traceback
import uuid
from common import (PRODUCTION, PromptExecutionError, PromptTimeoutError, bounded_wait,
                    finish, graph_for_job, hardware, marker, now, remaining, shot_id,
                    snapshot_references, workspace, write_json)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--job', default=str(PRODUCTION / 'job.json'))
    parser.add_argument('--deadline-utc')
    args = parser.parse_args()
    job = json.loads(Path(args.job).read_text())
    deadline = args.deadline_utc or job.get('deadline_utc')
    remaining(deadline)
    graph = graph_for_job(job)
    timeout = bounded_wait(job.get('timeout_seconds', 1800), deadline)
    hardware()
    ws = workspace()
    if ws.status()['server'] != 'ready':
        raise RuntimeError('Start the workspace and confirm the server is ready first')
    queue = ws.client.get_json('/queue')
    if queue.get('queue_running') or queue.get('queue_pending'):
        raise RuntimeError('Queue is not empty; inspect existing work before submitting')
    ws.client.validate_graph(graph)
    directory = PRODUCTION / 'shots' / shot_id(job['shot_id'])
    directory.mkdir(parents=True, exist_ok=False)  # Same shot can never requeue silently.
    write_json(directory / 'job.json', job, immutable=True)
    write_json(directory / 'workflow.api.json', graph, immutable=True)
    snapshot_references(ws, job, directory)
    identity = str(uuid.uuid4())
    receipt = {'shot_id': job['shot_id'], 'prompt_id': identity, 'status': 'prepared', 'created_utc': now(),
               'deadline_utc': deadline, 'media_validation': 'not_run', 'content_review': 'not_run',
               'reference_count': len(job['reference_images']), 'preset': 'h3-omni-int8', 'steps': 8,
               'attention': 'native_dense', 'extensions': []}
    write_json(directory / 'prompt-id.json', {'prompt_id': identity}, immutable=True)
    write_json(directory / 'receipt.json', receipt)
    marker('SHOT_PREPARED', shot_id=job['shot_id'], prompt_id=identity, receipt=str(directory / 'receipt.json'))
    try:
        # Check immediately before submission. No retries, including lost HTTP responses.
        timeout = bounded_wait(timeout, deadline)
        receipt.update(status='submitting', submitted_utc=now())
        write_json(directory / 'receipt.json', receipt)
        response = ws.client.queue_prompt(graph, prompt_id=identity)
        write_json(directory / 'submission.json', response, immutable=True)
        if response['prompt_id'] != identity:
            raise RuntimeError('Unexpected prompt identity; inspect original queue/history')
        receipt['status'] = 'queued'
        write_json(directory / 'receipt.json', receipt)
        marker('SHOT_QUEUED', shot_id=job['shot_id'], prompt_id=identity)
        last_print = [0]
        def on_status(value):
            write_json(directory / 'live-status.json', {'utc': now(), **value})
            if value['elapsed_seconds'] - last_print[0] >= 60:
                marker('SHOT_PROGRESS', shot_id=job['shot_id'], prompt_id=identity,
                       state=value['state'], elapsed_seconds=round(value['elapsed_seconds']))
                last_print[0] = value['elapsed_seconds']
        history = ws.client.wait_prompt(identity, timeout=bounded_wait(timeout, deadline), on_status=on_status)
        receipt.update(status='execution_complete', execution_completed_utc=now())
        write_json(directory / 'receipt.json', receipt)
        finish(ws, directory, history)
    except PromptExecutionError as error:
        write_json(directory / 'history.json', error.history)
        receipt.update(status='execution_failed', error_type=type(error).__name__)
        write_json(directory / 'receipt.json', receipt)
        marker('SHOT_FAILED', shot_id=job['shot_id'], prompt_id=identity, status=receipt['status'])
        raise
    except BaseException as error:
        # If execution completed but media validation failed, preserve that distinction.
        current = json.loads((directory / 'receipt.json').read_text())
        if current['status'] in ('execution_complete', 'complete_media_verified'):
            state = 'media_validation_or_packaging_failed'
        elif isinstance(error, (PromptTimeoutError, TimeoutError)):
            state = 'timeout_may_be_running' if current['status'] != 'prepared' else 'deadline_before_submission'
        else:
            state = 'submission_or_connection_unknown'
        current.update(status=state, error_type=type(error).__name__, error=str(error), updated_utc=now())
        write_json(directory / 'receipt.json', current)
        marker('SHOT_NEEDS_INSPECTION', shot_id=job['shot_id'], prompt_id=identity, status=state,
               receipt=str(directory / 'receipt.json'))
        raise


if __name__ == '__main__':
    try:
        main()
    except BaseException:
        PRODUCTION.mkdir(parents=True, exist_ok=True)
        with (PRODUCTION / 'run-errors.log').open('a') as log:
            traceback.print_exc(file=log)
        raise
