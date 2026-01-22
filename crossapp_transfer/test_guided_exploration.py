"""
测试 guided_exploration 中 Phase 0-3 的有效性
使用真实数据：从 data/ 读取 prototype 和 TIG，通过 parse_current_screen 获取设备屏幕
"""
import json
import sys
from pathlib import Path
import xml.etree.ElementTree as ET

# 添加父目录到路径以导入 utils
sys.path.insert(0, str(Path(__file__).parent))

from utils import (
    parse_current_screen,
    _match_screen_to_target_tigs,
    _select_capability_for_step,
    _map_capability_to_actions,
    _extract_ui_description_from_xml,
    _is_capability_feasible,
    _find_navigation_capability,
    _extract_semantic_keywords,
    _score_element_relevance,
)


# =========================================================
# 数据加载 (Real Data Loading)
# =========================================================

def load_prototype_data():
    """从 data/example_prototype.json 加载原型数据"""
    data_path = Path(__file__).parent / "data" / "example_prototype.json"
    
    if not data_path.exists():
        raise FileNotFoundError(f"Prototype file not found: {data_path}")
    
    with data_path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    
    print(f"✓ Loaded {data.get('num_prototypes', 0)} prototypes from {data_path.name}")
    return data


def load_tig_library():
    """从 data/tig.json 加载 TIG 库"""
    tig_path = Path(__file__).parent / "data" / "tig.json"
    
    if not tig_path.exists():
        raise FileNotFoundError(f"TIG file not found: {tig_path}")
    
    with tig_path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    
    # 将节点列表转换为字典格式 {tig_id: tig_node}
    tig_library = {}
    for node in data.get("nodes", []):
        tig_id = node.get("id")
        if tig_id:
            tig_library[tig_id] = node
    
    print(f"✓ Loaded {len(tig_library)} TIG nodes from {tig_path.name}")
    return tig_library


def get_current_screen_state(adb_serial: str, output_dir: str = "./test_output"):
    """通过 parse_current_screen 获取真实设备的当前屏幕状态"""
    print(f"\n📱 Capturing current screen from device: {adb_serial}")
    
    try:
        screen_data = parse_current_screen(adb_serial, output_dir)
        print(f"✓ Screen captured: {screen_data['hash'][:12]}...")
        print(f"✓ XML saved to: {screen_data['xml_path']}")
        print(f"✓ Screenshot saved to: {screen_data['screenshot_path']}")
        return screen_data
    except Exception as e:
        raise RuntimeError(f"Failed to capture screen: {e}")


# =========================================================
# UI 元素包装类
# =========================================================

class UIElement:
    """UI 元素包装类，从 XML 节点提取"""
    def __init__(self, node):
        attrib = node.attrib if hasattr(node, 'attrib') else {}
        self.text = attrib.get('text', '')
        self.resource_id = attrib.get('resource-id', '')
        self.content_desc = attrib.get('content-desc', '')
        self.bounds = attrib.get('bounds', '')
        self.clickable = attrib.get('clickable', 'false') == 'true'
        self.class_name = attrib.get('class', '')
        self.enabled = attrib.get('enabled', 'true') == 'true'
        self.scrollable = attrib.get('scrollable', 'false') == 'true'
        
        # 收集子节点的文本信息（用于嵌套组件）
        self.child_texts = []
        self.child_descs = []
        self._extract_child_info(node)
    
    def _extract_child_info(self, node):
        """递归提取所有子节点的文本和描述信息"""
        for child in node:
            child_attrib = child.attrib if hasattr(child, 'attrib') else {}
            
            # 提取子节点的文本
            child_text = child_attrib.get('text', '').strip()
            if child_text:
                self.child_texts.append(child_text)
            
            # 提取子节点的内容描述
            child_desc = child_attrib.get('content-desc', '').strip()
            if child_desc:
                self.child_descs.append(child_desc)
            
            # 递归处理更深层的子节点
            self._extract_child_info(child)
    
    def get_all_text(self):
        """获取元素及其子元素的所有文本（用于评分）"""
        all_texts = []
        if self.text:
            all_texts.append(self.text)
        if self.content_desc:
            all_texts.append(self.content_desc)
        all_texts.extend(self.child_texts)
        all_texts.extend(self.child_descs)
        return ' '.join(all_texts)
    
    def get_display_label(self):
        """获取元素的显示标签（优先使用子节点文本）"""
        # 优先使用第一个有意义的子节点文本
        if self.child_texts:
            return self.child_texts[0]
        # 其次使用自身文本
        if self.text:
            return self.text
        # 再使用内容描述
        if self.content_desc:
            return self.content_desc
        # 最后使用 resource-id
        if self.resource_id:
            return self.resource_id.split('/')[-1] if '/' in self.resource_id else self.resource_id
        return 'Unlabeled'


