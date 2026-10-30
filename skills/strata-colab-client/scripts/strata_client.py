#!/usr/bin/env python3
"""Small credential-safe Strata client. No redirects and no POST retries."""
import argparse
from datetime import datetime, timezone
import json
import http.client
import os
from pathlib import Path
import socket
import ssl
import stat
import sys
import time
import threading
import urllib.parse

MAX_BYTES = 16 * 1024 * 1024

class ClientError(Exception):
    pass

def normalize_base(value):
    p = urllib.parse.urlsplit(value)
    if p.username or p.password or p.query or p.fragment:
        raise ClientError('Base URL must not contain credentials, query, or fragment')
    if not p.hostname or p.path.rstrip('/') != '/v1':
        raise ClientError('Base URL must end in /v1')
    if p.scheme != 'https' and not (p.scheme == 'http' and p.hostname in ('localhost', '127.0.0.1', '::1')):
        raise ClientError('External endpoints require HTTPS')
    return urllib.parse.urlunsplit((p.scheme, p.netloc, '/v1', '', ''))


def load_manifest(path):
    manifest = json.loads(Path(path).read_text(encoding='utf-8'))
    if manifest.get('schema_version') != 1 or manifest.get('api_key_env') != 'STRATA_API_KEY':
        raise ClientError('Unsupported manifest schema or credential contract')
    try:
        expiry = datetime.fromisoformat(manifest['expires_at'].replace('Z', '+00:00'))
        if expiry.tzinfo is None or expiry <= datetime.now(timezone.utc):
            raise ValueError()
    except (KeyError, ValueError, TypeError, AttributeError):
        raise ClientError('Manifest is expired or has an invalid expiry; get a fresh export') from None
    return normalize_base(manifest['base_url'])


