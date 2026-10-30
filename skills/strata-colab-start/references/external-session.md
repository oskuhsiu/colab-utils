# Authenticated external session

## Choose and prove the route

The notebook's built-in public mode uses ngrok and needs an existing account/token. Resolve those prerequisites before paid setup; Colab login alone does not provide `NGROK_AUTHTOKEN`. For Mac-only access use [colab-cli.md](colab-cli.md).

When public access without an account/domain is requested, [Pinggy anonymous HTTPS](https://pinggy.io/docs/) is a candidate. Its [SSE guidance](https://pinggy.io/docs/guides/pocketbase/) and live lightweight probes supported incremental transport with authentication. Actual public **model** JSON/SSE inference still needs verification. Free sessions last about 60 minutes and rotate URLs; align exposure and VM-release deadlines with the current verified limits. The route is outside the notebook's ngrok form, and existing experimental run helpers are not a supported default deployment path. [Cloudflare Quick Tunnels](https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/do-more-with-tunnels/trycloudflare/) explicitly do not support SSE.

Use only a route within the user's approved traffic-processing scope: the tunnel provider sees prompts/responses. Before weights, probe missing/wrong-key denial and authenticated forwarding; check SSE support and test incremental synthetic SSE where feasible. A URL or correct-key 503 can prove gateway reachability but not loaded-model readiness. Keep TLS verified, redirects disabled and provider host identity checked. Provider reverse SSH (such as Pinggy) is separate from Colab bootstrap. Its task-local TOFU pin detects later host changes, not independent vendor verification.

## Gateway contract

Bind Strata and its restricted bearer gateway to loopback; expose only the gateway. All external routes require `Authorization: Bearer <STRATA_API_KEY>`:

- `GET /health`
- `GET /v1/models`
- `POST /v1/chat/completions`, JSON or SSE

This is temporary Colab service, not an always-on deployment. Use the approved paid-resource budget; do not treat positive CU as permission to buy more or bypass platform limits. The raw backend may allow unauthenticated health; verify authentication at the exposed gateway.

## Built-in ngrok forms

Inspect live cell titles/controls before using these names. Provision `NGROK_AUTHTOKEN` and a random `STRATA_API_KEY` of at least 32 letters/digits/underscore/hyphen through Colab Secrets with notebook access. Provision the same service key privately to the client. Keep values out of argv, code, chat, output, logs and manifests; use redacted diagnostics. CLI-only Secrets limitations are in the CLI reference.

1. 外部API工具 defines helpers. 外部API依赖 installs optional dependencies only when authorized (`install_external_dependencies`).
2. 外部API启停: use `external_action`, `accept_ngrok_traffic_processing`, `confirm_paid_colab_positive_cu` and `external_session_minutes` within existing authorization. Local Strata must be healthy. Preserve 8 MiB body limit, one request, 3600-second streaming timeout and `stop_server_at_session_expiry=True` unless a required authorized change justifies otherwise. Never round a duration cap upward.
3. 导出无密钥会话信息: enable `export_session_info` after live verification. Check `strata-session.json` contains no key, uses `https://<verified-host>/v1`, and records the live model/context and expiry. Discover the model rather than hard-coding `strata`; refresh after restart/URL rotation.

The notebook accepts ngrok hosts under `ngrok-free.app`, `ngrok.app` or `ngrok.io`; reject lookalikes/redirects. Client requests use `ngrok-skip-browser-warning: 1` so HTML screening is not mistaken for readiness.

## Verify and expire

From the actual client, confirm denied unauthenticated requests, authenticated health/models JSON and approved real model JSON/SSE. For long processing prefer SSE: this gateway's ordinary JSON requests have a 240-second maximum. HTTP 200/comments are insufficient; parse data/error events, require actual response content and `[DONE]`, and preserve incomplete output as partial.

The exposure timer and backend stop do **not** release Colab billing. `停止外部API` closes access; `停止全部` also stops owned backend processes. For end-runtime/expiry, separately release the exact owned allocation and verify server-side absence as directed by the lifecycle skill.
