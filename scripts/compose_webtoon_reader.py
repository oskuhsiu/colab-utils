#!/usr/bin/env python3
"""Build a local, phone-width HTML reader from approved panel art and lettering."""

from __future__ import annotations

import argparse
import html
import json
import os
from pathlib import Path


def escape(value: object) -> str:
    return html.escape(str(value), quote=True)


def reader_html(project_dir: Path, *, prefer_upscaled: bool = False) -> tuple[str, int]:
    project_dir = project_dir.resolve()
    tasks = json.loads((project_dir / "webtoon_tasks.json").read_text(encoding="utf-8"))
    storyboard = json.loads((project_dir / "webtoon_storyboard.json").read_text(encoding="utf-8"))
    run_manifest_path = project_dir / "results" / "webtoon_run_manifest.json"
    run_manifest = json.loads(run_manifest_path.read_text(encoding="utf-8")) if run_manifest_path.is_file() else {}
    output_dir = project_dir / "results" / "deliverables"
    output_dir.mkdir(parents=True, exist_ok=True)
    use_upscaled = bool(prefer_upscaled) and all(
        (project_dir / panel["output_path"]).is_file()
        and (project_dir / "results" / "upscaled-panels" / f"{panel['panel_id']}.png").is_file()
        for panel in tasks["panels"]
    )
    rendered_panels = 0
    sections: list[str] = []
    for segment in tasks["segments"]:
        segment_panels: list[str] = []
        for panel in segment["panels"]:
            task = next(item for item in tasks["panels"] if item["panel_id"] == panel["panel_id"])
            image_path = project_dir / "results" / "upscaled-panels" / f"{panel['panel_id']}.png" if use_upscaled else project_dir / task["output_path"]
            if not image_path.is_file():
                continue
            rendered_panels += 1
            image_url = os.path.relpath(image_path, output_dir)
            lettering = []
            for line in task.get("lettering", []):
                lettering.append(
                    f'<div class="lettering {escape(line["kind"])} {escape(line.get("position", "top_left"))}">'
                    f'{escape(line["text"])}</div>'
                )
            lettering_block = "\n".join(lettering)
            alt = f"{segment['story_beat']}；{panel['camera']}"
            segment_panels.append(f'''<figure class="panel {escape(panel['composition_class'])}" id="{escape(panel['panel_id'])}">
  <img src="{escape(image_url)}" alt="{escape(alt)}" loading="lazy" />
  <div class="lettering-layer">{lettering_block}</div>
</figure>''')
        gap = segment.get("gap_after", {})
        mobile_px = int(gap.get("mobile_px", 100))
        factor = mobile_px / 390
        gap_html = (
            f'<div class="scroll-gap {escape(gap.get("class", "beat"))}" '
            f'style="--gap-factor:{factor:.4f};--gap-max:{mobile_px * 2}px" '
            f'aria-label="{escape(gap.get("reason", ""))}"></div>'
        )
        sections.append(
            f'<section class="segment" aria-label="{escape(segment["story_beat"])}">'
            + "\n".join(segment_panels)
            + gap_html
            + "</section>"
        )

    low = run_manifest.get("generation_settings", {}).get(
        "selected_panel_width_px", tasks["generation"]["panel_width_px"]
    )
    resolution_note = f"{low * 2}px 放大稿" if use_upscaled else f"{low}px 草稿"
    title = escape(storyboard["title"])
    page_title = escape(f"{storyboard['chapter_id']}｜{storyboard['title']}")
    promise = escape(storyboard["episode_promise"])
    hook = escape(storyboard["episode_hook"])
    content = "\n".join(sections)
    document = f'''<!doctype html>
<html lang="zh-Hant">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <meta name="description" content="{promise}" />
  <title>{page_title}｜被俘日記</title>
  <style>
    :root {{ color-scheme: dark; font-family: -apple-system, BlinkMacSystemFont, "Hiragino Sans GB", "PingFang TC", "Microsoft JhengHei", sans-serif; }}
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; background: #171715; color: #f8f1df; }}
    header {{ padding: 30px 22px 24px; text-align: center; }}
    header h1 {{ margin: 0 0 8px; font-size: clamp(24px, 6vw, 42px); letter-spacing: .08em; }}
    header p {{ max-width: 600px; margin: 8px auto; color: #cfc4ae; line-height: 1.65; }}
    header .meta {{ color: #a99d88; font-size: 13px; }}
    .reader {{ width: min(100%, 768px); margin: 0 auto; container-type: inline-size; background: #0f0f0e; }}
    .panel {{ position: relative; margin: 0; width: 100%; overflow: hidden; background: #ece4d4; }}
    .panel img {{ display: block; width: 100%; height: auto; }}
    .lettering-layer {{ position: absolute; inset: 0; pointer-events: none; }}
    .lettering {{ position: absolute; max-width: 78%; padding: .48em .75em; border: 2px solid #25221f; color: #181614; font-size: clamp(16px, 4.2cqw, 28px); font-weight: 650; line-height: 1.38; text-align: center; white-space: pre-wrap; box-shadow: 0 2px 5px #0004; }}
    .lettering.top_left {{ left: 4%; top: 4%; }}
    .lettering.top_right {{ right: 4%; top: 4%; }}
    .lettering.bottom_left {{ left: 4%; bottom: 4%; }}
    .lettering.bottom_right {{ right: 4%; bottom: 4%; }}
    .lettering.upper_left {{ left: 4%; top: 24%; }}
    .lettering.diary {{ border-radius: 8px; background: #fff7df; font-family: "Songti TC", "PMingLiU", serif; font-weight: 600; }}
    .lettering.caption {{ border-radius: 8px; background: #fffdf4f2; }}
    .lettering.dialogue {{ border-radius: 48% 48% 44% 44%; background: #fff; }}
    .lettering.sfx {{ padding: .1em .28em; border: 0; background: transparent; color: #211a14; font-size: clamp(22px, 8cqw, 56px); font-weight: 900; -webkit-text-stroke: 1px #fff5dc; paint-order: stroke fill; box-shadow: none; transform: rotate(-7deg); }}
    .scroll-gap {{ height: min(calc(var(--gap-factor) * 100cqw), var(--gap-max)); }}
    .scroll-gap.reveal_delay, .scroll-gap.impact {{ background: linear-gradient(#0f0f0e, #171715 44%, #0f0f0e); }}
    .scroll-gap.scene_transition, .scroll-gap.time_passage {{ height: min(calc(var(--gap-factor) * 100cqw), 920px); background: #171715; }}
    footer {{ padding: 32px 20px 64px; text-align: center; color: #cfc4ae; line-height: 1.7; }}
    @media (min-width: 769px) {{ header {{ padding-top: 48px; }} }}
  </style>
</head>
<body>
  <header>
    <p class="meta">被俘日記・{escape(storyboard['chapter_id'])}・{resolution_note}</p>
    <h1>{title}</h1>
    <p>{promise}</p>
    <p class="meta">向下滑動閱讀 · 全篇共 {rendered_panels} 格</p>
  </header>
  <main class="reader">
{content}
  </main>
  <footer><p>{hook}</p><p>下一格未完，待續。</p></footer>
</body>
</html>
'''
    return document, rendered_panels


