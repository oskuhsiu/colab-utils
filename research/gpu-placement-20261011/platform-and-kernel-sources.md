# Platform and kernel evidence for GPU placement

Checked 2026-10-11. This is a source report; placement decisions remain with the main agent.

## Answer

| Platform | Hardware facts relevant to these trials | Kernel/dtype boundary |
|---|---|---|
| Colab L4 | NVIDIA Ada, SM89, 24 GB; NVIDIA lists native FP16, BF16, FP8, INT8 and FP32 on the product page (S1). | Current Comfy Kitchen's FP8 layout is SM >= 8.9; NVFP4 is native only on SM >= 10.0/Blackwell (S9). Sol/VSA attention is CUDA SM80+ and requires BF16 or FP16 inputs (S10). |
| Colab T4 | NVIDIA Turing, SM75, 16 GB GDDR6; product page lists FP32, FP16, INT8 and INT4 (S2). Turing's Tensor Cores are documented for FP16 and integer 8/4/1-bit inputs (S4). | Comfy's MiniMax H3 contract is BF16/FP32 only (S7). On a T4, current ComfyUI reports manual cast to FP32; forcing FP16 can produce NaNs because H3 activations exceed FP16 range (S8). INT8 attention is available on SM75+, but Sol/VSA is SM80+ (S10, S11). |
| Kaggle Notebook (current) | Kaggle staff announced P100 retirement after 2026-09-15; T4x2 remains, with two 16 GB T4 GPUs. A staff reply says T4x2 is the only Notebook offering at present; L4 is limited to a small set of competitions (S12). | Treat each T4 as a separate 16 GB device for single-GPU model residency; multi-GPU use would require explicit sharding/parallel code. The official technical-spec page still lists an old P100 row, so that row is stale against S12. |
| Kaggle Notebook (old P100 row) | NVIDIA P100 is Pascal GP100, SM60, with 12/16 GB HBM2 (S3, S5). | Pascal has native FP16 arithmetic but no Tensor Cores; NVIDIA's current architecture matrix lists Pascal's last CUDA toolkit support as CUDA 12.x (S5). Current Comfy Kitchen CUDA wheels require CUDA Runtime >=13.0 and driver r580+, so the current wheel path is unavailable on P100 (S9). |

Wan2GP's profiles label profile 4 as 32 GB+ RAM / 12 GB+ VRAM and profile 5 as 16 GB+ / 10 GB+; these are generic thresholds, not H3 guarantees (S13). Its H3 handler exposes BF16, Quanto INT8, NVFP4 AWQ, GGUF Q4 and Q2 text encoders (S14). v17.17 claims 5–6 GB VRAM for 480p H3 but gives no universal guarantee (S15). Local A100 evidence: H01 profile 4 ~4 GiB GPU/~55 GiB CPU tree; H02 and H07 succeeded.

Kandinsky 6 official inference examples load `torch_dtype=torch.bfloat16`; the Lite metadata lists F32/BF16 tensors (S16). A pinned Comfy snapshot explicitly declares `supported_inference_dtypes = [torch.bfloat16, torch.float32]` (S23). The upstream setup table names Hopper SM90 and Ampere/Ada/consumer Blackwell SM80/86/89/120/121; that install preset does not prove the separate Comfy FP32/SDPA path is incompatible with T4. No SM75/SM60 runtime success or memory guarantee was found; K6 Lite's official distilled point is 10 steps at 864x480, 121 frames (S16).

LTX-2.5's official minimum is 32 GB VRAM, 32 GB system RAM, 100 GB free storage, CUDA >=12.7; recommended is A100 80 GB/H100 and 64 GB+ RAM (S18). The official Comfy node repository provides low-VRAM loaders and a lighter single-stage 2.5 workflow, but does not establish a supported 16/24 GB guarantee (S19, S20).

## Evidence

S1 — NVIDIA, “L4 Tensor Core GPU” (direct read, product specs): https://www.nvidia.com/en-us/data-center/l4/ — Ada; 24 GB; FP16/BF16/FP8/INT8/FP32.

S2 — NVIDIA, “T4 Tensor Core GPU” (direct read, product specs): https://www.nvidia.com/en-us/data-center/tesla-t4/ — Turing; 16 GB; FP32/FP16/INT8/INT4.

S3 — NVIDIA, “Tesla P100 PCIe Data Sheet” (direct read, PDF): https://www.nvidia.com/content/dam/en-zz/Solutions/Data-Center/tesla-p100/pdf/nvidia-tesla-p100-PCIe-datasheet.pdf — Pascal; 12/16 GB HBM2; FP16.

S4 — NVIDIA, “Turing Tuning Guide” (direct read, PDF): https://docs.nvidia.com/cuda/hopper-tuning-guide/pdf/Turing_Tuning_Guide.pdf — Turing Tensor Cores use FP16; integer matrix multiply supports 8/4/1-bit.

S5 — NVIDIA, CUDA architecture matrix and Pascal guide (direct read): https://docs.nvidia.com/datacenter/tesla/drivers/latest/cuda-toolkit-driver-and-architecture-matrix.html and https://docs.nvidia.com/cuda/pascal-tuning-guide/ — Pascal 6.0; native FP16; last toolkit support CUDA 12.x.

S7 — Comfy-Org, `supported_models.py` (direct read, current master): https://github.com/Comfy-Org/ComfyUI/blob/master/comfy/supported_models.py#L3648 — `MiniMaxH3.supported_inference_dtypes = [torch.bfloat16, torch.float32]`.