class ScreenWrapper:
    """屏幕包装器，提供便捷的 UI 查询接口"""
    def __init__(self, xml_content):
        self.xml_content = xml_content
        try:
            self.root = ET.fromstring(xml_content)
            self._elements = None
        except ET.ParseError as e:
            raise ValueError(f"Invalid XML content: {e}")
    
    def get_all_text(self):
        """提取屏幕上所有可见文本"""
        texts = []
        for node in self.root.iter():
            attrib = node.attrib if hasattr(node, 'attrib') else {}
            text = attrib.get('text', '').strip()
            desc = attrib.get('content-desc', '').strip()
            if text:
                texts.append(text)
            if desc:
                texts.append(desc)
        return ' '.join(texts)
    
    def get_interactable_elements(self):
        """获取所有可交互的 UI 元素（clickable=true）"""
        if self._elements is None:
            self._elements = []
            for node in self.root.iter():
                attrib = node.attrib if hasattr(node, 'attrib') else {}
                if attrib.get('clickable', 'false') == 'true':
                    self._elements.append(UIElement(node))
        return self._elements
    
    def get_all_elements(self):
        """获取所有 UI 元素"""
        elements = []
        for node in self.root.iter():
            elements.append(UIElement(node))
        return elements



# =========================================================
# Phase 0: Context Perception Tests
# =========================================================

def test_phase0_context_perception(current_screen, tig_library, target_step):
    """测试 Phase 0: 环境感知与 TIG 匹配"""
    print("\n" + "="*70)
    print("Phase 0: Context Perception (环境感知 & TIG 匹配)")
    print("="*70)
    
    target_tig_ids = target_step.get('supporting_tig_nodes', [])
    print(f"\n📍 Target TIG Nodes: {', '.join(target_tig_ids)}")
    
    # Test 1: UI 描述提取
    print("\n[Test 1] UI Description Extraction")
    ui_desc = _extract_ui_description_from_xml(current_screen['xml'])
    print(f"✓ Extracted UI Description:")
    print(f"  {ui_desc[:200]}...")
    
    # Test 2: TIG 匹配
    print("\n[Test 2] TIG Matching Against Target Nodes")
    context_match = _match_screen_to_target_tigs(
        current_screen,
        target_tig_ids,
        tig_library
    )
    
    print(f"\n🎯 Matching Results:")
    print(f"  Matched TIG: {context_match['matched_tig'] or 'None'}")
    print(f"  Match Score: {context_match['score']:.3f}")
    print(f"\n  Top Candidates:")
    for i, candidate in enumerate(context_match['top_candidates'][:3], 1):
        print(f"    {i}. {candidate['tig_id']}")
        print(f"       Score: {candidate['score']:.3f}")
        print(f"       Intent: {candidate['intent_label']}")
    
    # Test 3: 验证匹配质量
    print("\n[Test 3] Match Quality Assessment")
    if context_match['matched_tig']:
        if context_match['score'] >= 0.7:
            print(f"✓ High confidence match ({context_match['score']:.3f})")
        elif context_match['score'] >= 0.5:
            print(f"⚠ Medium confidence match ({context_match['score']:.3f})")
        else:
            print(f"⚠ Low confidence match ({context_match['score']:.3f})")
    else:
        print("✗ No match found - may need navigation")
    
    return context_match


# =========================================================
# Phase 1: Decision Making Tests
# =========================================================

