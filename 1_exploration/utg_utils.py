"""
UTG utilities for parsing and processing UI automation results.
Shared utilities between APE and DroidBot parsers.
"""

import hashlib
import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, List, Tuple, Any, Optional


def normalize_xml_for_state_id(xml_content: str) -> str:
    """
    Normalize XML content for generating stable state IDs.
    Removes dynamic attributes like bounds, index, etc.
    
    Args:
        xml_content: Raw XML content as string
        
    Returns:
        Normalized XML string for hashing
    """
    try:
        root = ET.fromstring(xml_content)
    except ET.ParseError:
        # If XML is malformed, use the content as-is
        return xml_content
    
    # Attributes to remove (dynamic attributes)
    dynamic_attrs = {
        'bounds', 'index', 'focused', 'selected', 
        'scroll-type', 'password', 'checkable', 'checked'
    }
    
    def normalize_node(node):
        """Recursively normalize XML node"""
        # Remove dynamic attributes
        for attr in list(node.attrib.keys()):
            if attr in dynamic_attrs:
                del node.attrib[attr]
        
        # Normalize children
        for child in node:
            normalize_node(child)
        
        # Sort attributes for consistent ordering
        node.attrib = dict(sorted(node.attrib.items()))
    
    normalize_node(root)
    
    # Convert back to string with consistent formatting
    def node_to_string(node, depth=0):
        """Convert node to consistent string representation"""
        attrs = ' '.join(f'{k}="{v}"' for k, v in sorted(node.attrib.items()))
        indent = '  ' * depth
        
        if len(node) == 0:
            if node.text and node.text.strip():
                return f'{indent}<{node.tag} {attrs}>{node.text.strip()}</{node.tag}>'
            else:
                return f'{indent}<{node.tag} {attrs}/>'
        else:
            children = '\n'.join(node_to_string(child, depth + 1) for child in node)
            return f'{indent}<{node.tag} {attrs}>\n{children}\n{indent}</{node.tag}>'
    
    return node_to_string(root)


def compute_state_id(xml_content: str) -> str:
    """
    Compute a stable state ID from XML content.
    
    Args:
        xml_content: Raw XML content
        
    Returns:
        12-character state ID (SHA1 hash prefix)
    """
    normalized = normalize_xml_for_state_id(xml_content)
    sha1_hash = hashlib.sha1(normalized.encode('utf-8')).hexdigest()
    return sha1_hash[:12]


def create_directories(output_path: Path) -> None:
    """
    Create necessary output directories.
    
    Args:
        output_path: Base output directory path
    """
    (output_path / 'states').mkdir(parents=True, exist_ok=True)
    (output_path / 'events').mkdir(parents=True, exist_ok=True)


def write_json_file(data: Any, file_path: Path) -> None:
    """
    Write data to JSON file with proper formatting.
    
    Args:
        data: Data to write
        file_path: Output file path
    """
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def copy_file_safe(source: Path, target: Path) -> bool:
    """
    Safely copy file from source to target.
    
    Args:
        source: Source file path
        target: Target file path
        
    Returns:
        True if successful, False otherwise
    """
    try:
        if source.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            with open(source, 'rb') as src, open(target, 'wb') as tgt:
                tgt.write(src.read())
            return True
    except Exception as e:
        print(f"Error copying file {source} to {target}: {e}")
    return False


def escape_js_string(s: str) -> str:
    """
    Escape string for JavaScript output.
    
    Args:
        s: String to escape
        
    Returns:
        JavaScript-safe string
    """
    if s is None:
        return 'null'
    
    # Escape special characters
    s = s.replace('\\', '\\\\')
    s = s.replace('"', '\\"')
    s = s.replace('\n', '\\n')
    s = s.replace('\r', '\\r')
    s = s.replace('\t', '\\t')
    
    return f'"{s}"'


