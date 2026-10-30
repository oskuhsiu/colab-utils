# FastH3 primary-source lookup

Checked 2026-10-09 (UTC+8). URLs below are the recoverable primary sources; model
and repository `main` branches can move, so the listed commits are the revisions
observed during this lookup.

## Answer

FastVideo/FastVideo-Minimax-FastH3-Preview-v0.2 is a self-contained Diffusers
modular pipeline (35B, BF16) distilled for four DiT forwards. Its release contract
is the explicit shared-grid ladder `[999, 749, 500, 250]`, guidance scale 1.0,
and, for the trained sparse route, `VIDEO_SPARSE_ATTN_H3`, `VSA_sparsity=0.9`,
`VSA_tile_size=64`. Dense execution is allowed, but other step counts/grids are
off-distribution. FastVideo has an official LoRA entry point that inspects an
adapter header and infers VSA when it contains `to_gate_compress`.

There is official sm_89 code in FastVideo, but no direct L4 FastH3 benchmark in
the sources checked. NVIDIA identifies L4 as compute capability 8.9; FastVideo's
measured sm_89 numbers are on RTX 4090. Treat L4 execution as an explicit test
target, not an established result.

ComfyUI's current native H3 nodes and official T2V/I2V/R2V templates are public.
The closerAI page is public documentation, but its plugin/workflow download is
permission-gated; no public closerAI GitHub repository or downloadable workflow
was found in this bounded search. DiffSynth-Studio supports base/quantized H3 and
LightX2V 4-step examples, but I found no explicit FastVideo FastH3-v0.2 path.

## Evidence

