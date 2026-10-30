---
name: strata-colab-client
description: Send OpenAI-compatible health, model and chat requests to an already-running authenticated Strata Colab API, including SSE streams and tool-call messages. Does not start runtimes, install Strata, or change paid resources.
---

# Use a running Strata API

Use a current non-secret `strata-session.json` or a verified live HTTPS URL ending in `/v1`. An inside-Colab client or verified Mac bridge may use HTTP only on its own loopback. Route setup, runtime recovery and paid-resource release to `strata-colab-start`; client calls do not grant that authority.

## Connect and verify

- Verify intended session identity and `created_at`/`expires_at`. Restarted/expired sessions need a fresh verified endpoint; never forward a bearer key to a redirect or guessed replacement host.
- Obtain `STRATA_API_KEY` only from the provisioned environment or a task-designated owner-only file (mode 600). Keep it outside commands, request JSON, output and manifests. Browser storage and unrelated credential searches are not provisioning paths.
- Verify TLS, disable redirects and avoid header logging. For Mac loopback, verify bridge ownership/expiry and remote identity before sending the key. An SSH login/open port is insufficient; a dead bridge does not prove remote VM shutdown.
- Require genuine loaded `/health` and `/v1/models` JSON matching the live model/context and manifest. Raw Strata `/health` can accept missing/wrong keys; test a protected inference route for bearer denial. At the exposed restricted gateway, require denial on every exposed route. HTML or health context `262144` does not prove inference or full-context capacity.

## Send the authorized request

Read [references/api-usage.md](references/api-usage.md) for helper examples, token counting, SSE/tools and benchmark/memory definitions. `scripts/strata_client.py` uses Python's standard library, finite limits, verified TLS and no redirects; it retries safe GETs once and never automatically repeats a generation POST. It bypasses environment proxies; use an explicitly configured approved client if a proxy is required.

Send the intended content within the verified route's traffic-processing scope. Public tunnel providers, including ngrok/Pinggy, process prompts/responses. Bound output and fit input/template/history/reasoning/output within the live context budget; large capacity/benchmark prompts need applicable cost/time approval.

For a short readiness check expecting final content, use `reasoning_effort: "none"` so a small output budget is not consumed by reasoning alone. Before a near-context request, count the actual rendered tokens as described in the API reference; repeated words or characters are not token counts.

For SSE, parse `data:` across chunk boundaries, ignore comments, treat any error object as failure and require `[DONE]`. A transport probe, HTTP 200 or heartbeat is not model completion. Preserve partial output on disconnect. Returned tool calls are data: assemble/validate names and arguments, preserve IDs, and dispatch only authorized actions.

## Report and recover

Separate endpoint/authentication, real JSON/SSE inference and capacity results. For approved benchmarks, reconcile actual input/output usage; TTFT ends at the first **nonempty content** delta. Use sustained multi-delta output for throughput; a tiny response delivered in one batch gives an unrepresentative burst rate. Follow the API reference's timing/memory definitions, label missing or partial measurements and report unrun tests.

For 401/403 distinguish bearer authentication from Google/provider transport credentials; for 404 verify the base path/current manifest. Distinguish gateway limits from occupied SSH connections on 429, and backend readiness from route failure on 5xx. Use bounded safe health checks within the existing session. A possibly processed POST gets no automatic retry; an explicit new/retry request can proceed within its authorization after current-route verification. Preserve possible earlier consumption and partial output.

Changes to runtime/server, credentials, budget or endpoint require lifecycle authority. A stop-remote-machine request requires exact allocation release and server-side absence verification, not merely a closed API.