def read_key(key_file=None):
    if key_file:
        # Open without following a symlink; check the actual opened file.
        flags = os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0)
        fd = os.open(key_file, flags)
        with os.fdopen(fd, 'r', encoding='utf-8') as f:
            info = os.fstat(f.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_mode & 0o077:
                raise ClientError('Key file must be a regular owner-only file (chmod 600)')
            if hasattr(os, 'getuid') and info.st_uid != os.getuid():
                raise ClientError('Key file must belong to the current user')
            key = f.read(8193).strip()
    else:
        key = os.environ.get('STRATA_API_KEY', '').strip()
    if not key or len(key) > 8192 or any(c.isspace() for c in key):
        raise ClientError('Set STRATA_API_KEY securely or provide an owner-only key file')
    return key


class Client:
    def __init__(self, base_url, key, timeout=60, total_timeout=180):
        self.base = normalize_base(base_url)
        self.key = key
        self.timeout = min(max(float(timeout), 1), 300)
        self.total_timeout = min(max(float(total_timeout), 1), 3600)

    def request(self, operation, payload=None):
        paths = {'health': '/health', 'models': '/v1/models', 'chat': '/v1/chat/completions'}
        if operation not in paths:
            raise ClientError('Unknown operation')
        if operation == 'chat' and not isinstance(payload, dict):
            raise ClientError('Chat needs a JSON object')
        method = 'POST' if operation == 'chat' else 'GET'
        body = json.dumps(payload).encode() if method == 'POST' else None
        target = urllib.parse.urlsplit(self.base)
        headers = {'Authorization': 'Bearer ' + self.key, 'Content-Type': 'application/json',
            'ngrok-skip-browser-warning': '1',
            'Accept': 'text/event-stream' if payload and payload.get('stream') else 'application/json'}
        deadline = time.monotonic() + self.total_timeout
        sockets = []
        connections = []
        expired = threading.Event()

        def abort():
            expired.set()
            for sock in list(sockets):
                try:
                    sock.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass
                try:
                    sock.close()
                except OSError:
                    pass

        def connect_socket(address, timeout, source_address=None):
            # DNS itself has no portable socket timeout; resolve in a daemon and
            # bound the caller's wait. The resolver never receives credentials.
            resolved = []
            errors = []
            ready = threading.Event()
            def resolve():
                try:
                    resolved.extend(socket.getaddrinfo(address[0], address[1], 0, socket.SOCK_STREAM))
                except OSError as e:
                    errors.append(e)
                finally:
                    ready.set()
            threading.Thread(target=resolve, daemon=True).start()
            if not ready.wait(max(0, deadline-time.monotonic())) or expired.is_set():
                raise TimeoutError()
            if errors:
                raise OSError('DNS resolution failed')
            for family, kind, protocol, _, sockaddr in resolved:
                if expired.is_set() or time.monotonic() >= deadline:
                    raise TimeoutError()
                sock = socket.socket(family, kind, protocol)
                sockets.append(sock)
                try:
                    sock.settimeout(min(timeout, max(0.01, deadline-time.monotonic())))
                    if source_address:
                        sock.bind(source_address)
                    sock.connect(sockaddr)
                    sock.settimeout(min(timeout, max(0.01, deadline-time.monotonic())))
                    return sock
                except OSError:
                    sock.close()
            raise OSError('Connection failed')

        timer = threading.Timer(self.total_timeout, abort)
        timer.daemon = True
        timer.start()
        try:
            # GET may retry once. Never duplicate a possibly processed generation.
            for attempt in range(2 if method == 'GET' else 1):
                if expired.is_set() or time.monotonic() >= deadline:
                    raise ClientError('Total request deadline exceeded')
                timeout = min(self.timeout, max(0.01, deadline-time.monotonic()))
                if target.scheme == 'https':
                    conn = http.client.HTTPSConnection(target.hostname, target.port, timeout=timeout,
                                                       context=ssl.create_default_context())
                else:
                    conn = http.client.HTTPConnection(target.hostname, target.port, timeout=timeout)
                conn._create_connection = connect_socket
                connections.append(conn)
                try:
                    conn.connect()
                    sockets.append(conn.sock)
                    if expired.is_set() or time.monotonic() >= deadline:
                        raise ClientError('Total request deadline exceeded')
                    conn.request(method, paths[operation], body=body, headers=headers)
                    response = conn.getresponse()
                    if expired.is_set() or time.monotonic() >= deadline:
                        response.close()
                        raise ClientError('Total request deadline exceeded; no generation retry')
                    code = response.status
                    if code >= 300:
                        response.close()
                        conn.close()
                        if method == 'GET' and attempt == 0 and code in (429, 502, 503, 504):
                            time.sleep(min(0.25, max(0, deadline-time.monotonic())))
                            continue
                        raise ClientError(f'HTTP {code}; response body withheld; no generation retry')
                    break
                except (http.client.HTTPException, TimeoutError, OSError):
                    conn.close()
                    if expired.is_set() or time.monotonic() >= deadline:
                        raise ClientError('Total request deadline exceeded; no generation retry') from None
                    if method == 'GET' and attempt == 0:
                        continue
                    raise ClientError('Network/TLS/HTTP failure; endpoint may have rotated; no generation retry') from None
            with response:
                content_type = response.headers.get('Content-Type', '').split(';')[0].lower()
                stream = bool(payload and payload.get('stream'))
                if stream and content_type != 'text/event-stream':
                    raise ClientError('Expected an SSE response')
                if not stream and content_type != 'application/json':
                    raise ClientError('Expected JSON; endpoint may be a sign-in/interstitial page')
                chunks = self._chunks(response, deadline, expired)
                if stream:
                    yield from parse_sse(chunks)
                else:
                    raw = b''.join(chunks)
                    try:
                        result = json.loads(raw)
                        if isinstance(result, dict) and result.get('error'):
                            raise ClientError('API returned an application error; body withheld')
                        yield result
                    except (ValueError, UnicodeError):
                        raise ClientError('Response is not valid JSON') from None
        finally:
            timer.cancel()
            for conn in connections:
                conn.close()

    def _chunks(self, response, deadline, expired):
        count = 0
        try:
            while True:
                remaining = deadline-time.monotonic()
                if expired.is_set() or remaining <= 0:
                    raise ClientError('Total response deadline exceeded')
                try:
                    response.fp.raw._sock.settimeout(min(self.timeout, remaining))
                except AttributeError:
                    pass
                chunk = response.read1(4096)
                if expired.is_set() or time.monotonic() >= deadline:
                    raise ClientError('Total response deadline exceeded; partial output possible')
                if not chunk:
                    break
                count += len(chunk)
                if count > MAX_BYTES:
                    raise ClientError('Response exceeds 16 MiB limit')
                yield chunk
        except (http.client.HTTPException, TimeoutError, OSError):
            raise ClientError('Response interrupted; partial output possible; no generation retry') from None


def parse_sse(chunks):
    """Yield JSON events, preserving tool-call deltas. Require explicit completion."""
    buffer = b''
    data = []
    for chunk in chunks:
        buffer += chunk
        while b'\n' in buffer:
            line, buffer = buffer.split(b'\n', 1)
            line = line.rstrip(b'\r')
            if not line:
                if not data:
                    continue
                value = b'\n'.join(data)
                data = []
                if value == b'[DONE]':
                    return
                try:
                    result = json.loads(value)
                    if isinstance(result, dict) and result.get('error'):
                        raise ClientError('SSE returned an application error; body withheld')
                    yield result
                except (ValueError, UnicodeError):
                    raise ClientError('Malformed SSE JSON') from None
            elif line.startswith(b'data:'):
                data.append(line[5:].lstrip(b' '))
            # Comments, event and id fields are transport metadata, not instructions.
    raise ClientError('SSE ended without [DONE]; partial output possible; no generation retry')


class OutputRedactor:
    """Redact literal credentials, including fragments along the same SSE field."""
    def __init__(self, key):
        self.key = key
        self.tails = {}

    def clean(self, value, path=()):
        if isinstance(value, dict):
            return {k.replace(self.key, '[REDACTED]'): self.clean(v, path+(k,)) for k,v in value.items()}
        if isinstance(value, list):
            return [self.clean(v, path+(v.get('index', i) if isinstance(v, dict) else i,)) for i,v in enumerate(value)]
        if not isinstance(value, str):
            if isinstance(value, (int, float)) and self.key in str(value):
                return '[REDACTED]'
            return value
        previous = self.tails.get(path, '')
        combined = previous + value
        self.tails[path] = combined[-(len(self.key)-1):] if len(self.key)>1 else ''
        # If a credential began in an earlier delta, hide its completion now.
        overlap = 0
        for n in range(1, min(len(previous), len(self.key)-1)+1):
            if previous.endswith(self.key[:n]) and value.startswith(self.key[n:]):
                overlap = max(overlap, len(self.key)-n)
        if overlap:
            value = '[REDACTED]' + value[overlap:]
        return value.replace(self.key, '[REDACTED]')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('operation', choices=['health', 'models', 'chat'])
    source = p.add_mutually_exclusive_group(required=True)
    source.add_argument('--base-url')
    source.add_argument('--manifest', type=Path)
    p.add_argument('--key-file', type=Path)
    p.add_argument('--request', type=Path, help='Chat JSON file; do not put credentials in it')
    p.add_argument('--timeout', type=float, default=60)
    p.add_argument('--total-timeout', type=float, default=180)
    args = p.parse_args()
    try:
        base = args.base_url
        if args.manifest:
            base = load_manifest(args.manifest)
        key = read_key(args.key_file)
        payload = json.loads(args.request.read_text(encoding='utf-8')) if args.request else None
        if args.operation == 'chat' and (not isinstance(payload, dict) or not payload.get('model') or not isinstance(payload.get('messages'), list)):
            raise ClientError('Chat JSON requires model and messages; discover model with models first')
        redactor = OutputRedactor(key)
        for result in Client(base, key, args.timeout, args.total_timeout).request(args.operation, payload):
            print(json.dumps(redactor.clean(result), ensure_ascii=False), flush=True)
        return 0
    except ClientError as e:
        print(str(e), file=sys.stderr)
    except (OSError, ValueError, KeyError, TypeError, AttributeError, RecursionError):
        print('Invalid or unreadable configuration/request/credential file', file=sys.stderr)
    return 1

if __name__ == '__main__':
    sys.exit(main())
