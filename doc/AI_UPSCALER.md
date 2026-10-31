# AI image and video enlarger

This adds Real-ESRGAN super-resolution as a post-processing step for the current
ComfyUI, FastH3, original H3, Wan and Qwen outputs. The default is **native 2×**.
For example, the T4 FastH3 preview at 512×288 becomes 1024×576; the L4 workflow
at 864×480 becomes 1728×960. Frame-wise video processing retains the source
frame rate and audio. Model inference may introduce detail or flicker, so judge
the enlarged result in motion before delivery.

## Choose an entry point

| Entry | Use |
| --- | --- |
| [Image ComfyUI workflow](../workflows/ai_upscale_image_2x.json) | Upload an RGB image and save a 2× PNG. |
| [Video ComfyUI workflow](../workflows/ai_upscale_video_2x.json) | Upload a short SDR clip, upscale its frames, rebuild the MP4 with its audio and fps. |
| [FastH3 L4 + 2× workflow](../workflows/fast_h3_l4_upscale_2x.json) | Generate once and save both the native clip and a second, enlarged clip. |
| [Colab notebook](../notebooks/AI_Media_Upscaler_Colab.ipynb) | Stream an existing image/video through the upscaler on a T4 or the current GPU. |
| [CLI](../scripts/media_upscale.py) | Process files from any existing pipeline; preserve PNG alpha and stream long videos with bounded frame memory. |

Matching `.api.json` files are beside each UI workflow. The three graphs use
ComfyUI core nodes; the FastH3 variant also uses the same FastH3 nodes as the
existing L4 workflow. Core node schemas were checked against the ComfyUI revision
already pinned by [fast_h3_lock.json](../scripts/fast_h3_lock.json).

```text
Image:  LoadImage --------------------------> ImageUpscaleWithModel -> SaveImage
        UpscaleModelLoader --------------------------^

Video:  LoadVideo -> GetVideoComponents -> frames -> AI upscale -> CreateVideo -> SaveVideo
                            |                                      ^
                            +---------------- audio + fps ---------+

FastH3: existing generation -> receipt + duration trim -> native MP4
                                          |
                                          +-> AI upscale -> enlarged MP4
                                               original audio + 24 fps
```

The core video graph holds the decoded frames and enlarged output tensors in RAM.
Use the streaming notebook/CLI for long clips or limited RAM. Its video path keeps
one frame and its output on the CPU and one padded tile on the inference device.
It does not extract a folder of every frame or interpolate frames.

## Models and selection

The catalog fixes each official release URL, byte count and SHA-256 in
[media_upscale_models.json](../scripts/media_upscale_models.json).

| Model ID | Native scale | Weight | Intended material |
| --- | --- | --- | --- |
| `realesrgan-x2plus` | 2× | 63.96 MiB | Default general image/video pass; avoids computing a 4× image just to deliver 2×. |
| `realesrgan-x4plus` | 4× | 63.94 MiB | General 4× output. |
| `realesrgan-anime-x4` | 4× | 17.11 MiB | Optional anime/illustration pass; 6 RRDB blocks instead of 23. |

