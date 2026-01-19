import json
from pathlib import Path
from typing import Any, Dict, List
import re
import xml.etree.ElementTree as ET
from collections import defaultdict
import subprocess
import hashlib
from pathlib import Path
import tempfile


# =========================================================
# 读取 Prototype
# =========================================================
def load_prototypes(path: str) -> List[Dict[str, Any]]:
    """
    读取 prototype.json 文件并返回原型列表。
    支持两种格式：
    1) {"prototypes": [...]} 包装；
    2) 直接的原型列表 [...]
    """
    prototype_file = Path(path)
    if not prototype_file.is_file():
        raise FileNotFoundError(f"Prototype file not found: {prototype_file}")

    with prototype_file.open("r", encoding="utf-8") as fp:
        data = json.load(fp)

    if isinstance(data, dict) and "prototypes" in data:
        prototypes = data.get("prototypes", [])
    elif isinstance(data, list):
        prototypes = data
    else:
        raise ValueError("Prototype file must be a dict with 'prototypes' key or a list of prototypes")

    if not isinstance(prototypes, list):
        raise ValueError("'prototypes' must be a list")

    normalized: List[Dict[str, Any]] = []
    for idx, proto in enumerate(prototypes):
        if not isinstance(proto, dict):
            raise ValueError(f"Prototype at index {idx} is not an object")
        normalized.append(proto)

    return normalized

# =========================================================
# 屏幕解析
# =========================================================
def _adb(serial: str, args: list[str], stdout=None):
    cmd = ["adb", "-s", serial] + args
    subprocess.run(cmd, check=True, stdout=stdout)


def parse_current_screen(adb_serial: str, output_dir: str) -> dict:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        tmp_png = tmp / "screen.png"
        tmp_xml = tmp / "ui.xml"

        # 1️⃣ 截图
        with tmp_png.open("wb") as f:
            _adb(adb_serial, ["exec-out", "screencap", "-p"], stdout=f)

        # 2️⃣ dump UI XML
        _adb(adb_serial, ["shell", "uiautomator", "dump", "/sdcard/ui.xml"])
        _adb(adb_serial, ["pull", "/sdcard/ui.xml", str(tmp_xml)])

        xml_content = tmp_xml.read_text(encoding="utf-8")

        print("XML Content:", xml_content)
        png_bytes = tmp_png.read_bytes()

    # 3️⃣ 计算 hash（XML + PNG）
    h = hashlib.sha1()
    h.update(xml_content.encode("utf-8"))
    h.update(png_bytes)
    screen_hash = h.hexdigest()

    # 4️⃣ 以 hash 命名保存
    xml_path = output_dir / f"{screen_hash}.xml"
    png_path = output_dir / f"{screen_hash}.png"

    if not xml_path.exists():
        xml_path.write_text(xml_content, encoding="utf-8")
    if not png_path.exists():
        png_path.write_bytes(png_bytes)

    return {
        "hash": screen_hash,
        "xml": xml_content,
        "xml_path": str(xml_path),
        "screenshot_path": str(png_path),
    }


def parse_screen_xml_to_capabilities(xml_content: str) -> Dict[str, List[str]]:
    """将 XML 内容解析为能力到节点的映射。
    该函数用于配合 ScreenExecutor，直接接收 XML 字符串进行能力推断。
    Returns:
        {capability_name: [node_key, ...]}
    """
    try:
        root = ET.fromstring(xml_content)
    except ET.ParseError:
        return {}

    capability_to_nodes: Dict[str, List[str]] = defaultdict(list)

    for node in root.iter():
        attrib = node.attrib if hasattr(node, 'attrib') else {}
        node_id = attrib.get('resource-id', '')
        node_class = attrib.get('class', '')
        node_text = attrib.get('text', '')
        node_desc = attrib.get('content-desc', '')
        node_clickable = attrib.get('clickable', 'false') == 'true'
        node_bounds = attrib.get('bounds', '')

        node_key = node_id if node_id else f"{node_class}|{node_text}|{node_desc}|{node_bounds}"

        inferred_caps = _infer_capabilities(node_class, node_id, node_text, node_desc, node_clickable)
        for cap in inferred_caps:
            if node_key not in capability_to_nodes[cap]:
                capability_to_nodes[cap].append(node_key)

    return dict(capability_to_nodes)


def _load_latest_screen_xml() -> str | None:
    """查找最近保存的屏幕 XML 文件并返回其内容。
    优先搜索以下路径：
    - assets/Trace/**/**/*.xml（与 test_executor 的存储策略一致）
    - ref/ITeM/assets/Trace/**/**/*.xml 作为备选
    """
    search_dirs = [
        Path('assets/Trace'),
        Path('ref/ITeM/assets/Trace'),
        Path.cwd() / 'assets' / 'Trace',
    ]

    latest_file: Path | None = None
    latest_mtime: float = -1.0
    for base in search_dirs:
        if not base.exists():
            continue
        for xml_path in base.rglob('*.xml'):
            try:
                mtime = xml_path.stat().st_mtime
            except OSError:
                continue
            if mtime > latest_mtime:
                latest_mtime = mtime
                latest_file = xml_path

    if latest_file is None:
        return None
    try:
        return latest_file.read_text(encoding='utf-8')
    except Exception:
        return None