def test_phase1_decision_making(target_step, screen_wrapper, context_match):
    """测试 Phase 1: 基于上下文的决策"""
    print("\n" + "="*70)
    print("Phase 1: Decision Making (基于上下文的决策)")
    print("="*70)
    
    print(f"\n📋 Step Configuration:")
    print(f"  Description: {target_step.get('description', 'N/A')}")
    print(f"  Required Capabilities: {', '.join(target_step.get('required_capabilities', []))}")
    print(f"  Optional Capabilities: {', '.join(target_step.get('optional_capabilities', []))}")
    
    # Test 1: 能力可行性检测
    print("\n[Test 1] Capability Feasibility Check")
    all_caps = target_step.get('required_capabilities', []) + target_step.get('optional_capabilities', [])
    
    feasible_caps = []
    for cap in all_caps:
        feasible = _is_capability_feasible(cap, screen_wrapper)
        status = "✓" if feasible else "✗"
        print(f"  {status} {cap}")
        if feasible:
            feasible_caps.append(cap)
    
    # Test 2: 决策制定
    print(f"\n[Test 2] Decision Making (Context Score: {context_match['score']:.3f})")
    decision = _select_capability_for_step(target_step, screen_wrapper, context_match)
    
    print(f"\n🧠 Decision Output:")
    print(f"  Selected Capability: {decision.name}")
    print(f"  Decision Type: {decision.type}")
    print(f"  Confidence: {decision.confidence:.3f}")
    print(f"  Reason: {decision.reason}")
    
    # Test 3: 决策合理性分析
    print(f"\n[Test 3] Decision Rationality")
    if decision.type == "EXECUTION":
        if decision.name in feasible_caps:
            print(f"✓ Decision is executable (capability found on screen)")
        else:
            print(f"⚠ Capability not directly feasible - may use heuristics")
    elif decision.type == "NAVIGATION":
        print(f"✓ Navigation decision - attempting to reach target context")
    else:
        print(f"⚠ Unexpected decision type: {decision.type}")
    
    return decision


# =========================================================
# Phase 2: Grounding Tests
# =========================================================