These choices follow the official [model zoo](https://github.com/xinntao/Real-ESRGAN/blob/master/docs/model_zoo.md)
and [inference model definitions](https://github.com/xinntao/Real-ESRGAN/blob/master/inference_realesrgan.py).
Their suitability for a particular image remains a visual choice. The anime model
can deliver exact 2× by applying Lanczos 0.5 after native 4× inference. Asking the
native 2× model for 4× fails with a request to select a native 4× model.

Spandrel 0.4.2 loads the weights through PyTorch `weights_only=True`; BasicSR is
not installed. This uses the same loader family as ComfyUI's
[core upscale nodes](https://github.com/Comfy-Org/ComfyUI/blob/a4b5a045e56fc334903db8457b728b64e006119c/comfy_extras/nodes_upscale_model.py).
It avoids the earlier Colab BasicSR install failure recorded in the
[Qwen upscaler research](../plan/qwen-image-acceleration-and-upscaler-oss-scout.md).
The existing Qwen panel-manifest/reader pipeline continues to use its measured
Swin2SR backend; this new workflow can process its exported PNGs separately.

Real-ESRGAN source code is [BSD-3-Clause](https://github.com/xinntao/Real-ESRGAN/blob/master/LICENSE).
The official checkpoint releases do not specify a separate weight license;
the catalog records that distinction. Spandrel's package metadata and supported
architectures are documented in its [repository](https://github.com/chaiNNer-org/spandrel).

## ComfyUI

1. Download the selected model into `ComfyUI/models/upscale_models` using the CLI
   below. For the current FastH3 Colab runtime, the directory is
   `/content/fast-h3/ComfyUI/models/upscale_models`.
2. Import the appropriate `.json` UI workflow. Select the uploaded file in
   `LoadImage` or `LoadVideo`, then queue it. Outputs are under
   `ComfyUI/output/ai_upscale`.
3. For the combined FastH3 graph, edit the usual prompt, seed and generation
   settings, then queue. Its native branch remains identical to the original
   graph, including VSA evidence and duration trimming; enlargement begins at
   the trimmed frames, with the corresponding audio.

Use the combined variant directly in ComfyUI. `fast_h3_colab.py` retains its
existing native-output validation contract; for that CLI, finish/fetch generation
first and run `media_upscale.py video` on the resulting `video.mp4`.
The standalone video graph accepts the current 8-bit SDR clips. For transparent
images use the notebook/CLI PNG path, which resizes alpha separately.

To export a 4× or anime variant without editing JSON links:

```bash
python3 scripts/media_upscale_workflow.py --kind image \
  --model realesrgan-anime-x4 --scale 2 --output-dir /tmp/anime-upscale
python3 scripts/media_upscale_workflow.py --kind video \
  --model realesrgan-x4plus --scale 4 --output-dir /tmp/video-upscale-4x
```

## Colab and command line

In [AI_Media_Upscaler_Colab.ipynb](../notebooks/AI_Media_Upscaler_Colab.ipynb), run A
once, then B for each input. Set `MEDIA_TYPE`, `INPUT_PATH`, `MODEL` and `SCALE`.
An empty input path uses `OUTPUT_PATH` if the setup/job cells are run in an existing
generation notebook. The result is exposed as `UPSCALED_OUTPUT_PATH`, with its
receipt beside it. Only the selected weight is downloaded. CUDA uses FP16 when
the model supports it; CPU uses FP32. Start with tile 192 and padding 16; reduce
tile size if a particular GPU job runs out of memory.

For a local environment with PyTorch already installed:

```bash
python3 -m pip install spandrel==0.4.2 'Pillow>=10.0'
python3 scripts/media_upscale.py download

python3 scripts/media_upscale.py image path/to/panel.png \
  --output path/to/panel-2x.png
python3 scripts/media_upscale.py video path/to/video.mp4 \
  --output path/to/video-2x.mp4
```

For the optional anime model, first download it, then select it on the job:

```bash
python3 scripts/media_upscale.py download --model realesrgan-anime-x4
python3 scripts/media_upscale.py image path/to/panel.png \
  --model realesrgan-anime-x4 --scale 2 --output path/to/panel-anime-2x.png
```

To populate ComfyUI's model directory, no inference dependencies are needed:

```bash
python3 scripts/media_upscale.py download \
  --model-dir /content/fast-h3/ComfyUI/models/upscale_models
```

Inputs stay intact. An existing output or receipt causes an error; choose a new
filename for another take. Stage outputs and weights on local disk such as
`/content`, then copy completed files to Drive or download them. Publication uses
local hard links to prevent overwriting another result; Google Drive FUSE is not
a supported working directory.

The streaming video path accepts constant-frame-rate, square-pixel, unrotated,
8-bit SDR video and writes H.264 MP4 at CRF 18. It preserves rational fps and frame
count, copies AAC audio streams and converts other audio to AAC. VFR, HDR/high
bit depth, rotation metadata and non-square pixels receive explicit errors;
convert those inputs deliberately before upscaling. Animated or high-depth
images also require conversion to an explicit 8-bit still image. JPEG EXIF
orientation is normalized to the displayed orientation before inference.

Each `OUTPUT.upscale.json` records input/output/model hashes, native and delivery
scale, device, precision, tiles, inference time and validation. Video publication
requires complete decode plus dimensions, frame count, fps, durations and audio
checks. Image publication requires PNG decode and dimensions checks. These are
technical checks; frame-wise Real-ESRGAN has no temporal state, as shown by its
[official video implementation](https://github.com/xinntao/Real-ESRGAN/blob/master/inference_realesrgan_video.py).
Inspect flicker, edges and fine text in the enlarged result.

## Rebuild and verification

```bash
python3 scripts/media_upscale_workflow.py
python3 scripts/build_media_upscaler_notebook.py
python3 -m unittest discover -s tests -p 'test_media_upscale*.py' -v
```

Use an environment containing PyTorch, NumPy and Pillow for the inference/media
tests; the base interpreter skips those tests when their dependencies are absent.
The graph and notebook contract tests run without those dependencies.

Validated on 2026-10-11: **23 upscaler/graph/notebook tests and 12 existing FastH3
workflow tests passed**. All three official weights passed hash verification,
Spandrel loading and real CPU FP32 inference on an odd-size tiled input.
The default native 2× model also processed a full-size FastH3 image frame from
512×288 to 1024×576, and a reduced-size, full-duration video fixture from 128×72
to 256×144. The video retained **120 frames, 24 fps, exactly 5 seconds and
32 kHz stereo AAC**; independent decoding found its copied audio identical.
Image inference took 5.30 seconds and the small-video inference took 28.17 seconds
on the tested CPU; these are not T4 speed estimates.

These are historical validation results; the original per-run media and receipts
are not prerequisites for this workflow.

The enlarged image and five video frames were visually inspected. There was no
real-time playback or audio listening review. New graph schemas, links and widget
serialization were checked offline. The initial implementation used **0 additional
Colab CU** and allocated no GPU session; the native ComfyUI upscale graphs remain
untested live.

A subsequent historical validation tested the streaming CLI on Colab A100 80GB with CUDA FP16, RealESRGAN x2plus and a complete H3 I2V clip:
832×480 → 1664×960, 124 frames at 24 fps. The local copies passed full decoding and
hash checks; decoded audio PCM was identical to the source. Tile 192 took 84.27 s
including CLI load/encode/verification (79.23 s inference); tile 1024 took 15.77 s
(10.84 s inference). Since the source fits within 1024×1024, the latter runs one
tile per frame. On this measured A100 workload, use `--tile 1024`; smaller GPUs or
larger sources still need their own memory check. These timings exclude dependency
installation and weight downloads. This establishes this CLI's actual CUDA path,
not live notebook execution, native Comfy node execution or temporal quality.
