# Open-Source Scouting Report: Agent Control of Colab for MiniMax-H3

> Decision Verdict: Option A — Direct Adoption
> Estimated MVP Delivery: 1–2 days after account authentication and GPU allocation; planning estimate, not a measured delivery time
> Primary Recommendation: Google's `googlecolab/google-colab-cli`

Research date: 2026-09-23. This is a selection and implementation plan. No Colab runtime was allocated and no compute units were spent.

## 1. Requirement Scope and Boundaries

- Core Business Loop: A local agent submits a MiniMax-H3 inference job to the user's Colab GPU, collects the resulting video and execution record, and releases the runtime.
- Target Delivery Type: CLI, invoked by the agent's existing terminal tool.
- Licensing Constraint: Personal/internal tool; prefer permissive control software. Model weights have separate terms.
- Existing state: This workspace contains no implementation. Local `uv` and Python are available; `colab` is not on PATH.
- Budget: Use the user's existing Google AI Pro Colab allowance. Google One Help confirms 200 CCUs for AI Pro, and Colab's FAQ describes monthly deposits into the account's Colab balance. The benefit rollout was announced September 22, 2026. [AI Pro benefits](https://support.google.com/googleone/answer/14534406?hl=en), [Colab FAQ](https://research.google.com/colaboratory/faq.html), [rollout announcement](https://developers.googleblog.com/colab-is-now-part-of-your-google-ai-plan/).
- Completion evidence for the eventual implementation: The agent authenticates as the intended account, records the allocated GPU and actual memory, executes one H3 job, retrieves a playable MP4 and logs, and confirms that its runtime has been released.

