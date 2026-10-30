# Colab CLI lifecycle and recovery

Read for CLI setup/recovery or a Mac-only bridge. Check installed help/source; the concrete pitfalls below were observed with CLI 0.7.2, not guaranteed for later versions.

## Own the allocation

Use existing authorized official login and a unique run-specific config. Keep credentials and an exact-endpoint release handle private; separately record session identity, original start/deadline and CU/hour. Arm and verify the independent watchdog before allocation. When process inspection is denied, verify its advancing heartbeat and exact target; `EPERM` is not evidence it exited. Retries preserve the deadline; an extension updates both record and watchdog.

Budget setup, readiness, generation and export against the remaining campaign time, reserving closeout once. Fixed nested margins can abort productive work early; editing a helper does not extend a timeout already running. Check all phase cutoffs before launch.

Establish ownership from the allocation response or saved request identity; an account-wide before/after difference alone is insufficient. Reconcile current server state and preserve unrelated assignments. On capacity refusal, stop allocation attempts until a verified slot release or changed authorization makes a bounded retry appropriate.

In 0.7.2, `new` spawned a keepalive daemon and missing SSH proxy session names could allocate a VM. Inspect the actual call sites and suppress these behaviors through a verified supported/scoped invocation. An invented `--no-keepalive` flag is not a solution.

On stop or expiry, use official `stop -s <owned-session>` with the intended auth/config. If its handle was pruned, inspect the installed release implementation: 0.7.2 uses `state.client.unassign(session.endpoint)` without requiring successful kernel cleanup. Through the authorized SDK, match the exact recorded endpoint/resource in `list_assignments()`, unassign only that runtime, and re-list to verify absence. This is not an invented `stop --endpoint` option. Query usage after the absence check; a failed optional balance read must not erase verified release.

## Bootstrap once, monitor separately

Prefer a short wall-clock-bounded official CLI/SDK execution to launch an owned background worker. The observed long Jupyter execution/monitoring hang does not establish that short ordinary execution is unusable. If the launch channel fails, inspect whether the worker started before repeating it.

For long installation/download/load, have the worker write non-secret status/log files. Read only owned files through the official authenticated runtime contents REST API (`/api/contents/<path>`) with bounded request/body/total time and redirects disabled. Refresh a verified owned proxy lease through official SDK/cache interfaces when necessary. Sustained Jupyter/SFTP monitoring had timeout problems; a single SFTP status timeout previously triggered premature deployment cleanup.

Recover a transient read within a finite allowance and the original deadline. Repeated failures require checking server-side assignment and owned job/status before reinstall/reallocation. An output channel can fail while remote work continues. Record sanitized exception class/frame locations and one discriminating probe; a failed SSH bootstrap does not by itself establish its root cause. Cleanup stays idempotent, finite and limited to owned processes/sockets.

## Conditional environment fixes

Use these only when the matching failure occurs:

- **Handle lost / proxy 401 or 404:** `exec` may prune a local handle, or the proxy token may rotate while its URL and allocation stay unchanged. Reconcile `list_assignments()` and refresh the verified owned proxy info in private state before kernel recovery. Creating another client from the same stale handle does not refresh its lease.
- **Kernel/globals lost:** persist kernel/session IDs and attach the same owned kernel across SDK calls. Missing `CFG` can mean a new kernel, not a failed installation. Inspect existing kernels before recovery; preserve unrelated notebook state.
- **Installation interpreter / pip seeding:** launch with the interpreter that installed the dependencies; direct upstream setup does not imply the notebook's `.venv` exists. On the observed Colab Python 3.13 image, available `uv venv --allow-existing --seed --python <kernel-python> <repo-venv>` recovered failed ordinary seeding. Check flags and reuse a working environment, including pip.
- **Container memory guard:** unavailable cgroup information is not proof of insufficient RAM. Match the engine's process membership to its actual cgroup mount and individually readable limit/stat/event files; directory-list denial does not prove those files are unreadable. Keep admission checks intact and evaluate a supported user-permitted fallback with actual workload measurements.
- **Local DNS/TLS/tooling:** a CLI logging/cache permission error is a local tooling failure; reuse a working official SDK/login with task-scoped state. Use scoped alternatives for DNS/SSH/process-inventory failures, preserving TLS/SNI and certificate checks. A supported Certifi path may resolve native trust-store failure; preserve system DNS/users and unrelated processes.
- **Colab Secrets:** `google.colab.userdata.get()` requires UI execution/access grants and can time out through CLI-only execution. Use one concrete UI action or an authorized task-designated/generated secure credential path, rather than repeating the unavailable mechanism.

## Conditional SSH bootstrap and Mac bridge

For bootstrap, use official Colab SSH only after ordinary CLI/SDK execution is concretely unavailable/failing. Use one bounded upload/launch/probe operation, then close it. Colab permits one SSH connection; concurrent bridge/control connections caused 429 collisions. Explicitly select auth/config/key and a per-runtime host pin; suppress update banners that corrupt proxy bytes. Provider reverse SSH tunneling (such as Pinggy) is a separate public-transport operation, not the Colab bootstrap method.

The official CLI's `ssh --proxy-mode` is an experimental candidate for Mac loopback forwarding to the authenticated Colab gateway. It needs Google authentication and working local forwarding, but no ngrok account. Native interactive SSH in the observed version ignored the custom config/DNS wrapper and disabled host checking; use an explicitly scoped verified client instead.

Prove intended HTTP forwarding/authentication with a lightweight gateway before weights; then verify live health/models and actual JSON/SSE from the Mac. SSH login, a listener or uploaded code is insufficient. Keep no auto-allocation, reconnection or anti-idle loop. If another SSH connection is active, identify and close only an owned one. Existing run-specific helpers remain experimental artifacts, not a supported installer or proof that transport problems are resolved.