def _infer_capabilities(node_class: str, node_id: str, node_text: str, node_desc: str, node_clickable: bool) -> List[str]:
    """根据节点属性推断其可支持的能力标签。
    该映射为启发式规则，覆盖常见音乐类 App 的控件与能力关系。
    """
    caps: List[str] = []

    # 统一大小写与空值处理
    cid = (node_id or '').lower()
    ctext = (node_text or '').lower()
    cdesc = (node_desc or '').lower()
    clazz = (node_class or '')

    # 搜索相关
    if 'search' in cid or 'search' in ctext or 'search' in cdesc or 'Search' in node_text:
        caps.extend(['Search_Music', 'Activate(Search_Bar)'])
    if 'edittext' in clazz.lower():
        caps.append('Activate(Search_Bar)')

    # 播放控制相关
    if re.search(r'play|start', cid) or re.search(r'play|start', cdesc) or re.search(r'▶|►', node_text):
        caps.extend(['Play_Song', 'Play_Track', 'Control_Playback'])
    if re.search(r'pause|stop', cid) or re.search(r'pause|stop', cdesc):
        caps.extend(['Pause_Song', 'Control_Playback'])
    if re.search(r'next', cid) or re.search(r'next', cdesc):
        caps.extend(['Play_Next_Track', 'Control_Playback'])
    if 'seekbar' in clazz.lower():
        caps.append('Seek_Track')

    # 列表浏览 / 选择歌曲
    if node_clickable and ('textview' in clazz.lower() or 'imageview' in clazz.lower()):
        # 作为可点击的列表项处理
        caps.extend(['Select_Song', 'Select_Track', 'Browse_Track_List'])
    if re.search(r'listview|recyclerview', clazz.lower()):
        caps.append('Browse_Track_List')

    # 播放列表管理相关
    if re.search(r'playlist', cid) or re.search(r'playlist', cdesc) or 'playlist' in ctext:
        caps.extend(['View_Existing_Playlists', 'Manage_Queue'])
    if re.search(r'add', cid) or re.search(r'add', cdesc):
        caps.append('Add_File_To_Playlist')
    if re.search(r'remove|delete', cid) or re.search(r'remove|delete', cdesc):
        caps.append('Remove_Tracks')
    if re.search(r'reorder|drag|move', cid) or re.search(r'reorder|drag|move', cdesc):
        caps.extend(['Reorder_Tracks', 'Reorder_Queue'])

    # 音频设置 / 均衡器
    if re.search(r'equalizer|eq', cid) or re.search(r'equalizer|eq', cdesc):
        caps.extend(['Adjust_Equalizer', 'Select_Equalizer_Preset'])
    if re.search(r'profile|audio', cid) or re.search(r'profile|audio', cdesc):
        caps.append('Adjust_Audio_Profile')

    # 主题 / 颜色自定义
    if re.search(r'color|theme', cid) or re.search(r'color|theme', cdesc) or 'theme' in ctext:
        caps.extend(['Customize_Interface_Colors', 'Change_Primary_Color'])
    if re.search(r'album', cid) or re.search(r'album', cdesc):
        caps.append('Toggle_Album_Color_Customization')
    if re.search(r'track', cid) or re.search(r'track', cdesc):
        caps.append('Toggle_Track_Color_Customization')

    # 去重保持顺序
    seen = set()
    deduped = []
    for cap in caps:
        if cap not in seen:
            seen.add(cap)
            deduped.append(cap)
    return deduped

# =========================================================
# 能力映射
# =========================================================
def map_prototype_to_screen(proto, available_nodes):
    """
    将 Prototype 的核心能力映射到屏幕可执行节点
    Args:
        proto: 单个 Prototype
        available_nodes: 当前屏幕可执行能力 {capability: [node_id]}
    Returns:
        {capability: node_id}
    """
    # 实现：
    # 1. 遍历 proto['core_capabilities']
    # 2. 查找可用节点
    # 3. 返回映射
    ...

# =========================================================
# Guided Exploration
# =========================================================
def guided_exploration(proto, action_mapping):
    """
    在新 App 中执行 Prototype 的功能
    Args:
        proto: Prototype 对象
        action_mapping: 能力到节点的映射
    """
    # 实现：
    # 1. 遍历 proto['core_capabilities']
    # 2. 执行动作（click / swipe / input）
    # 3. 获取屏幕反馈
    # 4. 如果动作失败，尝试 guided exploration：
    #    - 滑动、回退、重新定位节点
    # 5. 更新当前屏幕状态
    ...

# =========================================================
# 执行验证
# =========================================================
def verify_prototype_execution(proto):
    """
    验证功能原型是否完成
    Args:
        proto: Prototype 对象
    """
    # 实现：
    # 1. 根据 proto['postconditions'] 检查屏幕状态或功能完成情况
    # 2. 返回 True/False 或记录日志
    ...

# =========================================================
# 日志记录
# =========================================================
def log_prototype_execution(proto):
    """
    记录 Prototype 执行过程、屏幕状态和结果
    """
    # 实现：
    # 1. 保存执行步骤
    # 2. 保存屏幕截图或 XML
    # 3. 可用于调试和分析
    ...

# =========================================================
# 屏幕操作接口
# =========================================================
def perform_action(node_id: str, action_type: str = "click"):
    """
    执行屏幕操作（点击/滑动/输入）
    """
    # 实现：
    # 1. 调用你已有的屏幕操作方法
    # 2. action_type 可选为 click/swipe/input
    ...

# =========================================================
# 获取屏幕反馈
# =========================================================
def get_screen_feedback() -> dict:
    """
    获取当前屏幕反馈（XML/截图）
    Returns:
        屏幕状态
    """
    # 实现：
    # 1. 获取屏幕 XML 或截图
    # 2. 返回可用于状态判断的数据结构
    ...