def test_phase2_grounding(decision, screen_wrapper, target_step):
    """测试 Phase 2: 动作映射"""
    print("\n" + "="*70)
    print("Phase 2: Grounding (动作映射)")
    print("="*70)
    
    # Test 1: 语义关键词提取
    print(f"\n[Test 1] Semantic Keyword Extraction for '{decision.name}'")
    keywords = _extract_semantic_keywords(decision.name)
    print(f"✓ Extracted Keywords: {keywords}")
    
    # Test 2: UI 元素评分（详细版）
    print(f"\n[Test 2] UI Element Relevance Scoring (Detailed)")
    interactable = screen_wrapper.get_interactable_elements()
    print(f"  Total interactable elements: {len(interactable)}")
    
    # 打印所有元素的详细信息
    print(f"\n  📋 All Interactable Elements:")
    scored_elements = []
    for idx, elem in enumerate(interactable[:], 1):
        score = _score_element_relevance(elem, keywords)
        scored_elements.append((elem, score))
        
        # 获取元素显示标签
        label = elem.get_display_label()
        
        # 打印详细信息
        print(f"\n    Element {idx}: Score={score:.3f}")
        print(f"      Display Label: {label[:60]}")
        print(f"      Text: {elem.text[:50] if elem.text else '(empty)'}")
        print(f"      Content-Desc: {elem.content_desc[:50] if elem.content_desc else '(empty)'}")
        
        # 显示子节点信息
        if elem.child_texts:
            print(f"      Child Texts: {elem.child_texts}")
        if elem.child_descs:
            print(f"      Child Descs: {elem.child_descs}")
        
        print(f"      Resource-ID: {elem.resource_id if elem.resource_id else '(empty)'}")
        print(f"      Class: {elem.class_name}")
        print(f"      Bounds: {elem.bounds}")
        
        # 显示评分原因
        if score > 0:
            matched_keywords = []
            all_text = elem.get_all_text().lower()
            for kw in keywords:
                if kw.lower() in all_text or \
                   (elem.resource_id and kw.lower() in elem.resource_id.lower()):
                    matched_keywords.append(kw)
            if matched_keywords:
                print(f"      ✓ Matched Keywords: {matched_keywords}")
    
    # 按分数排序
    scored_elements.sort(key=lambda x: x[1], reverse=True)
    
    print(f"\n  🏆 Top Scored Elements (Top 10):")
    for i, (elem, score) in enumerate(scored_elements[:10], 1):
        label = elem.get_display_label()
        all_text = elem.get_all_text()
        print(f"    {i}. Score: {score:.3f} - {label[:60]}")
        if elem.resource_id:
            print(f"       ID: {elem.resource_id}")
        if all_text and len(all_text) > len(label):
            print(f"       All Text: {all_text[:80]}")
        if elem.child_texts:
            print(f"       Children: {', '.join(elem.child_texts[:3])}")
    
    # Test 3: 动作映射（详细版）
    print(f"\n[Test 3] Action Mapping (Detailed)")
    print(f"  Decision Type: {decision.type}")
    print(f"  Decision Capability: {decision.name}")
    print(f"  Decision Confidence: {decision.confidence:.3f}")
    
    # 额外诊断信息
    print(f"\n  📊 Grounding Diagnostics:")
    high_score_count = sum(1 for _, s in scored_elements if s > 0.5)
    medium_score_count = sum(1 for _, s in scored_elements if 0.3 < s <= 0.5)
    low_score_count = sum(1 for _, s in scored_elements if 0.1 < s <= 0.3)
    zero_score_count = sum(1 for _, s in scored_elements if s == 0)
    
    print(f"    High relevance (>0.5): {high_score_count} elements")
    print(f"    Medium relevance (0.3-0.5): {medium_score_count} elements")
    print(f"    Low relevance (0.1-0.3): {low_score_count} elements")
    print(f"    No relevance (0): {zero_score_count} elements")
    
    # 基于 scored_elements 生成动作
    actions = []
    
    if scored_elements and scored_elements[0][1] > 0:
        best_elem, best_score = scored_elements[0]
        
        print(f"\n  🎯 Using Best Scored Element:")
        print(f"    Element: {best_elem.get_display_label()[:60]}")
        print(f"    Score: {best_score:.3f}")
        print(f"    Resource-ID: {best_elem.resource_id}")
        print(f"    Bounds: {best_elem.bounds}")
        
        # 根据分数和能力名称决定动作类型
        if best_score < 0:
            print(f"\n    ⚠️ Low grounding confidence ({best_score:.3f})")
            print(f"       Fallback to exploratory scroll")
            
            # 导入 Action 类
            from utils import Action, _generate_heuristic_scroll
            actions.append(_generate_heuristic_scroll(screen_wrapper))
        else:
            # 导入 Action 类
            from utils import Action
            
            # 确定动作类型
            action_type = "CLICK"
            params = {}
            
            # 如果能力暗示是输入
            if "Search" in decision.name or "Input" in decision.name:
                input_text = target_step.get("input_params", {}).get("text", None)
                if input_text:
                    action_type = "INPUT"
                    params["text"] = input_text
                    print(f"    Action Type: INPUT (text: '{input_text}')")
                else:
                    print(f"    Action Type: CLICK (to focus input field)")
            else:
                print(f"    Action Type: CLICK")
            
            actions.append(Action(
                type=action_type,
                target=best_elem,
                params=params,
                description=f"Interact with '{best_elem.get_display_label()}' (Score: {best_score:.3f})"
            ))
    else:
        print(f"\n    ⚠️ No scored elements available")
        print(f"       Fallback to exploratory scroll")
        
        from utils import Action, _generate_heuristic_scroll
        actions.append(_generate_heuristic_scroll(screen_wrapper))
    
    # 显示生成的动作
    print(f"\n🛠️ Generated Actions: {len(actions)} action(s)")
    for i, action in enumerate(actions, 1):
        print(f"\n  Action {i}:")
        print(f"    Type: {action.type}")
        print(f"    Description: {action.description}")
        if hasattr(action, 'target') and action.target:
            target_label = action.target.get_display_label() if hasattr(action.target, 'get_display_label') else (action.target.text or action.target.content_desc or 'Unlabeled')
            print(f"    Target: {target_label}")
            if hasattr(action.target, 'resource_id'):
                print(f"    Target Resource-ID: {action.target.resource_id}")
            if hasattr(action.target, 'bounds'):
                print(f"    Bounds: {action.target.bounds}")
            if hasattr(action.target, 'child_texts') and action.target.child_texts:
                print(f"    Child Texts: {action.target.child_texts}")
        if hasattr(action, 'params') and action.params:
            print(f"    Params: {action.params}")
    
    return actions