**GPU correction and target.** A V100 has 16 or 32 GB, so it cannot provide more than 32 GB per GPU. A100 hardware has 40/80 GB variants; H100 hardware has 80 GB and larger variants. The official Colab CLI accepts `A100`, `H100`, and `G4` requests, but accepted command values are not proof that every tier can allocate each type. [NVIDIA hardware reference](https://docs.nvidia.com/heavyai/installation-and-configuration/system-requirements/hardware), [NVIDIA GPU specifications](https://docs.nvidia.com/datacenter/tesla/mig-user-guide/supported-gpus.html), [CLI allocation implementation](https://github.com/googlecolab/google-colab-cli/blob/main/src/colab_cli/commands/session.py).

| Runtime target | Memory basis | Use in this project |
| :--- | :--- | :--- |
| A100 | 40 or 80 GB hardware variants; measure the assigned device | Initial target for quantized/offloaded H3 |
| H100 | 80 GB or larger hardware variants; measure the assigned device | More headroom if the account can allocate it |
| G4 | Google Cloud's G4 family uses RTX PRO 6000; NVIDIA specifies 96 GB for the full Blackwell Server GPU | Additional candidate; verify the actual Colab device and software compatibility |
| V100 | 16/32 GB | Does not satisfy the stated memory threshold |

The G4 mapping is a hardware-family inference, not a measurement of this account's Colab allocation. [Google GPU machine types](https://docs.cloud.google.com/compute/docs/gpus), [RTX PRO 6000 specifications](https://www.nvidia.com/en-us/data-center/rtx-pro-6000-blackwell-server-edition/).

**Model fit.** The model is MiniMax-H3. Its official architecture includes a 33B transformer and Qwen3-VL-32B encoder; its reference serving example uses four GPUs. More than 32 GB alone does not establish that an unmodified BF16 deployment fits. For the first single-GPU experiment, use an existing quantized/offloaded inference path. [Official H3 repository](https://github.com/MiniMax-AI/MiniMax-H3).

DiffSynth-Studio documents an H3 NF4 example with CPU offload and a minimum of 7 GB VRAM at its example settings. That is an upstream capability claim, not a benchmark performed here. Its host-RAM, disk, runtime, and output-quality behavior still need validation on the chosen Colab allocation. ComfyUI also has native H3 workflows if a visual workflow becomes necessary. [DiffSynth H3 documentation](https://github.com/modelscope/DiffSynth-Studio/blob/main/docs/en/Model_Details/MiniMax-H3.md), [ComfyUI H3 guide](https://docs.comfy.org/tutorials/video/minimax/minimax-h3).

## 2. Shortlisted Candidates

Counts and latest default-branch commit timestamps below were retrieved directly from GitHub's REST API on the research date. Main checked the two Google repositories; Luna collected the `colabctl` data. Ratings are project-fit judgments, not security certifications.

| Repository | URL | Stars | Last Commit (UTC) | Tech Stack | License | Risk Level | Rating |
| :--- | :--- | ---: | :--- | :--- | :--- | :--- | :--- |
| Google Colab CLI | [googlecolab/google-colab-cli](https://github.com/googlecolab/google-colab-cli) | 1,275 | 2026-09-22 22:21:36 | Python CLI, Colab backend, Jupyter | Apache-2.0 | Warning: young project; documentation drift | 4.5/5 |
| Google Colab MCP | [googlecolab/colab-mcp](https://github.com/googlecolab/colab-mcp) | 1,027 | 2026-04-01 20:41:35 | Python MCP bridge, browser notebook | Apache-2.0 | Warning: client requirements; slower repository activity | 3/5 |
| colabctl | [mandipadk/colabctl](https://github.com/mandipadk/colabctl) | 0 | 2026-07-14 22:27:42 | Python CLI, SDK, MCP, multiple transports | Apache-2.0 | Warning: one contributor; additional abstraction | 2.5/5 |

Evidence: [CLI repository metadata](https://api.github.com/repos/googlecolab/google-colab-cli), [CLI commit](https://github.com/googlecolab/google-colab-cli/commit/e25c2655c7ff2fffb7e6c493c51a910d5c461a0b), [MCP repository metadata](https://api.github.com/repos/googlecolab/colab-mcp), [MCP commit](https://github.com/googlecolab/colab-mcp/commit/b9ab3899e0f1fa493390b1fd6d54aa2e464ecdf1).

Additional evidence: [colabctl metadata](https://api.github.com/repos/mandipadk/colabctl), [colabctl commit](https://github.com/mandipadk/colabctl/commit/839c5e05).

Luna's discovery searches covered both `site:github.com colab agent control MCP CLI` and `site:github.com "awesome-colab"`, plus browser variants and Colab topic tags. It also screened [keys-i/colab-cli](https://github.com/keys-i/colab-cli), an independent Rust implementation with five stars and one contributor, and [GoLab](https://github.com/hoangnecon/golab), a browser MCP bridge without documented server-side GPU allocation/termination. Neither supplies a needed advantage over the official CLI for this MVP.

## 3. Five-Pillar Due Diligence

### googlecolab/google-colab-cli

- Maintenance & Governance: Published by Google Colab, officially announced June 5, 2026, and updated within one day of this review. Luna observed no GitHub releases, but PyPI independently confirms package version 0.7.2 was published September 22. The project is young; a bus factor of three has not been established. [Announcement](https://developers.googleblog.com/introducing-the-google-colab-cli/), [PyPI package metadata](https://pypi.org/pypi/google-colab-cli/json).
- Community Health: 181 forks at retrieval; Luna counted 16 contributors and 82 total PRs, not 82 open PRs. Public discussions exist. These counts do not establish maintainer independence, organic star growth, or support capacity.
- Setup Friction: macOS/Linux support; Python 3.12 or newer. Install with `uv`, authenticate the user's Google account, then invoke the CLI. Initial Google consent remains an interactive step. [README](https://github.com/googlecolab/google-colab-cli), [package metadata](https://github.com/googlecolab/google-colab-cli/blob/main/pyproject.toml), [authentication design](https://github.com/googlecolab/google-colab-cli/blob/main/docs/04_automation_and_utility.md).
- Modularity & Reusability: Covers provisioning, execution, file transfer, logs, usage reporting, and teardown through separate commands. Estimated fit exceeds 85% of the control loop; H3 inference itself remains a workload script. Consumer Colab remains a proprietary backend dependency.
- Supply Chain & Licensing: Apache-2.0; use the official package and record its tested version. Dependency declarations and a lockfile are visible. No dependency/CVE audit was performed, so a clean vulnerability status is not asserted.
- Summary: Best match for a terminal-capable agent. Its explicit lifecycle and file commands suit unattended job orchestration after login. Documentation needs checking against the installed version: the README says ADC is the authentication default, whereas current source defaults to OAuth2. Specify `--auth oauth2` explicitly. [CLI entry point](https://github.com/googlecolab/google-colab-cli/blob/main/src/colab_cli/cli.py).

### googlecolab/colab-mcp

- Maintenance & Governance: Official Google Colab project, but the last default-branch commit is about six months old. This passes the 12-month shortlist screen but misses the preferred 1–3-month cadence. The current README says external contributions are not being accepted.
- Community Health: 209 forks at retrieval, with discussions used for intake. Contributor independence, organic growth, and bus factor remain unverified.
- Setup Friction: Install/use `uv`, configure the local MCP client, and open the Colab notebook in a browser. The client must support dynamic tool-list notifications (`notifications/tools/list_changed`).
- Modularity & Reusability: Appropriate for adding, editing, rearranging, and executing notebook cells. The browser bridge adds a dependency that the terminal workflow does not need. Complete unattended GPU provisioning and artifact recovery were not runtime-tested.
- Supply Chain & Licensing: Apache-2.0. The documented Git-based launcher follows a moving revision unless pinned. No dependency/CVE audit was performed.
- Summary: Good alternative when the notebook itself must be the interactive workspace. Less suitable for the requested script-and-results workflow. Current repository guidance takes precedence over the launch article's earlier invitation for contributions. [MCP README](https://github.com/googlecolab/colab-mcp), [official MCP announcement](https://developers.googleblog.com/announcing-the-colab-mcp-server-connect-any-ai-agent-to-google-colab/).

### mandipadk/colabctl

- Maintenance & Governance: Luna observed one contributor, seven PRs, and five releases; latest release was v0.5.0 on June 29, 2026. Recent activity meets the preferred three-month window, but ownership is concentrated.
- Community Health: Zero stars at retrieval; independent adoption is not established.
- Setup Friction: Adds a Python CLI/SDK/MCP layer. Its default transport delegates to the official CLI; browser and native transports add setup choices.
- Modularity & Reusability: Job execution, results, files, and stop operations cover much of the requested loop. The roadmap reports testing against Colab Pro. That is not a test of this user's AI Pro account.
- Supply Chain & Licensing: Apache-2.0. Its security policy identifies credentials, proxy tokens, native transport, and cloudpickle marshalling as relevant surfaces. No dependency audit was performed.
- Summary: Potentially useful for a future Python SDK or detached-job requirement. The present task needs only the official CLI, so another transport layer is unnecessary. [README](https://github.com/mandipadk/colabctl), [roadmap](https://github.com/mandipadk/colabctl/blob/main/ROADMAP.md), [security policy](https://github.com/mandipadk/colabctl/blob/main/SECURITY.md).

## 4. Architectural Decision Verdict

- Recommended Path: **Option A — Direct Adoption** of the official Colab CLI.
- Key Justification: It already implements the required control interface on this Mac, works with consumer Colab sessions, and exposes execution, artifact retrieval, and resource cleanup without a core modification. Google explicitly presents it for terminal-based agents. [Google's CLI announcement](https://developers.googleblog.com/introducing-the-google-colab-cli/).

```text
Local agent
    |
    v
Official Colab CLI -- Google account OAuth
    |
    v
Consumer Colab GPU -- H3 workload script
    |
    +--> MP4 + logs downloaded locally
    |
    +--> runtime released
```

| Control approach | Decision for this requirement |
| :--- | :--- |
| Official CLI | Primary interface; full job lifecycle in terminal commands |
| Official MCP | Alternative for live notebook collaboration |
| Browser automation | Fallback for account/UI interactions; unnecessary as the main execution mechanism |
| Custom consumer REST client | Adds maintenance of backend details already handled by the official CLI |
| Colab Enterprise API | Separate Google Cloud product and billing path; not the route for spending this consumer Colab allowance |
| SSH | Use the CLI's supported SSH command only if a shell/IDE workflow is needed; not required for the MVP |

The Enterprise REST documentation and pricing describe cloud resources and accelerator charges. Do not treat consumer Colab CU as that product's billing credit. [Enterprise REST API](https://docs.cloud.google.com/colab/docs/reference/rest), [Enterprise pricing](https://cloud.google.com/colab/pricing).

**Budget behavior:** read `colab usage` before allocation and during the job. Its rate aggregates all active assignments. With only this job active, approximate remaining hours as `remaining CU / current CU per hour`; setup and idle allocation also consume the available runtime budget. Measure CU per completed clip before estimating monthly output. Do not hard-code a claimed A100 hourly rate. [Usage command design](https://github.com/googlecolab/google-colab-cli/blob/main/docs/04_automation_and_utility.md).

**Resource limits:** selecting high system RAM does not increase a GPU's VRAM. Hardware access and runtime lifetime remain subject to Colab availability and account entitlement. AI Pro's allowance is verified; allocation of a particular GPU to this account has not been verified. [Colab resource limits](https://research.google.com/colaboratory/faq.html).

**Model licensing:** MiniMax-H3 uses its own Community License, including territory and commercial conditions. Apache-2.0 licensing of the controller does not change the model's terms. Deployment-location applicability remains to be established before running weights; this report does not determine legal eligibility. [H3 license](https://huggingface.co/MiniMaxAI/MiniMax-H3/blob/main/LICENSE).

## 5. Minimalist MVP Plan (1-1-1-1 Rule)

- Core User Story: As the account owner, I can give my agent one H3 inference task and receive a local video plus a record of the run.
- Starter Architecture: Official CLI, one versioned Python inference script, and a thin local orchestration command. Use the existing Google OAuth flow; create no application login system.
- One Core Interface: Proposed `./run-h3 --prompt "..."`, invoking the CLI internally.
- One Core Data Entity: A local JSON file for each run; no database.
- Minimal Schema Draft:

```text
Entity: Run
- id: string
- session_name: string
- model_revision: string
- inference_settings: object
- hardware_and_memory: object
- cu_before_after: object
- status: string
- output_path: string
```

- Milestones:
  - Phase 1: Authenticate the intended account; request A100; inspect `nvidia-smi`, free VRAM, system RAM, disk, and BF16 support; run one small upstream NF4/offload example; download and validate its MP4; save a run record; stop the session.
  - Phase 2: Wrap that successful path in the single command, pin working revisions, validate input, enforce a runtime budget, and clean up on ordinary errors/interruption. Confirm the backend session is gone after cleanup. Download artifacts before teardown; session-local files are ephemeral.
- Scope Blacklist:
  - [ ] No application authentication or multi-user accounts
  - [ ] No microservice decomposition
  - [ ] No non-core exports or styling features
  - [ ] No new browser controller, public tunnel, model-serving dashboard, or multi-GPU scheduler

The setup sequence to validate during implementation is:

```bash
uv tool install 'google-colab-cli==0.7.2'
colab --auth oauth2 usage
colab --auth oauth2 new -s h3 --gpu A100 --high-mem
colab --auth oauth2 status -s h3
```

The first authenticated command may present Google's consent flow. `--high-mem` requires the appropriate account entitlement; it is a host-RAM request. After allocation, use `colab exec` for hardware checks and the prepared inference script, then `colab download`, `colab log`, and `colab stop -s h3`. These are proposed operations, not commands executed in this research session. [Session command source](https://github.com/googlecolab/google-colab-cli/blob/main/src/colab_cli/commands/session.py), [CLI command reference](https://github.com/googlecolab/google-colab-cli).

## 6. Next Actions

- [ ] Action 1: Install a tested CLI release and authenticate with the Google account that owns the 200 CU allowance; record the balance without allocating a GPU.
- [ ] Action 2: Allocate one eligible A100 or larger runtime, verify its actual memory and CU rate, then run a small quantized H3 workload and measure successful output cost.
- [ ] Action 3: Add the single-command wrapper only after the first complete inference/download/cleanup loop succeeds.

Verification performed: primary documentation and selected source-code review; direct GitHub API metadata and commit checks; live PyPI version metadata; local prerequisite inspection. Luna's evidence was integrated for third-party alternatives and contributor/PR/release counts; main independently checked the decision-critical official CLI, MCP, model, account-benefit, and GPU sources. Browser account inspection was unavailable because this session's browser-control tool reported `CUA_REPL_ENABLED_SURFACES is required`. No account login, GPU allocation, package installation, H3 inference, latency benchmark, or dependency vulnerability scan was performed.
