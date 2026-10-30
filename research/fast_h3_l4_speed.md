# FastH3 L4 timing and hardware comparison

Checked 2026-10-09. Latest Luna/max trials used 864×480, 124 model frames trimmed to 120 frames / 5 seconds, 4 Euler steps, video/audio shifts 12/3 and 200 native VSA calls. Installation and model download are outside the per-clip total.

| Entry | Measured total | Measured VSA including first-forward loading | First iteration | Measured tail of remaining three iterations |
| --- | ---: | ---: | ---: | ---: |
| Notebook | 181.62 s | 98.6004 s | 69.55 s | 29.0504 s |
| ComfyUI + synthetic LoRA | 156.19 s | 86.8137 s | 57.65 s | 29.1637 s |

If each forward costs the mean of the final three, estimated four-step sampling is 38.73/38.88 s. Estimated first-iteration loading overhead is 59.87/47.93 s; subtracting that estimate from total gives 121.75/108.26 s for a full clip with text encoding/VAE/save/verification. These are estimates, not warm-run measurements. They assume the next run avoids the same first-forward loading overhead; dynamic offload or a changed graph can invalidate that assumption. Subtracting the entire first iteration would leave only three forwards.

The calculation is `steady_step = (measured_VSA - first_iteration) / 3`, then `estimated_sampling = steady_step * 4` and `estimated_total_without_first_load = measured_total - (first_iteration - steady_step)`.

Pinned ComfyUI [model_trange source](https://github.com/Comfy-Org/ComfyUI/blob/a4b5a045e56fc334903db8457b728b64e006119c/comfy/utils.py#L1265) changes progress-bar start time after the second iteration to estimate a rate with load overhead removed. Its 37–38 s display is not an independently timed four-step run.

NVIDIA [L4 specs](https://www.nvidia.com/en-us/data-center/l4/) report 30.3 FP32 TFLOPS, 24 GB memory, 300 GB/s and tensor figures marked as sparsity-assisted; NVIDIA [RTX 4060 Ti specs](https://www.nvidia.com/en-us/geforce/graphics-cards/40-series/rtx-4060-4060ti/) report 22 shader TFLOPS and 8/16 GB variants. The FP32 ratio is 1.38; it is not a prediction for this mixed INT8/BF16 pipeline. The author's local 4060 Ti 8 GB time of 359.88 s compared with our 181.62/156.19 s implies 1.98/2.30× speed relative to total time. Prompts, kernels, framework versions, offload and measurement scope differ, so this is contextual comparison, not a controlled GPU benchmark. The article's Blackwell server numbers use another hardware/backend configuration.

Observed server logs show dynamic VRAM staging, 21,833 MB DiT and 14,956 MB text encoder, and emulated NVFP4; all components do not remain simultaneously resident on L4. Actual memory-transfer/init/decoder overhead must be measured separately before attributing time entirely to GPU peak arithmetic.

Evidence: `artifacts/fast-h3-skill-trials/20261009/round03` and `round04` metrics/server logs/local media. No new GPU benchmark was started for the warm estimate.
