"""
批量可视化 local_index 中的所有 intent：
- 为每个 intent 生成可视化图片（优先使用 action 序列；没有则生成占位卡片）
- 图片保存到 utg/<APP>/intents 目录
- 计算图片 hash_id（md5 前 16 位）并写回 local_index.json 的对应 intent

用法：
    python local_index_visualize.py [utg_folder]
示例：
    python local_index_visualize.py "utg/NetEase Cloud Music"
若不传参，默认目录为脚本同级的 utg/NetEase Cloud Music
"""
import os
import sys
import json
import hashlib
import textwrap
from typing import Dict, Any, List
from PIL import Image, ImageDraw, ImageFont

from visualize import ActionVisualizer


def _default_utg_folder() -> str:
    base_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_dir, "utg", "NetEase Cloud Music")


def _load_local_index(utg_folder: str) -> Dict[str, List[Dict[str, Any]]]:
    path = os.path.join(utg_folder, "local_index.json")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_local_index(utg_folder: str, local_index: Dict[str, Any]):
    path = os.path.join(utg_folder, "local_index.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(local_index, f, ensure_ascii=False, indent=2)


def _ensure_dir(path: str):
    os.makedirs(path, exist_ok=True)


def _safe_filename(name: str, max_len: int = 80) -> str:
    safe = "".join(ch if ch.isalnum() or ch in ("-", "_", ".") else "_" for ch in name)
    if len(safe) > max_len:
        safe = safe[:max_len]
    return safe


def _compute_hash16(file_path: str) -> str:
    md5 = hashlib.md5()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            md5.update(chunk)
    return md5.hexdigest()[:16]


def _draw_wrapped_text(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont, x: int, y: int, 
                       max_width: int, line_spacing: int = 8, fill: str = "black") -> int:
    # 简易按像素宽度换行：粗略估算每行字符数
    # 回退：使用 textwrap 先按字符宽度近似再逐行绘制
    avg_char_width = font.getlength("汉A字a").__float__() / 4.0 if hasattr(font, "getlength") else 20.0
    approx_chars_per_line = max(8, int(max_width / max(1.0, avg_char_width)))
    lines = []
    for raw_line in text.splitlines():
        if not raw_line:
            lines.append("")
            continue
        lines.extend(textwrap.wrap(raw_line, width=approx_chars_per_line))
    line_height = font.size + line_spacing
    cur_y = y
    for line in lines:
        draw.text((x, cur_y), line, font=font, fill=fill)
        cur_y += line_height
    return cur_y


def _create_intent_card(intent_text: str, out_path: str):
    # 生成占位卡片图片：展示 intent 文本并提示未找到动作序列
    W, H = 1200, 800
    img = Image.new("RGB", (W, H), "white")
    draw = ImageDraw.Draw(img)
    try:
        title_font = ImageFont.truetype("msyh.ttc", 44)
        body_font = ImageFont.truetype("msyh.ttc", 34)
    except Exception:
        title_font = ImageFont.load_default()
        body_font = ImageFont.load_default()

    title = "Intent Visualization"
    subtitle = "未找到可视化的动作序列，生成占位卡片"

    draw.text((40, 30), title, fill="black", font=title_font)
    draw.text((40, 90), subtitle, fill="gray", font=body_font)

    # 分隔线
    draw.line([(40, 150), (W - 40, 150)], fill="#e0e0e0", width=2)

    # Intent 文本
    intent_title = "Intent:" 
    draw.text((40, 180), intent_title, fill="#333333", font=body_font)

    text_top = 230
    text_left = 40
    text_right = W - 40
    _draw_wrapped_text(draw, intent_text, body_font, text_left, text_top, max_width=(text_right - text_left))

    img.save(out_path)


def visualize_all_intents(utg_folder: str) -> Dict[str, Any]:
    print(f"UTG 目录: {utg_folder}")
    local_index = _load_local_index(utg_folder)
    intents_dir = os.path.join(utg_folder, "intents")
    _ensure_dir(intents_dir)

    visualizer = ActionVisualizer(utg_folder)

    total = 0
    success = 0
    placeholders = 0

    for cluster_id, tasks in local_index.items():
        if not isinstance(tasks, list):
            continue
        for idx, task in enumerate(tasks):
            total += 1
            intent = task.get("intent", "").strip()
            if not intent:
                continue

            # 生成文件名：cluster_{cid}_{idx}_{slug}.png（slug 限长，避免过长文件名）
            slug = _safe_filename(intent.replace(" ", "_")[:50]) or f"i{idx+1}"
            filename = f"cluster_{cluster_id}_intent_{idx+1}_{slug}.png"
            out_path = os.path.join(intents_dir, filename)

            print(f"[{total}] cluster={cluster_id} intent_idx={idx+1} -> {filename}")

            ok = visualizer.visualize_actions(cluster_id=cluster_id, matched_intent=intent, output_path=out_path)
            if ok:
                success += 1
            else:
                _create_intent_card(intent, out_path)
                placeholders += 1

            # 计算 hash 并写入 intent 对象
            try:
                h = _compute_hash16(out_path)
                task["hash_id"] = h
            except Exception as e:
                print(f"  警告: 计算 hash 失败: {e}")

    # 回写 local_index.json
    _save_local_index(utg_folder, local_index)

    summary = {
        "utg_folder": utg_folder,
        "total_intents": total,
        "visualized": success,
        "placeholders": placeholders,
        "intents_dir": intents_dir,
    }
    print("\n完成批量可视化:")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return summary


def main():
    utg_folder = sys.argv[1] if len(sys.argv) > 1 else _default_utg_folder()
    if not os.path.isdir(utg_folder):
        print(f"指定的 utg_folder 不存在: {utg_folder}")
        sys.exit(1)
    visualize_all_intents(utg_folder)


if __name__ == "__main__":
    main()
