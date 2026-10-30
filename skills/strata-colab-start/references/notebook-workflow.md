# Notebook form workflow

Use the cell title/form field, not a brittle screen coordinate. Read the live notebook before using these names.

- Cell 1 配置: `preset`, `apply_preset=False`, `model_quant`, `context_tokens=262144`, `kv_precision`, `kv_streaming`, `cuda_version`, `api_host=127.0.0.1`, `api_port=8080`. Presets only override quant/context/KV/streaming/reserve when `apply_preset=True`.

- Cell 2 初始化安全执行工具 defines helpers without downloading.
- Cell 3 可选 Drive 缓存: `mount_drive=False`, `use_drive_model_cache=False`. Mount/cache only if requested and access granted; Drive may reduce I/O performance and consumes user storage.
- Cell 4 硬件、预算和参数检查 reports detected hardware and blocking estimates. Re-run after configuration/hardware changes.
- Cell 5 获取固定源码: `fetch_source=True` only when authorized; retain `update_to_latest=False` unless the user requests an unverified upstream update.
- Cell 6 安装 + 可续传下载: both `install_and_download` and `accept_download_storage_and_build` must be deliberately enabled. Initial weights can be approximately 66–111 GB plus packing, MTP and environment overhead; use the current check's actual estimate/free space.
- Cell 7 应用配置并启动 / 停止 / 重启: `server_action` choices `不操作`, `启动`, `停止`, `重启`; startup deadline `startup_timeout_seconds` defaults to 900. Configuration changes require rechecking before restarting.
- Cell 8 短聊天: `run_chat=False` by default. Start with a small prompt/output budget only when inference is requested/approved. Optional tools are declarations, not authority to execute returned calls.
- Cell 9 长上下文压力测试: `run_long_context_test` and `accept_long_test_cost` are separate opt-ins. Preserve them off unless specifically approved.
- Cell 10 脱敏诊断: `show_diagnostics`, `log_tail_lines`; use redacted diagnostics rather than environment dumps or complete logs.

Colab's system Node process may occupy the default port 8080. During preflight, preserve that process and select a free loopback port; keep startup, exported URLs and test requests in agreement.

The current notebook validates context only through 262144 and uses a conservative normal-RAM estimate. For an approved longer context or supported low-RAM configuration outside these checks, use a bounded helper with the pinned upstream setup's verified flags and actual installation interpreter. Preserve the requested quant/context; derive the supported RoPE extension above the trained range. Confirm effective memory mode from the engine log before inference claims.

## Preset implications

The current presets are suggestions, not hardware guarantees:

- T4高RAM: Q2_0 / 65,536 context / q4_0 KV (lower precision)
- L4 and G4: IQ2_XS / 131,072 / int8 KV
- A10040: IQ2_XS / 262,144 / int8 KV
- A10080 and H100: IQ3_S / 262,144 / int8 KV
- 手动256K preserves the manual fields; default IQ2_XS / 262,144 / int8 KV

The context budget includes input, template/history, reasoning and output. T4/L4 presets reduce context and cannot satisfy an unchanged full-256K request. G4 is a resource label, not a definitive GPU identification.

CUDA 13 requires driver series 580+. CUDA 12 is experimental, requires its opt-in, and needs compatible driver/build support (series 525 is only a minimum family check). Do not install/change a Colab host driver. `k8v4` cannot use KV streaming. Vision, concurrency, MTP and larger context raise resource needs. Review the live checks rather than extrapolating throughput or RAM from GPU branding.