def build_series_index(series_root: Path) -> Path:
    series = json.loads((series_root / "series.json").read_text(encoding="utf-8"))
    links = []
    for chapter_slug in series.get("chapters", []):
        chapter_dir = series_root / chapter_slug
        board_path = chapter_dir / "webtoon_storyboard.json"
        if not board_path.is_file():
            continue
        board = json.loads(board_path.read_text(encoding="utf-8"))
        reader_path = chapter_dir / "results" / "deliverables" / "reader.html"
        status = "可閱讀" if reader_path.is_file() else "等待圖片"
        relative = os.path.relpath(reader_path, series_root / "results" / "deliverables")
        links.append(
            f'<li><a href="{escape(relative)}">{escape(board["chapter_id"])}｜{escape(board["title"])}</a>'
            f'<span>{status}</span></li>'
        )
    target = series_root / "results" / "deliverables" / "series-reader.html"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(f'''<!doctype html>
<html lang="zh-Hant"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>被俘日記｜網漫</title><style>
body{{margin:0;background:#191816;color:#f6f0df;font-family:-apple-system,BlinkMacSystemFont,"Hiragino Sans GB","PingFang TC",sans-serif}}main{{max-width:700px;margin:10vh auto;padding:28px}}h1{{letter-spacing:.08em}}li{{display:flex;justify-content:space-between;gap:16px;padding:18px 4px;border-bottom:1px solid #49443b}}a{{color:#ffdc9d;font-size:20px;text-decoration:none}}span{{color:#b7aa94;font-size:14px}}</style></head>
<body><main><h1>被俘日記・直式網漫</h1><p>由下方章節連結進入手機滑讀版。</p><ol>{''.join(links)}</ol></main></body></html>''', encoding="utf-8")
    return target


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project_dir", type=Path)
    parser.add_argument("--prefer-upscaled", action="store_true")
    args = parser.parse_args()
    project_dir = args.project_dir.resolve()
    target_dir = project_dir / "results" / "deliverables"
    target_dir.mkdir(parents=True, exist_ok=True)
    document, panel_count = reader_html(project_dir, prefer_upscaled=args.prefer_upscaled)
    reader_path = target_dir / ("reader-upscaled.html" if args.prefer_upscaled else "reader.html")
    reader_path.write_text(document, encoding="utf-8")
    series_index = build_series_index(project_dir.parent)
    print(json.dumps({"reader": str(reader_path), "series_reader": str(series_index), "panels": panel_count}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