# =========================================================
# Phase 3: Execution Analysis (不实际执行)
# =========================================================

def test_phase3_execution_analysis(actions, adb_serial: str, output_dir: str = "./test_output", execute: bool = False):
    """测试 Phase 3: 执行分析（可选实际执行动作）"""
    print("\n" + "="*70)
    print("Phase 3: Execution (动作执行)")
    print("="*70)
    
    if not actions:
        print("\n✗ No actions to execute")
        return None
    
    primary_action = actions[0]
    
    print(f"\n[Primary Action]")
    print(f"  Type: {primary_action.type}")
    print(f"  Description: {primary_action.description}")
    
    if not execute:
        print("\n⚠️  Execution disabled (use execute=True to run actions)")
        _preview_action(primary_action)
        return None
    
    # 实际执行动作
    print("\n🚀 Executing action...")
    
    import subprocess
    import time
    
    try:
        # 执行不同类型的动作
        if primary_action.type == "CLICK":
            if hasattr(primary_action, 'target') and primary_action.target:
                bounds = primary_action.target.bounds
                x, y = _parse_center_from_bounds(bounds)
                
                print(f"\n  ✓ Clicking at ({x}, {y})")
                print(f"    Target: {primary_action.target.get_display_label()}")
                
                cmd = ['adb', '-s', adb_serial, 'shell', 'input', 'tap', str(x), str(y)]
                subprocess.run(cmd, check=True, capture_output=True)
                print(f"  ✓ Click executed successfully")
            else:
                print(f"\n  ✗ Click action missing target")
                return None
        
        elif primary_action.type == "INPUT":
            if hasattr(primary_action, 'params') and 'text' in primary_action.params:
                text = primary_action.params['text']
                
                # 先点击目标元素以聚焦
                if hasattr(primary_action, 'target') and primary_action.target:
                    bounds = primary_action.target.bounds
                    x, y = _parse_center_from_bounds(bounds)
                    print(f"\n  ✓ Focusing input field at ({x}, {y})")
                    cmd = ['adb', '-s', adb_serial, 'shell', 'input', 'tap', str(x), str(y)]
                    subprocess.run(cmd, check=True, capture_output=True)
                    time.sleep(0.5)
                
                # 输入文本
                print(f"  ✓ Inputting text: '{text}'")
                # 转义特殊字符
                escaped_text = text.replace(' ', '%s').replace("'", "\\'")
                cmd = ['adb', '-s', adb_serial, 'shell', 'input', 'text', escaped_text]
                subprocess.run(cmd, check=True, capture_output=True)
                print(f"  ✓ Input executed successfully")
            else:
                print(f"\n  ⚠ Input action missing text parameter")
                return None
        
        elif primary_action.type == "SCROLL":
            if hasattr(primary_action, 'params'):
                params = primary_action.params
                start_x = params.get('start_x', 500)
                start_y = params.get('start_y', 1500)
                end_x = params.get('end_x', 500)
                end_y = params.get('end_y', 500)
                duration = params.get('duration', 300)
                
                print(f"\n  ✓ Scrolling from ({start_x}, {start_y}) to ({end_x}, {end_y})")
                cmd = ['adb', '-s', adb_serial, 'shell', 'input', 'swipe', 
                       str(start_x), str(start_y), str(end_x), str(end_y), str(duration)]
                subprocess.run(cmd, check=True, capture_output=True)
                print(f"  ✓ Scroll executed successfully")
            else:
                print(f"\n  ⚠ Scroll action missing parameters")
                return None
        
        elif primary_action.type == "KEY_EVENT":
            if hasattr(primary_action, 'params') and 'key' in primary_action.params:
                key = primary_action.params['key']
                print(f"\n  ✓ Sending key event: {key}")
                cmd = ['adb', '-s', adb_serial, 'shell', 'input', 'keyevent', key]
                subprocess.run(cmd, check=True, capture_output=True)
                print(f"  ✓ Key event executed successfully")
            else:
                print(f"\n  ⚠ Key event missing key parameter")
                return None
        
        # 等待 UI 稳定
        time.sleep(1.5)
        
        # 捕获执行后的屏幕状态
        print(f"\n📱 Capturing new screen state...")
        new_screen = get_current_screen_state(adb_serial, output_dir)
        
        print(f"\n✅ Action executed successfully!")
        print(f"  New screen hash: {new_screen['hash'][:16]}...")
        
        return new_screen
        
    except subprocess.CalledProcessError as e:
        print(f"\n✗ Execution failed: {e}")
        print(f"  Command: {' '.join(e.cmd)}")
        if e.stderr:
            print(f"  Error: {e.stderr.decode()}")
        return None
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return None


