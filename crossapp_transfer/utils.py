import json
from pathlib import Path
from typing import Any, Dict, List, Optional
import re
import xml.etree.ElementTree as ET
from collections import defaultdict
import subprocess
import hashlib
from pathlib import Path
import tempfile
import numpy as np
import time


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
# TIG匹配相关函数
# =========================================================
def _match_screen_to_target_tigs(
    current_screen: dict,
    target_tig_ids: List[str],
    tig_library: Dict[str, Any]
) -> Dict[str, Any]:
    """
    将当前屏幕状态匹配到目标TIG节点列表中
    
    该函数模仿 grounder.py 中的 TIGGrounder.ground() 方法，
    使用语义相似度和关键词匹配来定位当前屏幕对应的TIG节点。
    
    Args:
        current_screen: 当前屏幕状态，包含：
            - 'xml': 屏幕XML内容
            - 'screenshot_path': 截图路径（可选）
            - 'ui_description': UI描述（可选，如果没有会生成）
        target_tig_ids: 候选的TIG节点ID列表
        tig_library: TIG库，格式 {tig_id: tig_node_data}
    
    Returns:
        {
            'matched_tig': str,  # 匹配的TIG ID，如果未匹配则为None
            'score': float,      # 匹配分数 (0-1)
            'top_candidates': List[Dict]  # Top-3候选项
        }
    """
    # 如果没有目标TIG或TIG库为空，返回未匹配
    if not target_tig_ids or not tig_library:
        return {
            'matched_tig': None,
            'score': 0.0,
            'top_candidates': []
        }
    
    # 1. 获取UI描述（从current_screen获取或生成）
    ui_description = current_screen.get('ui_description', '')
    
    if not ui_description:
        # 从XML中提取简单的UI描述
        xml_content = current_screen.get('xml', '')
        ui_description = _extract_ui_description_from_xml(xml_content)
    
    # 2. 将UI描述转换为embedding
    ui_embedding = _text_to_embedding_simple(ui_description)
    
    # 3. 遍历目标TIG节点计算相似度
    scores = []
    for tig_id in target_tig_ids:
        if tig_id not in tig_library:
            continue
        
        tig_node = tig_library[tig_id]
        
        # 计算相似度分数
        score = _compute_tig_similarity_score(
            ui_description,
            ui_embedding,
            tig_node
        )
        
        scores.append({
            'tig_id': tig_id,
            'score': score,
            'intent_label': tig_node.get('intent_label', ''),
        })
    
    # 4. 按分数排序
    scores.sort(key=lambda x: x['score'], reverse=True)
    
    # 5. 获取最佳匹配
    similarity_threshold = 0.60  # 相似度阈值（比grounder.py稍低，因为是在限定范围内匹配）
    
    if scores and scores[0]['score'] >= similarity_threshold:
        best_match = scores[0]
        return {
            'matched_tig': best_match['tig_id'],
            'score': best_match['score'],
            'top_candidates': scores[:3]
        }
    else:
        return {
            'matched_tig': None,
            'score': scores[0]['score'] if scores else 0.0,
            'top_candidates': scores[:3] if scores else []
        }


def _extract_ui_description_from_xml(xml_content: str) -> str:
    """
    从XML内容中提取简单的UI描述
    
    Args:
        xml_content: 屏幕XML内容
        
    Returns:
        UI功能描述字符串
    """
    if not xml_content:
        return "Unknown screen"
    
    try:
        root = ET.fromstring(xml_content)
    except ET.ParseError:
        return "Unknown screen"
    
    # 收集关键信息
    texts = []
    content_descs = []
    resource_ids = []
    
    for node in root.iter():
        attrib = node.attrib if hasattr(node, 'attrib') else {}
        
        text = attrib.get('text', '').strip()
        if text and len(text) > 0:
            texts.append(text)
        
        desc = attrib.get('content-desc', '').strip()
        if desc and len(desc) > 0:
            content_descs.append(desc)
        
        res_id = attrib.get('resource-id', '').strip()
        if res_id and '/' in res_id:
            # 提取ID的简短部分，如 com.app:id/search -> search
            res_id = res_id.split('/')[-1]
            resource_ids.append(res_id)
    
    # 构建描述
    description_parts = []
    
    # 从resource-id推断功能
    id_keywords = set()
    for res_id in resource_ids[:20]:  # 只取前20个
        id_keywords.update(res_id.lower().split('_'))
    
    if id_keywords:
        description_parts.append(f"UI elements: {', '.join(list(id_keywords)[:10])}")
    
    # 从文本内容推断
    if texts:
        description_parts.append(f"Text content: {', '.join(texts[:5])}")
    
    # 从content-desc推断
    if content_descs:
        description_parts.append(f"Descriptions: {', '.join(content_descs[:5])}")
    
    return '. '.join(description_parts) if description_parts else "Unknown screen"


