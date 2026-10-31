#!/usr/bin/env python3
"""Single-GPU producer with independent artifact and review consumers.

No callback is supplied implicitly: this module never allocates, installs, or
stops a runtime. ``submit(attempt)`` receives a persisted prompt UUID and payload;
``wait(attempt, submission)`` returns only when that exact GPU job has completed.
``fetch(attempt, execution)`` must save and integrity-check recoverable artifacts
(it may transfer from Colab to a Mac). ``review(attempt, artifact)`` is optional
CPU/content QA. Callbacks return JSON-serializable evidence, never credentials.
Submission/completion evidence must contain the original ``prompt_id``; the wait
result must have ``status="execution_complete"``. Payload JSON is immutable;
referenced graph/media files must be sealed and hash-checked by the adapter.

The producer remains receptive while required saves drain. No ready work plus
completed save work atomically closes its generation window; later enqueues
remain for another run. The caller controls dependencies through ``set_ready``.
Only one producer can run against a directory. Unknown execution is reconciled
explicitly, never retried. The release-ready marker and ``on_saved_drain`` notify
the resource owner before any wait for long review work.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
import copy
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import re
import tempfile
import threading
import time
import uuid


class NeedsReconcile(RuntimeError):
    """An original submission may still exist; no new inference was attempted."""


def fits_deadline(deadline_epoch, generation_seconds, save_backlog_seconds,
                  new_save_seconds, release_reserve_seconds, *, now=None):
    """One serial save lane overlaps generation; content QA is outside this cost.

    The candidate's save starts after both its generation and the existing save
    backlog finish. The release allowance is added once, not at every stage.
    Estimates/fee isolation and a separate hard-stop watcher belong to the owner.
    """
    values = (deadline_epoch, generation_seconds, save_backlog_seconds,
              new_save_seconds, release_reserve_seconds)
    if any(type(v) not in (int, float) or not math.isfinite(v) for v in values):
        raise ValueError("Deadline and duration estimates must be finite numbers")
    if any(v < 0 for v in values[1:]):
        raise ValueError("Duration estimates must be nonnegative")
    now = time.time() if now is None else now
    tail = max(generation_seconds, save_backlog_seconds) + new_save_seconds
    return now + tail + release_reserve_seconds <= deadline_epoch


def _json(value):
    return json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n"


def _write(path, value):
    fd, temporary = tempfile.mkstemp(prefix="." + path.name, dir=path.parent)
    try:
        with os.fdopen(fd, "w") as stream:
            stream.write(_json(value))
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


class Pipeline:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self._mutex = threading.RLock()
        self._wake = threading.Event()
        with self._state(write=True):
            pass

    @contextmanager
    def _state(self, write=False):
        with self._mutex, (self.root / "state.lock").open("a+") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            path = self.root / "state.json"
            state = json.loads(path.read_text()) if path.exists() else {
                "version": 1, "jobs": {}, "gpu": "idle", "release_ready": False}
            try:
                yield state
                if write:
                    _write(path, state)
            finally:
                fcntl.flock(lock, fcntl.LOCK_UN)

    def snapshot(self):
        with self._state() as state:
            return copy.deepcopy(state)

    def _update(self, attempt_id, **fields):
        with self._state(write=True) as state:
            state["jobs"][attempt_id].update(fields, updated_epoch=time.time())

    def enqueue(self, attempt_id, payload, *, priority="normal", ready=True, origin_attempt=None):
        if not isinstance(attempt_id, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,79}", attempt_id):
            raise ValueError("attempt_id must be filename-safe, 1–80 characters")
        if priority not in ("normal", "retake") or type(ready) is not bool:
            raise ValueError("Choose normal/retake priority and a boolean ready flag")
        if priority == "retake" and not origin_attempt:
            raise ValueError("A retake must identify its original attempt")
        immutable = {"attempt_id": attempt_id, "prompt_id": str(uuid.uuid4()),
                     "payload": payload, "priority": priority, "origin_attempt": origin_attempt}
        content = _json(immutable)  # Reject non-JSON payloads before creating anything.
        with self._state(write=True) as state:
            path = self.root / (attempt_id + ".job.json")
            if attempt_id in state["jobs"] or path.exists():
                raise FileExistsError("Attempt exists; a retake needs a new ID")
            with path.open("x") as stream:
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
            state["jobs"][attempt_id] = {
                "sequence": len(state["jobs"]), "priority": priority, "ready": ready,
                "job_sha256": hashlib.sha256(content.encode()).hexdigest(),
                "execution": "pending", "artifact": "pending", "review": "pending"}
        self._wake.set()
        return immutable

    def set_ready(self, attempt_id, ready=True):
        if type(ready) is not bool:
            raise ValueError("ready must be boolean")
        with self._state(write=True) as state:
            job = state["jobs"][attempt_id]
            if job["execution"] != "pending":
                raise ValueError("Only an unsubmitted attempt can change readiness")
            job["ready"] = ready
        self._wake.set()

    def _attempt(self, attempt_id):
        with self._state() as state:
            record = copy.deepcopy(state["jobs"][attempt_id])
        content = (self.root / (attempt_id + ".job.json")).read_bytes()
        if hashlib.sha256(content).hexdigest() != record["job_sha256"]:
            raise RuntimeError("Immutable attempt payload changed")
        return {**json.loads(content), **record}

    def _claim(self, attempt_id):
        # Enqueue/readiness may change while the admission hook observes costs.
        with self._state(write=True) as state:
            ready = [(identity, job) for identity, job in state["jobs"].items()
                     if job["execution"] == "pending" and job["ready"]]
            if not ready:
                return False
            selected = min(ready, key=lambda pair: (pair[1]["priority"] != "retake", pair[1]["sequence"]))[0]
            if selected != attempt_id:
                return False
            state["jobs"][attempt_id].update(execution="submitting", submission_intent_epoch=time.time())
            return True

    def retry_fetch(self, attempt_id):
        """Explicitly retry artifact recovery after the caller reconciles partials."""
        with self._state(write=True) as state:
            job = state["jobs"][attempt_id]
            if job["execution"] != "complete" or job["artifact"] not in ("failed", "fetching"):
                raise ValueError("Only an existing completed execution can retry its failed save")
            job.update(artifact="pending", review="pending")

    def reconcile(self, attempt_id, execution_result):
        """Record an owner-confirmed original result, without any submission."""
        attempt = self._attempt(attempt_id)
        if execution_result.get("prompt_id") != attempt["prompt_id"]:
            raise ValueError("Reconciliation must identify the original prompt UUID")
        status = execution_result.get("status")
        if status not in ("execution_complete", "execution_failed"):
            raise ValueError("Confirm execution_complete or execution_failed")
        _json(execution_result)
        with self._state(write=True) as state:
            job = state["jobs"][attempt_id]
            if job["execution"] not in ("submitting", "running", "unknown"):
                raise ValueError("Only an unresolved original execution can be reconciled")
            job.update(execution="complete" if status == "execution_complete" else "failed",
                       execution_result=execution_result)

    @contextmanager
    def _producer(self):
        with (self.root / "producer.lock").open("a+") as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as error:
                raise RuntimeError("Another producer owns this pipeline") from error
            try:
                yield
            finally:
                fcntl.flock(lock, fcntl.LOCK_UN)

    def run(self, submit, wait, fetch, *, review=None, admit=None,
            on_saved_drain=None, wait_for_review=True):
        """Run ready work; an admission callback receives (attempt, snapshot).

        ``False`` admission drains already committed artifacts without starting
        the candidate. A transfer/review failure changes only its own lane.
        Callbacks must bound their own transport/CPU work. Queue/disk backlog
        bounds and the hard deadline can be enforced from ``admit``'s snapshot.
        """
        with self._producer():
            initial = self.snapshot()
            if any(j["execution"] in ("submitting", "running", "unknown") for j in initial["jobs"].values()):
                raise NeedsReconcile("Inspect the original prompt; inference is never retried")
            transfers = ThreadPoolExecutor(max_workers=1, thread_name_prefix="artifact")
            reviews = ThreadPoolExecutor(max_workers=1, thread_name_prefix="review")
            saves = []
            failure = None
            with self._state(write=True) as state:
                state.update(gpu="running", release_ready=False, generation_closed_epoch=None)

            def inspect(attempt, artifact):
                self._update(attempt["attempt_id"], review="running")
                try:
                    result = review(attempt, artifact)
                    _json(result)
                    verdict = result.get("verdict") if isinstance(result, dict) else None
                    self._update(attempt["attempt_id"], review=verdict if verdict in ("pass", "fail", "unknown") else "complete",
                                 review_result=result)
                except Exception as error:
                    self._update(attempt["attempt_id"], review="error", review_error=type(error).__name__)

            def save(attempt, execution):
                self._update(attempt["attempt_id"], artifact="fetching")
                try:
                    artifact = fetch(attempt, execution)
                    _json(artifact)
                    self._update(attempt["attempt_id"], artifact="saved", artifact_result=artifact)
                    if review is not None:
                        reviews.submit(inspect, attempt, artifact)
                    else:
                        self._update(attempt["attempt_id"], review="not_requested")
                except Exception as error:
                    self._update(attempt["attempt_id"], artifact="failed", artifact_error=type(error).__name__)

            def schedule_save(attempt, execution):
                future = transfers.submit(save, attempt, execution)
                saves.append(future)
                future.add_done_callback(lambda _: self._wake.set())

            try:
                for identity, job in initial["jobs"].items():
                    if job["execution"] == "complete" and job["artifact"] == "pending":
                        schedule_save(self._attempt(identity), job["execution_result"])
                while True:
                    snapshot = self.snapshot()
                    candidates = [(identity, job) for identity, job in snapshot["jobs"].items()
                                  if job["execution"] == "pending" and job["ready"]]
                    if not candidates:
                        if any(not future.done() for future in saves):
                            # Same-instance enqueue wakes immediately; a short
                            # poll also observes another process's enqueue.
                            self._wake.wait(0.05)
                            self._wake.clear()
                            continue
                        with self._state(write=True) as state:
                            if any(j["execution"] == "pending" and j["ready"]
                                   for j in state["jobs"].values()):
                                continue
                            state["generation_closed_epoch"] = time.time()
                        reason = "no_ready_work"
                        break
                    identity, _ = min(candidates, key=lambda pair: (pair[1]["priority"] != "retake", pair[1]["sequence"]))
                    attempt = self._attempt(identity)
                    if admit is not None and not admit(attempt, snapshot):
                        reason = "admission_denied"
                        break
                    if not self._claim(identity):
                        continue
                    try:
                        submission = submit(attempt)
                        _json(submission)
                        if not isinstance(submission, dict) or submission.get("prompt_id") != attempt["prompt_id"]:
                            raise ValueError("Submission evidence must identify the stored prompt UUID")
                        self._update(identity, execution="running", submission=submission)
                        execution = wait(attempt, submission)
                        _json(execution)
                        if not isinstance(execution, dict) or execution.get("prompt_id") != attempt["prompt_id"]:
                            raise ValueError("Completion evidence must identify the original prompt UUID")
                        if execution.get("status") != "execution_complete":
                            raise ValueError("Wait must confirm the original execution is complete")
                        self._update(identity, execution="complete", execution_result=execution)
                    except BaseException as error:
                        self._update(identity, execution="unknown", execution_error=type(error).__name__)
                        failure = NeedsReconcile("Original submission/execution needs reconciliation")
                        reason = "needs_reconcile"
                        break
                    schedule_save(attempt, execution)
            finally:
                # Ready GPU work never joins transfer or review futures; only
                # an otherwise empty queue waits for the necessary save tail.
                with self._state(write=True) as state:
                    if any(j["execution"] in ("submitting", "running", "unknown") for j in state["jobs"].values()):
                        failure = failure or NeedsReconcile("Original submission/execution needs reconciliation")
                    closed = state.get("generation_closed_epoch") or time.time()
                    state.update(gpu="needs_reconcile" if failure else "drained",
                                 generation_closed_epoch=closed,
                                 gpu_drained_epoch=None if failure else closed,
                                 stop_reason=locals().get("reason", "controller_error"))
                transfers.shutdown(wait=True)
                try:
                    with self._state(write=True) as state:
                        saved = all(j["artifact"] == "saved" for j in state["jobs"].values()
                                    if j["execution"] == "complete")
                        state["release_ready"] = not failure and saved
                        if state["release_ready"]:
                            state["artifacts_drained_epoch"] = time.time()
                    if self.snapshot()["release_ready"] and on_saved_drain is not None:
                        on_saved_drain(self.snapshot())
                finally:
                    reviews.shutdown(wait=wait_for_review)
            if failure:
                raise failure
            return self.snapshot()