def _preview_action(action):
    """预览动作而不执行"""
    print(f"\n[Preview Mode]")
    
    if action.type == "CLICK":
        if hasattr(action, 'target') and action.target:
            bounds = action.target.bounds
            x, y = _parse_center_from_bounds(bounds)
            print(f"  Would click at ({x}, {y})")
            print(f"  Target: {action.target.get_display_label()}")
        else:
            print(f"  ✗ Click action missing target")
    
    elif action.type == "INPUT":
        if hasattr(action, 'params') and 'text' in action.params:
            print(f"  Would input text: '{action.params['text']}'")
        else:
            print(f"  ⚠ Input action missing text parameter")
    
    elif action.type == "SCROLL":
        if hasattr(action, 'params'):
            print(f"  Would scroll with parameters: {action.params}")
    
    elif action.type == "KEY_EVENT":
        if hasattr(action, 'params'):
            print(f"  Would send key: {action.params.get('key', 'N/A')}")


def _parse_center_from_bounds(bounds_str):
    """从 bounds 字符串解析中心坐标
    
    Args:
        bounds_str: 格式如 "[0,348][1280,574]"
    
    Returns:
        (x, y): 中心点坐标
    """
    import re
    # 提取坐标: [x1,y1][x2,y2]
    match = re.match(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]', bounds_str)
    if match:
        x1, y1, x2, y2 = map(int, match.groups())
        center_x = (x1 + x2) // 2
        center_y = (y1 + y2) // 2
        return center_x, center_y
    else:
        raise ValueError(f"Invalid bounds format: {bounds_str}")


# =========================================================
# 综合测试流程
# =========================================================