def _text_to_embedding_simple(text: str) -> np.ndarray:
    """
    将文本转换为简单的embedding向量（基于hash的fallback实现）
    
    这是一个简化版本，用于在没有API访问的情况下工作。
    在生产环境中，应该使用真实的embedding API。
    
    Args:
        text: 输入文本
        
    Returns:
        384维的embedding向量
    """
    # 使用hash方法生成确定性向量
    hash_obj = hashlib.sha256(text.encode('utf-8'))
    hash_bytes = hash_obj.digest()
    
    # 转换为384维向量
    vector = np.frombuffer(hash_bytes, dtype=np.uint8)
    vector = np.tile(vector, (384 // len(vector) + 1))[:384]
    
    # 归一化
    vector = vector.astype(np.float32)
    vector = vector / (np.linalg.norm(vector) + 1e-8)
    
    return vector


def _compute_tig_similarity_score(
    ui_description: str,
    ui_embedding: np.ndarray,
    tig_node: Dict[str, Any]
) -> float:
    """
    计算UI描述与TIG节点的相似度分数
    
    Args:
        ui_description: UI文本描述
        ui_embedding: UI描述的embedding向量
        tig_node: TIG节点数据
        
    Returns:
        相似度分数 (0-1)
    """
    # A. 生成TIG节点的描述和embedding
    tig_description = _create_tig_node_description(tig_node)
    tig_embedding = _text_to_embedding_simple(tig_description)
    
    # B. 计算语义相似度
    sem_sim = _cosine_similarity(ui_embedding, tig_embedding)
    
    # C. 计算关键词匹配分数
    keyword_score = _compute_keyword_match_for_tig(ui_description, tig_node)
    
    # D. 加权融合
    final_score = 0.7 * sem_sim + 0.3 * keyword_score
    
    return final_score


def _create_tig_node_description(tig_node: Dict[str, Any]) -> str:
    """
    为TIG节点创建文本描述
    
    Args:
        tig_node: TIG节点数据
        
    Returns:
        节点的文本描述
    """
    intent_label = tig_node.get('intent_label', '')
    capabilities = tig_node.get('capabilities', [])
    ui_description = tig_node.get('ui_description', '')
    
    desc = f"Intent: {intent_label}\n"
    if ui_description:
        desc += f"Description: {ui_description}\n"
    if capabilities:
        desc += f"Capabilities: {', '.join(capabilities[:10])}"
    
    return desc


def _compute_keyword_match_for_tig(ui_description: str, tig_node: Dict[str, Any]) -> float:
    """
    计算UI描述与TIG节点的关键词匹配分数
    
    Args:
        ui_description: UI描述
        tig_node: TIG节点数据
        
    Returns:
        关键词匹配分数 (0-1)
    """
    ui_desc_lower = ui_description.lower()
    
    # 1. Intent Label匹配
    intent_label = tig_node.get('intent_label', '')
    intent_keywords = intent_label.lower().replace('_', ' ').split()
    intent_matches = sum(1 for kw in intent_keywords if kw in ui_desc_lower and len(kw) > 2)
    intent_score = intent_matches / len(intent_keywords) if intent_keywords else 0
    
    # 2. Capabilities匹配
    capabilities = tig_node.get('capabilities', [])
    capability_matches = 0
    for cap in capabilities[:20]:  # 只检查前20个能力
        cap_lower = cap.lower()
        # 提取能力中的关键词
        cap_keywords = cap_lower.replace('(', ' ').replace(')', ' ').replace('_', ' ').split()
        if any(kw in ui_desc_lower for kw in cap_keywords if len(kw) > 3):
            capability_matches += 1
    
    capability_score = capability_matches / min(20, len(capabilities)) if capabilities else 0
    
    # 3. UI Description匹配（如果TIG节点有ui_description字段）
    ui_desc_score = 0.0
    tig_ui_desc = tig_node.get('ui_description', '').lower()
    if tig_ui_desc:
        tig_keywords = set(tig_ui_desc.split())
        ui_keywords = set(ui_desc_lower.split())
        if tig_keywords and ui_keywords:
            overlap = len(tig_keywords & ui_keywords)
            ui_desc_score = overlap / len(tig_keywords | ui_keywords)
    
    # 综合分数
    keyword_score = 0.4 * intent_score + 0.4 * capability_score + 0.2 * ui_desc_score
    
    return keyword_score


def _cosine_similarity(vec1: np.ndarray, vec2: np.ndarray) -> float:
    """
    计算两个向量的余弦相似度
    
    Args:
        vec1: 向量1
        vec2: 向量2
        
    Returns:
        余弦相似度 (0-1)
    """
    dot_product = np.dot(vec1, vec2)
    norm1 = np.linalg.norm(vec1)
    norm2 = np.linalg.norm(vec2)
    
    if norm1 == 0 or norm2 == 0:
        return 0.0
    
    similarity = dot_product / (norm1 * norm2)
    # 将[-1, 1]映射到[0, 1]
    return (similarity + 1) / 2

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
def guided_exploration(proto, initial_screen_state, tig_library):
    """
    Execute a Functional Prototype with TIG-based Context Awareness
    
    Args:
        tig_library: A dictionary of all TIG definitions {tig_id: tig_node_data}
    """
    current_screen = initial_screen_state

    for step in proto["steps"]:
        step_completed = False
        retry_budget = 5

        print(f"--- Starting Step: {step['step']} ---")

        while not step_completed and retry_budget > 0:
            
            # ============================================================
            # Phase 0: 🔍 Context Perception (环境感知 & TIG 匹配)
            # ============================================================
            # 获取当前步骤支持的 TIG 列表 (即：我们应该在哪里？)
            target_tig_ids = step.get("supporting_tig_nodes", [])
            
            # 计算当前屏幕与目标 TIG 的匹配情况
            context_match = _match_screen_to_target_tigs(
                current_screen, 
                target_tig_ids, 
                tig_library
            )
            
            print(f"Current Context Match: {context_match['matched_tig']} "
                  f"(Confidence: {context_match['score']:.2f})")

            # ============================================================
            # Phase 1: 🧠 Decision Making (基于上下文的决策)
            # ============================================================
            # 如果不在正确的 TIG 中，capability 选择器可能会优先选择 "Navigation" 动作
            capability = _select_capability_for_step(
                step, 
                current_screen, 
                context_match  # <--- 传入感知结果
            )

            # ============================================================
            # Phase 2: 🛠️ Grounding (动作映射)
            # ============================================================
            candidate_actions = _map_capability_to_actions(
                capability,
                current_screen,
                step_config=step  # 传入 step 配置以获取 exploration_strategy
            )

            # ============================================================
            # Phase 3: ⚡ Execution & Feedback (执行与反馈)
            # ============================================================
            result = _execute_actions_with_feedback(
                candidate_actions,
                current_screen
            )

            # ============================================================
            # Phase 4: ✅ Verification (验证)
            # ============================================================
            if _evaluate_step_completion(step, result):
                current_screen = result.new_screen_state
                step_completed = True
                break

            # ============================================================
            # Phase 5: 🚑 Recovery (基于 TIG 的恢复)
            # ============================================================
            current_screen = _guided_recovery(
                step,
                result,
                current_screen,
                context_match # <--- 恢复策略也依赖于“我在哪”
            )
            retry_budget -= 1

        if not step_completed:
            raise RuntimeError(f"Step failed: {step['step']}")

    return True


from dataclasses import dataclass
from typing import List, Optional

@dataclass
class CapabilityDecision:
    name: str                  # 能力名称，如 "SelectTrack"
    type: str                  # "EXECUTION" (执行任务) 或 "NAVIGATION" (修正路径)
    confidence: float          # 决策置信度
    reason: str                # 决策理由 (用于 Debug 或 Paper Case Study)

def _select_capability_for_step(step, current_screen, context_match) -> CapabilityDecision:
    """
    Phase 1: Decision Making
    根据当前环境匹配度 (TIG Match) 和 步骤定义，选择最优能力。
    """

    # 阈值定义 (可以在论文 Experiment Setup 中列出)
    CONTEXT_THRESHOLD = 0.6  # 只有环境匹配分高于此，才敢执行核心任务

    # 1. 获取候选能力列表
    required_caps = step.get("required_capabilities", [])
    optional_caps = step.get("optional_capabilities", [])

    # ============================================================
    # Scenario A: 我们在正确的地方 (High Context Confidence)
    # ============================================================
    if context_match["score"] >= CONTEXT_THRESHOLD:
        
        # 优先检查 "必须能力" (Required)
        for cap_name in required_caps:
            # 这里的 feasibility check 是轻量级的，只看文本/图标是否存在，不做精确坐标映射
            if _is_capability_feasible(cap_name, current_screen):
                return CapabilityDecision(
                    name=cap_name,
                    type="EXECUTION",
                    confidence=0.9,
                    reason=f"Context matches ({context_match['matched_tig']}) and capability '{cap_name}' features found."
                )

        # 如果必须能力不可行 (例如：列表可能是空的)，检查 "可选能力"
        for cap_name in optional_caps:
            if _is_capability_feasible(cap_name, current_screen):
                return CapabilityDecision(
                    name=cap_name,
                    type="EXECUTION",
                    confidence=0.7,
                    reason="Required caps missing, falling back to optional capability."
                )
        
        # 如果环境对，但啥能力都执行不了 -> 触发局部探索 (Local Exploration)
        # 例如：在歌单页，但没看到歌 -> 决定 "Scroll_Down"
        strategy = step.get("exploration_strategy", "default")
        if "scroll" in strategy:
            return CapabilityDecision(
                name="Scroll_Explore",
                type="EXECUTION",
                confidence=0.6,
                reason="Context correct but elements missing. Strategy dictates scrolling."
            )
    
    # ============================================================
    # Scenario B: 我们在错误的地方 (Low Context Confidence)
    # ============================================================
    else:
        # 此时 Agent 迷路了，或者刚启动 App。
        # 决策目标从 "完成任务" 切换为 "寻找目标环境"。
        
        target_tigs = step.get("supporting_tig_nodes", [])
        print(f"⚠️ Context Mismatch! Current score: {context_match['score']}. Seeking TIGs: {target_tigs}")

        # 策略 1: 检查当前屏幕是否有通往目标的 "导航锚点"
        # 例如：我们在 "Home"，目标是 "Library"，我们要找 "Library" 的 Tab
        nav_cap = _find_navigation_capability(current_screen, target_tigs)
        if nav_cap:
            return CapabilityDecision(
                name=nav_cap,
                type="NAVIGATION",
                confidence=0.8,
                reason=f"Detected navigation path to target TIG."
            )
            
        # 策略 2: 通用回溯 (Backtrack)
        # 如果不知道去哪，通常 "Back" 或者 "Go Home" 是最安全的
        return CapabilityDecision(
            name="Navigate_Back_Or_Home",
            type="NAVIGATION",
            confidence=0.5,
            reason="Lost context. Initiating recovery navigation."
        )

    # ============================================================
    # Fallback: 实在没招了
    # ============================================================
    return CapabilityDecision(
        name="No_Op",
        type="WAIT",
        confidence=0.0,
        reason="No feasible capabilities found."
    )

def _is_capability_feasible(cap_name, current_screen):
    """
    轻量级可行性分析。
    不需要调用昂贵的视觉模型，只做关键词匹配。
    """
    # 将 Capability 驼峰转关键词: "SelectTrack" -> {"select", "track"}
    keywords = _parse_keywords_from_cap(cap_name) 
    
    # 简单规则：如果 Capability 的关键词在屏幕文本中出现，就认为"可行"
    # 这比 Phase 2 的 Grounding 要宽容得多
    screen_text = current_screen.get_all_text().lower()
    
    # 特例处理
    if "scroll" in cap_name.lower(): return True # 滚动通常总是可行的
    
    # 检查是否有重合
    for kw in keywords:
        if kw in screen_text:
            return True
            
    return False

def _find_navigation_capability(current_screen, target_tigs):
    """
    在当前屏幕寻找能否跳到 target_tigs 的入口
    """
    # 这是一个简化版。在实际论文中，这里可以查询 TIG 图的边 (Edges)
    # 查看是否有 current_tig -> target_tig 的已知路径
    
    screen_text = current_screen.get_all_text().lower()
    
    # 启发式规则：如果目标 TIG 叫 "Library_Browse"，看看屏幕上有没有 "Library" 这个词
    for tig_id in target_tigs:
        # 假设 TIG ID 里包含了线索，如 "TIG_LIBRARY_BROWSE" -> "library"
        clue = tig_id.split("_")[1].lower() 
        if clue in screen_text:
            return f"NavigateTo({clue.capitalize()})"
            
    return None

def _parse_keywords_from_cap(cap_name):
    # 简单的字符串处理
    import re
    # Split by uppercase: SelectTrack -> Select, Track
    words = re.findall(r'[A-Z][a-z]*', cap_name)
    return [w.lower() for w in words]




from dataclasses import dataclass, field
from typing import Dict, Any, List

@dataclass
class Action:
    type: str                  # "CLICK", "SCROLL", "INPUT", "KEY_EVENT", "WAIT"
    target: Optional[Any] = None # UI Element 对象 (包含 bounds, text 等)
    params: Dict[str, Any] = field(default_factory=dict) # 额外参数, 如 scroll_dir, input_text
    description: str = ""      # 用于日志和调试

    def __repr__(self):
        return f"[Action: {self.type}] {self.description}"



def _map_capability_to_actions(decision, current_screen, step_config):
    """
    Phase 2: Visual Grounding
    将抽象的 CapabilityDecision 映射为具体的 UI 动作。
    
    Args:
        decision (CapabilityDecision): Phase 1 的输出
        current_screen: 当前屏幕状态 (Wrapper of XML/Hierarchy)
        step_config: 当前步骤的完整 JSON 配置
    """
    actions = []
    cap_name = decision.name
    
    print(f"🛠️ Grounding Capability: {cap_name} (Type: {decision.type})")

    # ============================================================
    # Case A: 纯导航/系统动作 (Navigation / System)
    # ============================================================
    if "Navigate_Back" in cap_name:
        # 映射为物理返回键
        return [Action(type="KEY_EVENT", params={"key": "BACK"}, description="System Back")]
    
    if "Scroll_Explore" in cap_name:
        # 映射为通用滑动动作
        return [_generate_heuristic_scroll(current_screen)]

    # ============================================================
    # Case B: 交互动作 (Interaction - Click/Input)
    # ============================================================
    # 1. 提取语义特征 (Semantic Feature Extraction)
    # 将 "SelectTrack" 拆解为特征词: ["select", "track"]
    # 将 "Search_Music" 拆解为特征词: ["search", "music"]
    target_keywords = _extract_semantic_keywords(cap_name)
    
    # 如果 Step 配置里有具体参数 (比如输入文本)，也提取出来
    input_text = step_config.get("input_params", {}).get("text", None)

    # 2. 候选元素评分 (Candidate Scoring)
    # 遍历屏幕上所有可交互元素，计算它们与 target_keywords 的相似度
    candidates = []
    interactable_elements = current_screen.get_interactable_elements() # Filter by clickable=true

    for elem in interactable_elements:
        score = _score_element_relevance(elem, target_keywords)
        if score > 0:
            candidates.append((elem, score))
    
    # 3. 排序与选择 (Ranking & Selection)
    # 按分数降序排列
    candidates.sort(key=lambda x: x[1], reverse=True)

    # 4. 动作实例化 (Instantiation)
    if candidates:
        best_elem, best_score = candidates[0]
        
        # 阈值判定 (Grounding Threshold)
        # 如果最高分都低于 0.4，说明屏幕上可能根本没有对应的按钮
        if best_score < 0.4:
            print(f"⚠️ Low grounding confidence ({best_score:.2f}). Fallback to Scroll.")
            return [_generate_heuristic_scroll(current_screen)]

        # 确定动作类型
        action_type = "CLICK"
        params = {}
        
        # 如果 Capability 暗示是输入 (e.g., "Search_Music") 且我们有文本
        if "Search" in cap_name or "Input" in cap_name:
            if input_text:
                action_type = "INPUT"
                params["text"] = input_text
            else:
                # 如果没文本，先点一下聚焦
                action_type = "CLICK" 

        actions.append(Action(
            type=action_type,
            target=best_elem,
            params=params,
            description=f"Interact with '{best_elem.text or best_elem.desc}' (Score: {best_score:.2f})"
        ))
    
    else:
        # 屏幕上没找到任何相关元素 -> 默认滑动探索
        print("❌ No matching elements found. Generating exploration scroll.")
        actions.append(_generate_heuristic_scroll(current_screen))

    return actions

def _extract_semantic_keywords(cap_name):
    """
    从驼峰命名或下划线命名中提取核心词
    Input: "Select_Song" -> {"select", "song"}
    """
    import re
    # 分割驼峰和下划线
    words = re.findall(r'[a-zA-Z][a-z]*', cap_name.replace("_", " "))
    keywords = set(w.lower() for w in words)
    
    # 扩展同义词 (Synonym Expansion) - 可以在论文中提到使用了简单的知识库
    synonyms = {
        "track": ["song", "music", "audio", "title"],
        "browse": ["library", "list", "all"],
        "initiate": ["start", "play"],
        "playback": ["player", "playing"]
    }
    
    expanded = set(keywords)
    for k in keywords:
        if k in synonyms:
            expanded.update(synonyms[k])
            
    return expanded

def _score_element_relevance(elem, target_keywords):
    """
    计算 UI 元素与目标意图的关联度 (0.0 - 1.0)
    """
    # 1. 提取元素特征
    elem_text = (elem.text or "").lower()
    elem_desc = (elem.content_desc or "").lower()
    elem_id = (elem.resource_id or "").lower()
    
    combined_text = f"{elem_text} {elem_desc} {elem_id}"
    if not combined_text.strip():
        return 0.0

    # 2. 关键词匹配 (Keyword Matching)
    match_count = 0
    for kw in target_keywords:
        if kw in combined_text:
            match_count += 1
            
            # 精确匹配加分 (Exact Match Bonus)
            if kw == elem_text or kw == elem_desc:
                match_count += 1

    # 3. 视觉/属性 加权 (Heuristic Boosting)
    score = match_count / (len(target_keywords) + 1) # 基础分
    
    # 如果找 "Play"，而元素是 ImageButton 且 id 包含 "play"，大幅加分
    if "play" in target_keywords and "play" in elem_id:
        score += 0.3
        
    return min(score, 1.0)

def _generate_heuristic_scroll(current_screen):
    """
    生成一个智能滑动动作
    """
    # 默认向上滑 (即浏览下方内容)
    # 在论文中可以提到：会检测屏幕是否可滑动 (scrollable=true)
    return Action(
        type="SCROLL", 
        params={"start_x": 500, "start_y": 1500, "end_x": 500, "end_y": 500},
        description="Exploratory Scroll Down"
    )








class ExecutionResult:
    def __init__(self, success, new_screen_state, message=""):
        self.success = success
        self.new_screen_state = new_screen_state
        self.message = message

def _execute_actions_with_feedback(candidate_actions, current_screen_xml):
    """
    使用 ADB + UiAutomator 执行动作并捕获反馈
    """
    # 0. 选取置信度最高的动作 (假设 candidate_actions 已排序)
    action = candidate_actions[0]
    
    # 1. 执行动作 (Action Execution)
    try:
        if action.type == "CLICK":
            # 这里的 target 必须包含坐标 bounds，例如 "[100,200][300,400]"
            center_x, center_y = _get_center_from_bounds(action.target.bounds)
            _adb_click(center_x, center_y)
            
        elif action.type == "INPUT":
            # 先点击聚焦，再输入
            center_x, center_y = _get_center_from_bounds(action.target.bounds)
            _adb_click(center_x, center_y)
            time.sleep(0.5) 
            _adb_input_text(action.params['text'])
            
        elif action.type == "SCROLL":
            _adb_swipe(action.params['start_x'], action.params['start_y'], 
                       action.params['end_x'], action.params['end_y'])
    except Exception as e:
        return ExecutionResult(False, current_screen_xml, f"ADB Error: {str(e)}")

    # 2. 等待 UI 稳定 (Stabilization)
    # 这是一个关键参数，通常 UI 响应在 0.5s - 2.0s 之间
    time.sleep(2.0)

    # 3. 获取新状态 (State Capture)
    new_screen_xml = _get_ui_hierarchy()

    # 4. 生成反馈 (Feedback Generation)
    # 比较新旧 XML 的哈希值或关键节点数量来判断页面是否变化
    has_changed = _compare_states(current_screen_xml, new_screen_xml)
    
    if has_changed:
        return ExecutionResult(True, new_screen_xml, "UI State Changed")
    else:
        # 如果页面没变，可能是操作失败，或者操作本身不产生视觉变化（如复制文本）
        return ExecutionResult(False, new_screen_xml, "No Visual Change Detected")

# --- Helper Functions (底层 ADB 封装) ---

def _adb_click(x, y):
    cmd = f"adb shell input tap {x} {y}"
    subprocess.run(cmd, shell=True)

def _adb_input_text(text):
    # 注意：adb input text 不支持中文和空格，建议使用 'adb shell input keyevent' 或 ADBKeyboard
    # 这里做简单处理，将空格替换为 %s
    safe_text = text.replace(" ", "%s") 
    cmd = f"adb shell input text {safe_text}"
    subprocess.run(cmd, shell=True)

def _adb_swipe(x1, y1, x2, y2, duration=300):
    cmd = f"adb shell input swipe {x1} {y1} {x2} {y2} {duration}"
    subprocess.run(cmd, shell=True)

def _get_ui_hierarchy():
    """
    获取当前的 XML 结构。
    注意：这是最耗时的步骤，通常需要 1-2 秒。
    """
    # 1. Dump 到手机临时文件
    subprocess.run("adb shell uiautomator dump /sdcard/window_dump.xml", shell=True)
    # 2. Pull 到本地
    subprocess.run("adb pull /sdcard/window_dump.xml ./temp_dump.xml", shell=True)
    # 3. 读取内容
    with open("./temp_dump.xml", "r", encoding="utf-8") as f:
        return f.read()

def _get_center_from_bounds(bounds_str):
    # 解析 "[x1,y1][x2,y2]"
    import re
    coords = re.findall(r"\d+", bounds_str)
    x1, y1, x2, y2 = map(int, coords)
    return (x1 + x2) // 2, (y1 + y2) // 2

def _compare_states(old_xml, new_xml):
    # 简单实现：比较字符串长度或 Hash
    # 进阶实现：构建 DOM 树，计算 Tree Edit Distance (树编辑距离)
    return hash(old_xml) != hash(new_xml)


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