def write_utg_js(states: List[Dict], events: List[Dict], output_path: Path) -> None:
    """
    Write UTG data to JavaScript file.
    
    Args:
        states: List of state dictionaries
        events: List of event dictionaries
        output_path: Output directory path
    """
    utg_js_path = output_path / 'utg.js'
    
    # Create unique nodes by state_id, keeping only the first occurrence
    unique_states = {}
    for state in states:
        state_id = state["state_id"]
        if state_id not in unique_states:
            unique_states[state_id] = {
                "state_id": state_id,
                "step": state["step"],
                "activity": state["activity"],
                "image": state["screenshot_path"],
                "xml": state["xml_path"]
            }
    
    unique_states_list = list(unique_states.values())
    
    with open(utg_js_path, 'w', encoding='utf-8') as f:
        f.write('var nodes = [\n')
        
        for i, state in enumerate(unique_states_list):
            comma = ',' if i < len(unique_states_list) - 1 else ''
            f.write(f'  {{\n')
            f.write(f'    id: {escape_js_string(state["state_id"])},\n')
            f.write(f'    step: {state["step"]},\n')
            f.write(f'    activity: {escape_js_string(state["activity"])},\n')
            f.write(f'    image: {escape_js_string(state["image"])},\n')
            f.write(f'    xml: {escape_js_string(state["xml"])}\n')
            f.write(f'  }}{comma}\n')
        
        f.write('];\n\n')
        f.write('var edges = [\n')
        
        for i, event in enumerate(events):
            comma = ',' if i < len(events) - 1 else ''
            f.write(f'  {{\n')
            f.write(f'    id: {escape_js_string(event["event_id"])},\n')
            f.write(f'    tag: {escape_js_string(event["tag"])},\n')
            f.write(f'    step: {event["step"]},\n')
            f.write(f'    from: {escape_js_string(event["from"])},\n')
            f.write(f'    to: {escape_js_string(event["to"])},\n')
            f.write(f'    raw_action: {escape_js_string(event["raw_action"])}\n')
            f.write(f'  }}{comma}\n')
        
        f.write('];\n')


def extract_step_number_from_log_line(line: str) -> Optional[int]:
    """
    Extract step number from APE log line.
    
    Args:
        line: Log line to parse
        
    Returns:
        Step number if found, None otherwise
    """
    # Pattern: [APE] >>>>>>>> SATA begin step [<step_num>]
    match = re.search(r'\[APE\] >>>>>>>> SATA begin step \[(\d+)\]', line)
    if match:
        return int(match.group(1))
    return None


def extract_ape_edge_info(lines: List[str], start_idx: int) -> Optional[Tuple[str, str, str]]:
    """
    Extract edge information from APE log starting at given index.
    
    Args:
        lines: All log lines
        start_idx: Index of "Adding edge..." line
        
    Returns:
        Tuple of (source_state, action_str, target_state) or None
    """
    if start_idx + 3 >= len(lines):
        return None
    
    try:
        source_line = lines[start_idx + 1].strip()
        action_line = lines[start_idx + 2].strip()  
        target_line = lines[start_idx + 3].strip()
        
        # Extract source state
        source_match = re.search(r'\[APE\]\s+Source:\s+(.+)', source_line)
        if not source_match:
            return None
        source_raw = source_match.group(1).strip()
        
        # Extract action description
        action_match = re.search(r'\[APE\]\s+Action:\s+(.+)', action_line)
        if not action_match:
            return None
        action_raw = action_match.group(1).strip()
        
        # Extract target state
        target_match = re.search(r'\[APE\]\s+Target:\s+(.+)', target_line)
        if not target_match:
            return None
        target_raw = target_match.group(1).strip()
        
        return source_raw, action_raw, target_raw
        
    except Exception:
        return None


def extract_state_key_from_raw(raw_state: str) -> str:
    """
    Extract state key from raw APE state string.
    
    Args:
        raw_state: Raw state string from APE log
        
    Returns:
        State key (e.g., "g0s0")
    """
    # Pattern: g0s0[...] or similar
    match = re.match(r'(g\d+s\d+)', raw_state)
    if match:
        return match.group(1)
    return raw_state