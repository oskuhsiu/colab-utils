"""Small standard-library client for an already running ComfyUI server."""

import filecmp
import json
import math
import os
from pathlib import Path
import shutil
import tempfile
import time
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode, urlsplit
from urllib.request import Request, urlopen
import uuid


class GraphValidationError(ValueError):
    """A graph cannot satisfy the server's advertised node schema."""


class ComfyHTTPError(RuntimeError):
    def __init__(self, status, payload):
        self.status, self.payload = status, payload
        super().__init__(f"ComfyUI HTTP {status}: {payload}")


class PromptExecutionError(RuntimeError):
    def __init__(self, prompt_id, history):
        self.prompt_id, self.history = prompt_id, history
        super().__init__(f"ComfyUI execution failed for prompt {prompt_id}")


class PromptTimeoutError(TimeoutError):
    def __init__(self, prompt_id):
        self.prompt_id = prompt_id
        super().__init__(f"Timed out waiting for prompt {prompt_id}; it may still be running")


class ComfyClient:
    def __init__(self, base_url="http://127.0.0.1:8188", timeout=30, before_submit=None):
        parsed = urlsplit(base_url)
        if (parsed.scheme not in ("http", "https") or not parsed.hostname
                or parsed.username or parsed.password or parsed.query or parsed.fragment):
            raise ValueError("base_url must be an HTTP(S) server URL without credentials or query")
        if timeout <= 0:
            raise ValueError("timeout must be positive")
        if before_submit is not None and not callable(before_submit):
            raise ValueError("before_submit must be callable")
        self.base_url, self.timeout = base_url.rstrip("/"), timeout
        self.before_submit = before_submit

    def _open(self, path, data=None, timeout=None):
        if not path.startswith("/") or path.startswith("//"):
            raise ValueError("API path must start with one slash")
        body = None if data is None else json.dumps(data).encode("utf-8")
        headers = {} if body is None else {"Content-Type": "application/json"}
        request = Request(self.base_url + path, data=body, headers=headers)
        try:
            return urlopen(request, timeout=self.timeout if timeout is None else timeout)
        except HTTPError as error:
            with error:
                raw = error.read().decode("utf-8", errors="replace")
            try:
                payload = json.loads(raw)
            except ValueError:
                payload = raw
            raise ComfyHTTPError(error.code, payload) from error

    def get_json(self, path):
        with self._open(path) as response:
            return json.load(response)

    def post_json(self, path, data):
        # A lost response does not imply the prompt was not queued. Never retry.
        with self._open(path, data) as response:
            return json.load(response)

    def object_info(self):
        return self.get_json("/object_info")

    @staticmethod
    def _input_specs(declared, inputs, prefix=""):
        """Expand current ComfyUI DynamicCombo fields from their selected keys."""
        specs, required = {}, set()
        for group in ("required", "optional"):
            for name, spec in declared.get(group, {}).items():
                identity = prefix + name
                specs[identity] = spec
                if group == "required":
                    required.add(identity)
                if spec[0] == "COMFY_DYNAMICCOMBO_V3" and identity in inputs:
                    options = spec[1].get("options", [])
                    selected = next((option for option in options if option["key"] == inputs[identity]), None)
                    if selected is None:
                        raise GraphValidationError(f"Input {identity}: invalid dynamic combo selection")
                    nested, needed = ComfyClient._input_specs(selected.get("inputs", {}), inputs, identity + ".")
                    specs.update(nested)
                    required.update(needed)
        return specs, required

    def validate_graph(self, graph):
        """Check advertised inputs; /prompt still performs native validation."""
        schemas = self.object_info()
        if not isinstance(graph, dict) or not graph:
            raise GraphValidationError("Graph must be a nonempty API node dictionary")
        for node_id, node in graph.items():
            if not isinstance(node_id, str) or not isinstance(node, dict):
                raise GraphValidationError("API node IDs must be strings and nodes dictionaries")
            class_type = node.get("class_type")
            if not isinstance(class_type, str) or class_type not in schemas:
                raise GraphValidationError(f"Node {node_id}: unknown class_type {class_type!r}")
            inputs = node.get("inputs")
            if not isinstance(inputs, dict):
                raise GraphValidationError(f"Node {node_id}: inputs must be a dictionary")
            declared = schemas[class_type].get("input", {})
            specs, required = self._input_specs(declared, inputs)
            missing = required - inputs.keys()
            if missing:
                raise GraphValidationError(f"Node {node_id}: missing inputs {sorted(missing)}")
            for name, value in inputs.items():
                label = f"Node {node_id} input {name}"
                spec = specs.get(name)
                if isinstance(value, list) and len(value) == 2 and isinstance(value[0], str):
                    source, slot = value
                    source_node = graph.get(source)
                    source_class = source_node.get("class_type") if isinstance(source_node, dict) else None
                    source_schema = schemas.get(source_class, {}) if isinstance(source_class, str) else {}
                    outputs = source_schema.get("output", [])
                    if source_node is None or type(slot) is not int or not 0 <= slot < len(outputs):
                        raise GraphValidationError(f"{label}: invalid link {value!r}")
                    continue
                if not spec:
                    continue  # Hidden/custom dynamic inputs are validated by ComfyUI.
                kind = spec[0]
                options = spec[1] if len(spec) > 1 and isinstance(spec[1], dict) else {}
                if isinstance(kind, list):
                    valid = value in kind
                elif kind == "COMBO":
                    choices = options.get("options", [])
                    valid = (isinstance(value, list) and all(item in choices for item in value)
                             if options.get("multiselect", False) else value in choices)
                elif kind == "COMFY_DYNAMICCOMBO_V3":
                    valid = any(option["key"] == value for option in options.get("options", []))
                elif kind == "INT":
                    valid = type(value) is int
                elif kind == "FLOAT":
                    valid = type(value) in (int, float) and math.isfinite(value)
                elif kind == "BOOLEAN":
                    valid = type(value) is bool
                elif kind == "STRING":
                    valid = isinstance(value, str)
                else:
                    valid = False  # Typed objects must arrive through links.
                if not valid:
                    raise GraphValidationError(f"{label}: invalid value for {kind!r}")
                if kind in ("INT", "FLOAT") and any(
                    key in options and compare(value, options[key])
                    for key, compare in (("min", lambda a, b: a < b), ("max", lambda a, b: a > b))
                ):
                    raise GraphValidationError(f"{label}: value outside advertised range")
        return graph

    def queue_prompt(self, graph, prompt_id=None, extra_data=None):
        self.validate_graph(graph)
        identity = str(uuid.uuid4()) if prompt_id is None else str(prompt_id)
        payload = {"prompt": graph, "prompt_id": identity}
        if extra_data is not None:
            payload["extra_data"] = extra_data
        # Admission runs after schema checks, immediately before the one POST.
        if self.before_submit is not None:
            self.before_submit(identity)
        result = self.post_json("/prompt", payload)
        if result.get("error") or result.get("node_errors") or not result.get("prompt_id"):
            raise ComfyHTTPError(200, result)
        return result

    def _wait_json(self, path, prompt_id, deadline):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise PromptTimeoutError(prompt_id)
        try:
            with self._open(path, timeout=min(self.timeout, remaining)) as response:
                return json.load(response)
        except TimeoutError as error:
            raise PromptTimeoutError(prompt_id) from error
        except URLError as error:
            if isinstance(error.reason, TimeoutError):
                raise PromptTimeoutError(prompt_id) from error
            raise

    def wait_prompt(self, prompt_id, timeout=1800, poll_seconds=5, on_status=None):
        if timeout < 0 or poll_seconds <= 0:
            raise ValueError("timeout must be nonnegative and poll_seconds positive")
        started = time.monotonic()
        deadline = started + timeout
        while True:
            history = self._wait_json("/history/" + quote(str(prompt_id), safe=""),
                                      prompt_id, deadline).get(str(prompt_id))
            status = history.get("status", {}) if history else {}
            messages = status.get("messages", [])
            failed = status.get("status_str") in ("error", "failed", "interrupted") or any(
                message and message[0] in ("execution_error", "execution_interrupted", "execution_failed")
                for message in messages
            )
            if failed:
                raise PromptExecutionError(prompt_id, history)
            complete = status.get("completed") is True and status.get("status_str") == "success"
            state = "completed" if complete else "unknown"
            if not complete:
                queue = self._wait_json("/queue", prompt_id, deadline)
                for key, value in (("queue_running", "running"), ("queue_pending", "pending")):
                    if any(len(entry) > 1 and str(entry[1]) == str(prompt_id) for entry in queue.get(key, [])):
                        state = value
                        break
            if on_status:
                on_status({"prompt_id": str(prompt_id), "state": state,
                           "elapsed_seconds": time.monotonic() - started, "status": status})
            if complete:
                return history
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise PromptTimeoutError(prompt_id)
            time.sleep(min(poll_seconds, remaining))

    @staticmethod
    def output_files(history):
        files = []
        for output in history.get("outputs", {}).values():
            for key in ("videos", "gifs", "images"):
                for item in output.get(key, []):
                    filename = item.get("filename", "")
                    if Path(filename).suffix.lower() in (".mp4", ".webm", ".mov"):
                        entry = {"filename": filename, "subfolder": item.get("subfolder", ""),
                                 "type": item.get("type", "output")}
                        if entry not in files:
                            files.append(entry)
        return files

    def download_output(self, item, path):
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        query = urlencode({key: item.get(key, default) for key, default in
                           (("filename", ""), ("subfolder", ""), ("type", "output"))})
        fd, temporary = tempfile.mkstemp(prefix="." + target.name + ".", dir=target.parent)
        try:
            with os.fdopen(fd, "wb") as output, self._open("/view?" + query) as response:
                shutil.copyfileobj(response, output)
                output.flush()
                os.fsync(output.fileno())
            # Hard-link publication is atomic and cannot replace an existing file.
            # Unlike os.replace(), it also preserves a target created concurrently.
            try:
                os.link(temporary, target)
            except FileExistsError:
                if not filecmp.cmp(temporary, target, shallow=False):
                    raise FileExistsError(f"Output already exists with different bytes: {target}")
            return target
        finally:
            os.unlink(temporary)