def test_integrated_pipeline(adb_serial: str, prototype_index: int = 0, step_index: int = 0):
    """综合测试 Phase 0-3 的完整流程"""
    print("\n" + "="*70)
    print("🚀 Integrated Test: Phase 0-3 Pipeline with Real Data")
    print("="*70)
    
    # 1. 加载数据
    print("\n[Setup] Loading Data...")
    prototype_data = load_prototype_data()
    tig_library = load_tig_library()
    
    # 2. 选择测试原型和步骤
    prototypes = prototype_data.get('prototypes', [])
    if prototype_index >= len(prototypes):
        print(f"✗ Prototype index {prototype_index} out of range (0-{len(prototypes)-1})")
        return
    
    selected_prototype = prototypes[prototype_index]
    steps = selected_prototype.get('steps', [])
    
    if step_index >= len(steps):
        print(f"✗ Step index {step_index} out of range (0-{len(steps)-1})")
        return
    
    target_step = steps[step_index]
    
    print(f"\n📦 Selected Prototype: {selected_prototype.get('name', 'Unknown')}")
    print(f"   Intent: {selected_prototype.get('intent', 'N/A')}")
    print(f"\n📍 Testing Step {step_index + 1}: {target_step.get('step', 'Unknown')}")
    print(f"   Description: {target_step.get('description', 'N/A')}")
    
    # 3. 获取当前屏幕状态
    print("\n[Setup] Capturing Current Screen State...")
    try:
        current_screen = get_current_screen_state(adb_serial)
        screen_wrapper = ScreenWrapper(current_screen['xml'])
    except Exception as e:
        print(f"✗ Failed to capture screen: {e}")
        print("\n💡 提示:")
        print("  1. 确保设备已通过 ADB 连接")
        print("  2. 运行 'adb devices' 确认设备可见")
        print("  3. 确保已授予 USB 调试权限")
        return
    
    print(f"\n📱 Screen Info:")
    print(f"  Hash: {current_screen['hash'][:16]}...")
    print(f"  Interactable Elements: {len(screen_wrapper.get_interactable_elements())}")
    print(f"  All Elements: {len(screen_wrapper.get_all_elements())}")
    
    # 4. 执行各阶段测试
    try:
        # Phase 0: Context Perception
        context_match = test_phase0_context_perception(current_screen, tig_library, target_step)
        
        # Phase 1: Decision Making
        decision = test_phase1_decision_making(target_step, screen_wrapper, context_match)
        
        # Phase 2: Grounding
        actions = test_phase2_grounding(decision, screen_wrapper, target_step)
        
        # Phase 3: Execution (询问是否执行)
        print("\n" + "="*70)
        print("⚠️  Ready to Execute Action")
        print("="*70)
        
        user_input = input("\n执行动作? (y/n, 默认 n): ").strip().lower()
        execute = user_input == 'y'
        
        new_screen = test_phase3_execution_analysis(actions, adb_serial, output_dir="./test_output", execute=execute)
        
        # 总结
        print("\n" + "="*70)
        print("✅ Pipeline Test Completed Successfully!")
        print("="*70)
        print(f"\n📊 Summary:")
        print(f"  Context Match: {context_match['matched_tig'] or 'None'} (Score: {context_match['score']:.3f})")
        print(f"  Decision: {decision.name} ({decision.type}, Confidence: {decision.confidence:.3f})")
        print(f"  Actions Generated: {len(actions)}")
        
        if execute and new_screen:
            print(f"  Execution: ✓ Completed")
            print(f"  New Screen Hash: {new_screen['hash'][:16]}...")
            
            # 比较屏幕变化
            if new_screen['hash'] != current_screen['hash']:
                print(f"  Screen Changed: ✓ Yes (UI updated)")
            else:
                print(f"  Screen Changed: ✗ No (UI unchanged)")
        elif execute:
            print(f"  Execution: ✗ Failed")
        else:
            print(f"  Execution: - Skipped (preview mode)")
        
    except Exception as e:
        print(f"\n✗ Test Failed: {e}")
        import traceback
        traceback.print_exc()


# =========================================================
# Main Test Runner
# =========================================================

def main():
    """主测试入口"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Test Guided Exploration Phase 0-3')
    parser.add_argument('--serial', '-s', type=str, 
                        help='ADB device serial number (run "adb devices" to get it)')
    parser.add_argument('--prototype', '-p', type=int, default=0,
                        help='Prototype index to test (default: 0)')
    parser.add_argument('--step', '-t', type=int, default=0,
                        help='Step index to test (default: 0)')
    parser.add_argument('--execute', '-e', action='store_true',
                        help='Auto-execute actions without confirmation (use with caution!')
    
    args = parser.parse_args()
    
    # 如果没有指定设备序列号，尝试自动检测
    if not args.serial:
        import subprocess
        try:
            result = subprocess.run(['adb', 'devices'], 
                                    capture_output=True, text=True, check=True)
            lines = result.stdout.strip().split('\n')[1:]  # 跳过标题行
            devices = [line.split()[0] for line in lines if line.strip() and 'device' in line]
            
            if devices:
                args.serial = devices[0]
                print(f"📱 Auto-detected device: {args.serial}")
            else:
                print("✗ No ADB devices found")
                print("\n请确保:")
                print("  1. 设备已通过 USB 连接")
                print("  2. 已启用 USB 调试")
                print("  3. 运行 'adb devices' 确认设备可见")
                return
        except Exception as e:
            print(f"✗ Failed to detect ADB devices: {e}")
            print("\n请手动指定设备序列号: --serial <DEVICE_SERIAL>")
            return
    
    # 运行综合测试
    test_integrated_pipeline(args.serial, args.prototype, args.step)


if __name__ == "__main__":
    main()