**S1 — FastVideo HF release.** [Model card](https://huggingface.co/FastVideo/FastVideo-Minimax-FastH3-Preview-v0.2)
(README commit `d0b052d148db3d24fb39b702087f206484c30269`, 2026-08-28) states the
four-step ladder, shift-12 schedule, VSA 64-token tiles/90% sparsity, 768x1344,
124 frames, and 32x GB200 training. It says only `transformer/` differs from
base and `transformer_ref` is fetched from `MiniMaxAI/MiniMax-H3`. The card's
release tree shows 148 GB total; `transformer/` is 14 BF16 safetensor shards
(exact byte sizes are in the [HF tree API](https://huggingface.co/api/models/FastVideo/FastVideo-Minimax-FastH3-Preview-v0.2/tree/main/transformer?recursive=true&expand=true), latest file commits `11dd7d6`/`04ae4d1`),
`text_encoder/` is 14 shards/66.7 GB, and `vae/` is three shards
(5,061,033,024; 4,955,986,528; 398,539,336 bytes; commit `04ae4d1`).
`audio_vae/diffusion_pytorch_model.safetensors` is 605,429,340 bytes
(commit `11dd7d6`); `scheduler_config.json` is 97 bytes and the audio scheduler
config is 96 bytes. The [card](https://huggingface.co/FastVideo/FastVideo-Minimax-FastH3-Preview-v0.2/blob/main/README.md)
also warns that v0.1's generic `num_inference_steps=4` is wrong for this release.

**S2 — FastVideo code and LoRA.** Current FastVideo `main` was
`2b164405c3d15ed2d222d0582d6db09ffc5ee6b2` (2026-10-07). Its
[basic_fasth3.py](https://github.com/hao-ai-lab/FastVideo/blob/2b164405c3d15ed2d222d0582d6db09ffc5ee6b2/examples/inference/basic/basic_fasth3.py)
uses 5 sigma-grid points = 4 forwards, 0.9/64 VSA defaults, and guidance 1.0.
[basic_fasth3_lora_preview.py](https://github.com/hao-ai-lab/FastVideo/blob/2b164405c3d15ed2d222d0582d6db09ffc5ee6b2/examples/inference/basic/basic_fasth3_lora_preview.py)
loads a LoRA on `MiniMaxAI/MiniMax-H3`; `DenseLoRAPatch.from_adapter` checks for
`gate_compress`, infers VSA, and rejects `--no-vsa` when that payload is present.

**S3 — sm_89 evidence.** [FastVideo PR #1919](https://github.com/hao-ai-lab/FastVideo/pull/1919)
merged commit `8b51380` on 2026-10-06. It adds an opt-in sm_89 INT8-QK sparse
attention, fused-scale FP8 GEMM, and INT8 VAE epilogues; reported warm-server
results are RTX 4090 (54.6/43.9 s at 832x480; 154.6/132.8 s at 1344x768 for
V2/Trim). [NVIDIA's compute table](https://developer.nvidia.com/cuda/gpus)
places NVIDIA L4 at CC 8.9. No L4 run, memory result, or L4-specific FastH3
recipe was found.

**S4 — Kijai experimental files.** [HF tree](https://huggingface.co/Kijai/MiniMax-H3-experimental/tree/main)
was 102 GB at root commit `d8023be02fefbb3633b0cd335c3879f91177299d`
(2026-10-02). Relevant exact files: `minimax_h3_fastvideo_vsa_datafree_1300step_4step_int8_convrot.safetensors`
22,898,594,920 bytes, commit `641f2a0`; `minimax_h3_fl2va_pruned_w4a8_mixed.safetensors`
12,540,858,008 bytes, `0f82fa2`; `minimax_h3_ref2va_pruned_w4a8_mixed.safetensors`
11,770,657,048 bytes, `548222b`; `minimax_h3_video_vae_int8_convrot.safetensors`
3,171,670,912 bytes, `7f57059`; and `minimax_h3_lynnreal_light_vae_int8_convrot.safetensors`
2,137,493,384 bytes, `9e88553`. LoRAs include DMAD rank-39 (366,647,000 bytes,
`1db9d50`), FlashGen rank-13 (185,865,134, `709b3d5`), PDMD 2-step
(381,015,376, `c41575a`), and PDMD 4-step (558,735,392, `c41575a`). Its
[README](https://huggingface.co/Kijai/MiniMax-H3-experimental/blob/main/README.md)
requires ComfyUI 0.31.0; int8-convrot VAE speedups require 0.36.0.

**S5 — comfy-kitchen PR #90.** [PR #90](https://github.com/Comfy-Org/comfy-kitchen/pull/90)
merged `aa1ab22` on 2026-08-06. It adds `AsymW4A8Int8Layout`, grouped codebook
quantization, `w4a8_int8_linear`, CUDA dequant/GEMM, eager and Triton backends.
Current main (`be003b7`, 2026-10-02) keeps these symbols in
[`comfy_kitchen/tensor/w4a8_int8.py`](https://github.com/Comfy-Org/comfy-kitchen/blob/be003b7c23c5b01328657955b8bc5d3f073d868e/comfy_kitchen/tensor/w4a8_int8.py);
the layout declares `MIN_SM_VERSION=(8,0)`. PR text's test model is Kijai's
W4A8 FL2VA file and its example result is on a 5090, not L4.

**S6 — ComfyUI native nodes/templates.** Current ComfyUI master was
`a4b5a045e56fc334903db8457b728b64e006119c` (2026-10-09). In
[`comfy_extras/nodes_minimax_h3.py`](https://github.com/Comfy-Org/ComfyUI/blob/a4b5a045e56fc334903db8457b728b64e006119c/comfy_extras/nodes_minimax_h3.py),
the node classes are `EmptyMiniMaxH3LatentAV`, `MiniMaxH3ImageToVideo`,
`MiniMaxH3AddGuide`, `MiniMaxH3ReferenceToVideo`, `MiniMaxH3SigmaShift`, and
`MiniMaxH3FunControlNetApply`; the sigma node defaults to video/audio shifts
12/3. Official templates (workflow_templates main `8be1f8c`, 2026-10-08):
[T2V](https://github.com/Comfy-Org/workflow_templates/blob/main/templates/video_minimax_h3_t2v.json),
[I2V](https://github.com/Comfy-Org/workflow_templates/blob/main/templates/video_minimax_h3_i2v.json),
[R2V](https://github.com/Comfy-Org/workflow_templates/blob/main/templates/video_minimax_h3_r2v.json).
The T2V template records Comfy-Org model names/sizes: int8-convrot FL2VA 19.53
GB, Qwen3-VL NVFP4-AWQ 14.61 GB, and the int8 video/audio VAEs; these are the
Comfy-Org pack, distinct from the 148 GB FastVideo Diffusers repo.

**S7 — closerAI / DiffSynth boundary.** The author page
[closerAI-minimaxH3-Helper](https://closerai.douyoubuy.cn/2026/08/04/421622/)
(updated 2026-09-13) says the package is installed as
`custom_nodes/closerAI-minimaxH3-PromptHelper`, advertises 27+ nodes and FastH3
member distribution/RTX wheels, and explicitly says download requires permission
(599 coins for ordinary users; VIP/free for members). No public GitHub repo or
workflow download was found. DiffSynth's official
[MiniMax-H3 docs](https://github.com/modelscope/DiffSynth-Studio/blob/main/docs/en/Model_Details/MiniMax-H3.md)
document `MiniMaxH3Pipeline`, NF4/int8-convrot variants, 50 default steps, and
flow shifts 12/3; the model table includes LightX2V 4-step but no FastVideo
FastH3-v0.2 checkpoint or VSA-H3 contract.

## Uncertainty / Search boundary

No runtime, GPU, or L4 benchmark was executed here. The sm_89-to-L4 relation is
hardware taxonomy only; 4090 measurements must not be generalized to L4. The
FastVideo HF `main` branch and Kijai's experimental files may change; pin the
listed commits/OIDs. Search covered the specified official repositories, HF pages,
NVIDIA compute table, the closerAI author site, and DiffSynth source; it did not
attempt gated closerAI downloads or paid-member workflows.

## Main attention

Keep official FastVideo v0.2 (step-2900 training checkpoint, `[999,749,500,250]`) separate
from Kijai's `1300step` VSA file and from Comfy-Org's single-file int8/W4A8 pack.
For an L4-only test, use an sm_89-compatible dense/Triton path and record peak
VRAM/time; do not select the official FastH3 script's default `sm100a` profile.

## Addendum — Sol-Attn / VSA follow-up

**S8 — “PR17” is most likely PR #117.** The public closerAI page names the
`FastH3VSA` dependency as “comfy-kitchen PR 117” (the screenshot's `PR17` is
consistent with a clipped/missing final `1`); I found no public Comfy Kitchen
PR #17 matching this feature. [Comfy-Org/comfy-kitchen PR #117](https://github.com/Comfy-Org/comfy-kitchen/pull/117)
(`dae00a1`, merged 2026-08-29) is titled “Add int8 Sol-attention.” Its source
description explicitly says: 64-token query blocks route exact key blocks; VSA
mode uses `tail=False`, `block_len`, and `coarse_gate`; selection supports
adaptive `tau` or per-block `topk_ratio`; and the changed paths are
`comfy_kitchen/backends/eager/sol_attn.py`, `comfy_kitchen/backends/cuda/sage_attention/sol_attn*.cu`,
`sol_layout.cuh`, CUDA DLPack bindings, and `tests/test_sol_attn.py`.

The current public CUDA API is [`sol_attn`](https://github.com/Comfy-Org/comfy-kitchen/blob/main/comfy_kitchen/backends/cuda/__init__.py#L2543-L2629):
`sol_attn(q, k, v, tau=1.0, scale=None, sink_blocks=None, sink_q=None,
key_bias=None, topk_ratio=0.0, tail=True, block_len=None, coarse_gate=None,
token_aug=0)`, over `(B,T,H,128)` BF16/FP16 tensors. The chunked producer entry
[`sol_attn_chunked`](https://github.com/Comfy-Org/comfy-kitchen/blob/main/comfy_kitchen/backends/cuda/__init__.py#L2631-L2656)
accepts QKV chunks, `t`, `h`, RoPE frequencies, Q/K norm weights, optional
`kmean`/`vscale`, and returns `(out, kmean_next, vscale_next)`. The CUDA guard
requires SM80+; this is the generic Comfy Kitchen capability gate, not proof of
an L4 end-to-end workflow.

**S9 — Public Sol-Attn H3 implementation and SM89.**
[quzopl/ComfyUI-SolAttn-H3](https://github.com/quzopl/ComfyUI-SolAttn-H3) is a
public Apache-2.0 training-free Sol-Attn node for native H3. Its README records
CuTe backends for SM89/90/100/120 and measured Ada examples (L40 and RTX 4070
Ti), while warning that missing CuTe dependencies fall back to Triton. The
architecture table in [`kernel.py`](https://github.com/quzopl/ComfyUI-SolAttn-H3/blob/master/kernel.py#L11-L61)
maps `(8,9)` to `cute_sm89`; `load_sol_attn()` imports the public `sol_attn`
kernel API. Its [`attention.py`](https://github.com/quzopl/ComfyUI-SolAttn-H3/blob/master/attention.py#L0-L9)
documents H3's BHSD `(1, heads, S, 128)` input/output contract, and
`make_override` calls `sol_attn(qb,kb,vb,tau=...,thresh_type=...,kv_splits=...,
sink_start=...,sink_tokens=...)`. This is a public Sol-Attn reference with
SM89 coverage, but it is distinct from learned FastH3 VSA and has no L4 result.

**S10 — Public learned-VSA ComfyUI pack.**
[exportAnything/ComfyUI-FastH3-VSA](https://github.com/exportAnything/ComfyUI-FastH3-VSA)
is the closest public implementation to the screenshot's native FastH3 VSA
node: it uses Comfy Kitchen PR117's chunked Sol-Attn/VSA kernel, patches all 50
H3 blocks, requires complete gate weights, and enforces SM80+, head dimension 128,
one GPU. Its tested machine is RTX PRO 4500 Blackwell/SM120 (32 GiB); Linux,
other architectures, and less VRAM are explicitly unvalidated. Treat it as an
independent public reference, not evidence that closerAI's gated `PR17` code is
identical or that L4 works.

**S11 — FastVideo gate and selection paths.** In
[`fastvideo/models/dits/minimax_h3.py`](https://github.com/hao-ai-lab/FastVideo/blob/main/fastvideo/models/dits/minimax_h3.py#L179-L264),
`MiniMaxH3Attention` constructs `to_gate_compress = ReplicatedLinear(hidden_size,
inner_dim)` only when `VIDEO_SPARSE_ATTN_H3` resolves; `inner_dim =
num_attention_heads * attention_head_dim`, so the projection output is per-token
`[B,S,H*D]` and is unflattened to `[B,S,H,D]` before attention (lines 383-395).
The same file states base H3 has no gate and VSA students carry the trained gate.

In [`fastvideo/attention/backends/video_sparse_attn_h3.py`](https://github.com/hao-ai-lab/FastVideo/blob/main/fastvideo/attention/backends/video_sparse_attn_h3.py#L437-L482),
`_build_block_mask` pools tile scores, computes each video region's `span_topk`
from sparsity, and selects `torch.topk` indices; prefix keys remain dense. The
backend receives `gate_compress` as a parallel `[B,S,H,D]` tensor, and
[`video_sparse_attn_h3.py`](https://github.com/hao-ai-lab/FastVideo/blob/main/fastvideo/attention/backends/video_sparse_attn_h3.py#L899-L921)
adds the pooled coarse branch through `out += gate * softmax(pooled scores) *
pooled V`. On Ada/SM89, the route checks BF16/head-128/CC `(8,9)` and calls
[`sparse_sm89_attention`](https://github.com/hao-ai-lab/FastVideo/blob/main/fastvideo/attention/backends/minimax_h3_sparse_int8.py#L74-L128),
whose concrete signature is `(q, k, v, mask, vbs, *, int8_qk=True)` and whose
contract is forward-only BF16 `[B,H,S,128]`, 64-token masks, INT8 QK optional,
BF16 PV. This is the exact native FastVideo sm89 path; it is separate from the
Blackwell-only `sm100a` route.

## Addendum uncertainty

No public source tied the closerAI screenshot's private label “PR17” to a
specific repository commit. The PR117 identification is source-attributed from
the closerAI page and corroborated by the matching public Comfy Kitchen PR title,
not proof of closerAI implementation identity. The public Sol-Attn H3 and
exportAnything repositories provide reproducible reference code and constraints;
neither reports an L4 FastH3 generation.
