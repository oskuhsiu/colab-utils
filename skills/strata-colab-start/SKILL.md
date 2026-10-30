---
name: strata-colab-start
description: Operate or stop the Strata Qwen3.8 Colab runtime and prepare its temporary authenticated API. Use for setup, lifecycle recovery, and paid-resource release; use strata-colab-client for calls to an already-running API.
---

# Start Strata in Colab

Operate the selected notebook or a bounded owned helper using verified upstream setup flags through an already-authorized official Colab CLI/SDK or documented browser controls. Keep approved local dependencies isolated. Use task-designated credentials; browser storage and unrelated key files are not credential sources.

**Requests to end the remote runtime take priority:** release the exact owned allocation and verify server-side absence before diagnosis or documentation, even when SSH/kernel access fails.

## Establish the current session

1. Read prior run/handoff evidence to recover the source pin, model/context, resource choices, approvals, original start/deadline, and failure layer. Inspect server-side assignments; reuse only a matching healthy owned runtime. A new retry gets a unique run record, not a new budget clock. An expired cap needs an authorized extension/new cap.
2. Resolve the requested access scope from the conversation: inside Colab, this Mac, or public clients. Reuse login/grants and check route prerequisites before paid setup. Read [references/colab-cli.md](references/colab-cli.md) for CLI/SSH mechanics and [references/external-session.md](references/external-session.md) for public access.
3. Establish only missing authorization for GPU/RAM, total time or CU/spend cap, and download/storage. **Before allocation, arm and verify an independent release watchdog** covering setup through API use. Save the allocation request identity first; save the returned endpoint immediately and verify watchdog adoption before bootstrap. Observe account-wide CU/hour and reserve shutdown headroom. Retries retain the original deadline; extensions update the watchdog too. If reliable release cannot be established, resolve shutdown responsibility before spending.
4. Own one runtime. Inspect CLI allocation behavior: some versions automatically start keepalive or allocate on missing session names. Disable those behaviors through the verified implementation; never use anti-idle, automatic reconnection, or quota bypass.

## Configure, check, install

Read [references/notebook-workflow.md](references/notebook-workflow.md) for live form controls and preset tradeoffs. Reuse the approved source pin and resource settings; if an update is requested, verify its official release and setup flags. A valid source pin does not guarantee a usable prebuilt asset: verify the actual asset and budget remaining build/download/load time for a source-build fallback. Preserve requested context rather than applying a smaller preset.

- Check actual GPU/VRAM, host RAM and process memory limits, driver/CUDA, free disk, cache and loopback port before installation. Select an unused API port and carry it through configuration, manifest and client checks. Resource labels and fit estimates are insufficient; resolve blockers within authorization rather than changing host drivers.
- **For external client access, test authentication and HTTP forwarding before downloading weights:** missing/wrong key denied and correct-key HTTP reaches the gateway. For streaming, check the route's SSE support and probe incremental synthetic SSE where feasible. Keep transport results separate from model inference; release idle paid resources when prerequisites block productive work.
- For CLI setup, prefer a short bounded official CLI/SDK execution that launches an owned background worker. Monitor long installation/status through the official contents REST API. Use an official Colab SSH bootstrap only if ordinary execution is concretely unavailable/failing, then close it. Recover bounded transient reads without restarting a working job; inspect assignment/job before reinstalling or reallocating. Details are in the CLI reference.
- Run authorized installation once, reusing valid cache/processes. Verify completion, loaded `/health`, live model ID/context, effective engine mode, and a short inference before exporting a session. Compare supported fallbacks with the user's constraints before rejecting them. Repeated “Run all” or launch acknowledgements do not establish readiness.

## External access

Use the selected route within remaining time; keep Strata/gateway and any Mac listener on loopback. Store fresh task-generated keys privately, outside code, argv, output and manifests. For provider/Secrets details, read the external-session reference.

From the actual client, verify authentication, genuine health/models JSON, and approved JSON/SSE inference with content and `[DONE]`. Export a non-secret `strata-session.json` with the live model ID and endpoint expiry. Use `strata-colab-client` for calls.

**Context/performance claims require approved actual generation**: count rendered input tokens before sending, reserve template/reasoning/output space and reconcile inference usage. Follow the client skill's measurement guidance. For a stable maximum, reserve repeated near-full runs, a clean engine restart and shutdown time before spending the budget on intermediate checks. Configured context, heartbeats and synthetic transport timings do not prove capacity or speed. Record failures, partial output and tests not run; distinguish synthetic retrieval from general document quality.

## Stop and recover

Capture failure layer, sanitized error and current assignment/job state before bounded recovery. A failed client check or lost connection does not prove backend failure or VM release. Reuse a healthy owned model and sampler while correcting a probe within authorization; avoid restarting them for a local assertion failure. Changes in provider, resource budget or credential scope need applicable authorization.

An API-only stop leaves VM billing unless released. For end-runtime/expiry, release **only the recorded owned endpoint** through official CLI/SDK or Colab UI, then verify server-side absence and current usage. Total rate zero corroborates shutdown only when no other assignments remain. Invalidate the manifest and close owned local helpers afterward. If absence cannot be verified, report it and the exact manual disconnect/delete action. Preserve unrelated runtimes and processes.
