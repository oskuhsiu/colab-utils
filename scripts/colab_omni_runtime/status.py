#!/usr/bin/env python3
"""Inspect original prompt, optionally fetch/validate/package completed media."""
import argparse
import json
from common import PRODUCTION, finish, marker, shot_id, workspace, write_json


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--shot-id')
    parser.add_argument('--fetch', action='store_true')
    args = parser.parse_args()
    if args.fetch and not args.shot_id:
        parser.error('--fetch requires --shot-id')
    ws = workspace()
    state = ws.status()
    marker('SERVER_STATUS', server=state['server'], queue=state.get('queue'))
    if not args.shot_id:
        return
    directory = PRODUCTION / 'shots' / shot_id(args.shot_id)
    receipt = json.loads((directory / 'receipt.json').read_text())
    identity = receipt['prompt_id']
    history = ws.client.get_json('/history/' + identity).get(identity)
    if history:
        write_json(directory / 'history.json', history)
    marker('PROMPT_STATUS', shot_id=args.shot_id, prompt_id=identity,
           receipt_status=receipt['status'], history_status=history.get('status') if history else None)
    if args.fetch:
        status = history.get('status', {}) if history else {}
        if not (status.get('completed') is True and status.get('status_str') == 'success'):
            raise RuntimeError('Original prompt is not successfully completed; nothing requeued')
        finish(ws, directory, history)


if __name__ == '__main__':
    main()