S8 — Comfy-Org issue #16507 (direct read, open issue): https://github.com/Comfy-Org/ComfyUI/issues/16507 — T4 manual-casts H3 to FP32; FP16 prototype overflows/NaNs; no core FP16 solution.

S9 — Comfy Kitchen README (direct read): https://github.com/Comfy-Org/comfy-kitchen/blob/main/README.md — FP8 layout SM89+, NVFP4 SM10+, CUDA wheels require CUDA >=13.0/r580; source build can target 75 virtual.

S10 — Comfy Kitchen `__init__.py` (direct read): https://github.com/Comfy-Org/comfy-kitchen/blob/main/comfy_kitchen/__init__.py#L2587 — Sol-Attn CUDA requires SM80+ and BF16/FP16 inputs.

S11 — Comfy Kitchen `sage_attention.py` (direct read): https://github.com/Comfy-Org/comfy-kitchen/blob/main/comfy_kitchen/sage_attention.py#L1735 — INT8 attention requires SM75+.

S12 — Kaggle Team, “Sunsetting the NVIDIA Tesla P100 GPU” (official page; search extraction, open page was JS-empty; current crawl): https://www.kaggle.com/discussions/product-announcements/735239 — P100 retired 2026-09-15; T4x2 two×16 GB; only T4x2 currently; L4 limited to select competitions.

S13 — Wan2GP `run-docker-cuda-deb.sh` (direct read): https://github.com/deepbeepmeep/Wan2GP/blob/main/run-docker-cuda-deb.sh#L707 — profile RAM/VRAM thresholds.

S14 — Wan2GP MiniMax H3 handler (direct read): https://github.com/deepbeepmeep/Wan2GP/blob/main/models/minimax_h3/minimax_h3_handler.py#L2220 — H3 dtype BF16 and text-encoder variants.

S15 — Wan2GP README (direct read): https://github.com/deepbeepmeep/Wan2GP/blob/main/README.md#L244 — v17.17 MMGP H3 VRAM claim.

S16 — Kandinsky 6 Lite distilled model card (direct read): https://huggingface.co/kandinskylab/Kandinsky-6.0-Lite-distill-5s-Diffusers — BF16 example, F32/BF16 tensors, 10 steps, 864x480, 121 frames.

S17 — Kandinsky Lab, official repository (direct read): https://github.com/kandinskylab/kandinsky-6/blob/main/README.md#L211 — setup GPU table starts at SM80 except Hopper SM90.

S23 — Kandinsky Lab, pinned Comfy `supported_model.py` (root-fetched direct read; local copy `research/gpu-placement-20261011/sources/k6-supported_model.py:22`): https://github.com/kandinskylab/kandinsky-6/blob/f19c9b8ec2fcea5d391f5391983a540fc5e004da/comfyui/kandinsky6/supported_model.py — explicit BF16/FP32 inference dtype contract.

S18 — LTX official system requirements (direct read): https://docs.ltx.io/open-source-model/getting-started/system-requirements — 32 GB VRAM/RAM minimum, 100 GB storage, CUDA 12.7+.

S19 — Lightricks ComfyUI-LTXVideo (direct read): https://github.com/Lightricks/ComfyUI-LTXVideo/#low-vram — low-VRAM loaders/offload path.

S20 — Lightricks 2.5 workflow notes (direct read): https://github.com/Lightricks/ComfyUI-LTXVideo/blob/master/example_workflows/2.5/README.md — single-stage is lighter; default transformer is BF16.

S21 — Kaggle, “Getting Started on Kaggle” (official page; search extraction, open page was JS-empty): https://www.kaggle.com/docs/notebooks — 12-hour CPU/GPU session, 20 GB auto-saved working disk, T4x2 4 cores/29 GB RAM, Internet default for new notebooks, competition submissions may disable Internet.

S22 — Kaggle, “Efficient GPU Usage Tips” (official page; search extraction): https://www.kaggle.com/docs/efficient-gpu-usage — weekly GPU quota is 30 hours or sometimes higher depending on demand/resources.

## Uncertainty / Search boundary

- Kaggle's official docs page was retrievable only as a search extraction; its current technical table still lists P100 and is contradicted by the later staff retirement announcement. I did not treat the stale P100 row as current availability. The same docs state 12-hour CPU/GPU sessions, 20 GB `/kaggle/working`, 4 CPU cores, 29 GB RAM for T4x2, Internet on by default for new notebooks, and competition submissions may disable Internet (S21; search extraction).
- Kaggle GPU quota is documented as 30 hours per week “or sometimes higher depending on demand and resources,” so the exact per-account quota is not guaranteed (S22; search extraction): https://www.kaggle.com/docs/efficient-gpu-usage.
- No official H3 W6A8 success matrix for SM75 or SM60 was found. Current ComfyUI release notes confirm W6A8 format support, but that does not establish a T4/P100 kernel path. K6's upstream SM80+ install table does not establish incompatibility of Comfy FP32/SDPA on T4; no runtime receipt was found. No LTX-2.5 below-32-GB VRAM guarantee was found.
- Local benchmark receipts are supplied project evidence, not public-source hardware guarantees.

## Main attention

Key boundaries: Kaggle T4x2 only (16 GB each); H3 T4 FP32; Sol/VSA SM80+; P100 SM60 outside current CUDA13/comfy-kitchen wheels; K6 Comfy BF16/FP32 with T4 runtime unknown; LTX minimum 32 GB VRAM.
