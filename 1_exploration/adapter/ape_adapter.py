#!/usr/bin/env python3
"""
APE Result Parser

Parses APE (Android Package Explorer) automation results and converts them
to standardized UTG (UI Transition Graph) format.

Input structure:
/input
    ape_output.log          # APE execution log
    step-*.xml             # UI XML files  
    step-*.png             # Screenshots

Output structure:
/output
    /states/
        <state_id>.json    # State metadata
        <state_id>.xml     # UI XML
        <state_id>.png     # Screenshot
    /events/
        <event_id>.json    # Event metadata
    utg.js                 # Complete UTG in JavaScript format

Usage:
    python ape_parse.py <input_dir> <output_dir>
"""

import argparse
import re
import shutil
import sys
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Set

from utg_utils import (
    compute_state_id, create_directories, write_json_file, 
    copy_file_safe, write_utg_js, extract_step_number_from_log_line,
    extract_ape_edge_info, extract_state_key_from_raw
)


def parse_log(log_path: Path) -> Tuple[List[int], List[Tuple[str, str, str]]]:
    """
    Parse APE log file to extract steps and transitions.
    
    Args:
        log_path: Path to APE log file
        
    Returns:
        Tuple of (step_numbers, transitions)
        - step_numbers: List of step numbers found in log
        - transitions: List of (source_raw, action_str, target_raw) tuples
    """
    steps = []
    transitions = []
    
    try:
        with open(log_path, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
    except Exception as e:
        print(f"Error reading log file {log_path}: {e}")
        return [], []

    print(f"{len(lines)} lines read from log file")

    # Parse steps and transitions
    for i, line in enumerate(lines):
        # Extract step numbers
        step_num = extract_step_number_from_log_line(line)
        if step_num is not None:
            steps.append(step_num)
        
        # Extract transitions
        if '[APE] === Adding edge...' in line:
            edge_info = extract_ape_edge_info(lines, i)
            if edge_info:
                transitions.append(edge_info)
    
    print(f"Parsed log: {len(steps)} steps, {len(transitions)} transitions")
    return steps, transitions


def enhanced_parse_log(log_path: Path) -> Tuple[List[Dict], List[Dict]]:
    """
    Enhanced APE log parser that extracts step information with Source/Action/Target.
    
    Args:
        log_path: Path to APE log file
        
    Returns:
        Tuple of (step_info_list, transition_info_list)
        - step_info_list: List of step dictionaries with step number and activity
        - transition_info_list: List of transition dictionaries with step, source, action, target
    """
    steps_info = []
    transitions_info = []
    
    try:
        with open(log_path, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
    except Exception as e:
        print(f"Error reading log file {log_path}: {e}")
        return [], []

    print(f"{len(lines)} lines read from log file")
    
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        
        # Look for step begin pattern
        step_match = re.search(r'\[APE\] >>>>>>>> SATA begin step \[(\d+)\]', line)
        if step_match:
            step_num = int(step_match.group(1))
            
            # Extract activity from subsequent lines
            activity = None
            for j in range(i + 1, min(i + 50, len(lines))):
                activity_match = re.search(r'Entry state: .*?([a-zA-Z0-9_.]+Activity)', lines[j])
                if activity_match:
                    activity = activity_match.group(1)
                    break
                if 'SATA end step' in lines[j] or 'SATA begin step' in lines[j]:
                    break
            
            if not activity:
                # Try to find activity in state creation lines
                for j in range(max(0, i - 20), i + 20):
                    if j < len(lines):
                        state_match = re.search(r'Create state.*?([a-zA-Z0-9_.]+Activity)', lines[j])
                        if state_match:
                            activity = state_match.group(1)
                            break
            
            steps_info.append({
                'step': step_num,
                'activity': activity or "unknown.Activity"
            })
            
            # Look for Source/Action/Target pattern after step begins
            source_line = None
            action_line = None
            target_line = None
            
            for j in range(i + 1, min(i + 100, len(lines))):
                if 'SATA end step' in lines[j] or ('SATA begin step' in lines[j] and j > i):
                    break
                    
                if lines[j].strip().startswith('[APE]     Source:'):
                    source_line = lines[j].strip()
                elif lines[j].strip().startswith('[APE]     Action:'):
                    action_line = lines[j].strip()
                elif lines[j].strip().startswith('[APE]     Target:'):
                    target_line = lines[j].strip()
                    
                    # When we have all three, create transition
                    if source_line and action_line and target_line:
                        source_match = re.search(r'\[APE\]\s+Source:\s+(.+)', source_line)
                        action_match = re.search(r'\[APE\]\s+Action:\s+(.+)', action_line)
                        target_match = re.search(r'\[APE\]\s+Target:\s+(.+)', target_line)
                        
                        if source_match and action_match and target_match:
                            transitions_info.append({
                                'step': step_num,
                                'source_raw': source_match.group(1).strip(),
                                'action_raw': action_match.group(1).strip(),
                                'target_raw': target_match.group(1).strip()
                            })
                        
                        # Reset for next potential transition in same step
                        source_line = None
                        action_line = None
                        target_line = None
        
        i += 1
    
    print(f"Enhanced parsing found: {len(steps_info)} steps, {len(transitions_info)} transitions")
    return steps_info, transitions_info


def parse_xml(xml_path: Path) -> Optional[str]:
    """
    Parse XML file and return content.
    
    Args:
        xml_path: Path to XML file
        
    Returns:
        XML content as string, or None if error
    """
    try:
        with open(xml_path, 'r', encoding='utf-8', errors='ignore') as f:
            return f.read()
    except Exception as e:
        print(f"Error reading XML file {xml_path}: {e}")
        return None


def generate_state_json(tag: str, state_id: str, step: int, activity: str, xml_path: str, screenshot_path: str) -> Dict:
    """
    Generate state JSON metadata using new data structure.
    
    Args:
        tag: State tag (e.g., "s0001")
        state_id: Unique state identifier computed from XML
        step: Step number
        activity: Activity name
        xml_path: Path to XML file
        screenshot_path: Path to screenshot file
        
    Returns:
        State metadata dictionary
    """
    return {
        "tag": tag,
        "state_id": state_id,
        "step": step,
        "activity": activity,
        "xml_path": xml_path,
        "screenshot_path": screenshot_path
    }


def generate_event_json(tag: str, event_id: str, step: int, from_state_id: str, to_state_id: str, raw_action: str) -> Dict:
    """
    Generate event JSON metadata using new data structure.
    
    Args:
        tag: Event tag (e.g., "e0001")
        event_id: Unique event identifier (from_state_id --> to_state_id)
        step: Step number
        from_state_id: Source state ID
        to_state_id: Target state ID
        raw_action: Raw action string from APE log
        
    Returns:
        Event metadata dictionary
    """
    return {
        "tag": tag,
        "event_id": event_id,
        "step": step,
        "from": from_state_id,
        "to": to_state_id,
        "raw_action": raw_action
    }


def extract_action_description(action_raw: str) -> str:
    """
    Extract human-readable action description from raw APE action string.
    
    Args:
        action_raw: Raw action string from APE log
        
    Returns:
        Cleaned action description
    """
    # Extract action type and target info
    # Example: g0a8[1,1][1]@MODEL_LONG_CLICKclass=android.widget.TextView;resource-id=net.gsantner.markor:id/description;...
    
    # Extract action type
    action_type_match = re.search(r'@(MODEL_[A-Z_]+)', action_raw)
    action_type = action_type_match.group(1) if action_type_match else "UNKNOWN"
    
    # Extract class info
    class_match = re.search(r'class=([^;]+)', action_raw)
    class_name = class_match.group(1) if class_match else ""
    
    # Extract resource ID
    resource_match = re.search(r'resource-id=([^;]+)', action_raw)
    resource_id = resource_match.group(1) if resource_match else ""
    
    # Extract text content
    text_match = re.search(r'\[([^\]]+)\]$', action_raw)
    text_content = text_match.group(1) if text_match else ""
    
    # Build description
    parts = []
    if action_type:
        action_name = action_type.replace('MODEL_', '').replace('_', ' ').title()
        parts.append(action_name)
    
    if text_content and text_content != "":
        parts.append(f'"{text_content}"')
    elif resource_id:
        parts.append(f"#{resource_id}")
    elif class_name:
        parts.append(f"({class_name.split('.')[-1]})")
    
    return " ".join(parts) if parts else action_raw


def main():
    """Main execution function."""
    parser = argparse.ArgumentParser(description='Parse APE results to UTG format')
    parser.add_argument('input_dir', help='Input directory containing APE results')
    parser.add_argument('output_dir', help='Output directory for UTG files')
    
    args = parser.parse_args()
    
    input_path = Path(args.input_dir)
    output_path = Path(args.output_dir)
    
    if not input_path.exists():
        print(f"Error: Input directory {input_path} does not exist")
        sys.exit(1)
    
    log_path = input_path / 'ape_output.log'
    if not log_path.exists():
        print(f"Error: Log file {log_path} not found")
        sys.exit(1)
    
    # Create output directories
    create_directories(output_path)
    
    # Parse log file using enhanced parser
    print("Parsing log file...")
    steps_info, transitions_info = enhanced_parse_log(log_path)
    
    if not steps_info:
        print("No steps found in log file")
        sys.exit(1)
    
    # Process states - create one state per step
    print("Processing states...")
    states = []
    step_to_state_id = {}  # Map step number to state ID
    
    for step_info in steps_info:
        step_num = step_info['step']
        activity = step_info['activity']
        
        xml_file = input_path / f'step-{step_num}.xml'
        png_file = input_path / f'step-{step_num}.png'
        
        if not xml_file.exists():
            print(f"Warning: XML file {xml_file} not found for step {step_num}")
            continue
        
        # Parse XML and compute unique state ID
        xml_content = parse_xml(xml_file)
        if xml_content is None:
            continue
        
        state_id = compute_state_id(xml_content)
        step_to_state_id[step_num] = state_id
        
        # Generate state files with step-based naming
        tag = f"s{step_num:04d}"
        state_xml_name = f"{tag}.xml"
        state_png_name = f"{tag}.png"
        
        # Create state JSON with new structure
        state_json = generate_state_json(
            tag=tag,
            state_id=state_id,
            step=step_num,
            activity=activity,
            xml_path=state_xml_name,
            screenshot_path=state_png_name
        )
        
        # Write state JSON
        state_json_path = output_path / 'states' / f"{tag}.json"
        write_json_file(state_json, state_json_path)
        
        # Copy XML file
        target_xml = output_path / 'states' / state_xml_name
        copy_file_safe(xml_file, target_xml)
        
        # Copy PNG file if exists
        if png_file.exists():
            target_png = output_path / 'states' / state_png_name
            copy_file_safe(png_file, target_png)
        
        states.append(state_json)
        print(f"Processed state {tag} (ID: {state_id}) from step {step_num}")
    
    # Process events/transitions
    print("Processing transitions...")
    events = []
    
    for transition_info in transitions_info:
        step_num = transition_info['step']
        raw_action = transition_info['action_raw']
        
        # Generate event tag
        tag = f"e{step_num:04d}"
        
        # Determine from and to states
        # from_state = step N-1, to_state = step N
        from_step = step_num - 1 if step_num > 1 else step_num
        to_step = step_num
        
        from_state_id = step_to_state_id.get(from_step)
        to_state_id = step_to_state_id.get(to_step)
        
        if from_state_id and to_state_id:
            # Generate event_id as "from_state_id --> to_state_id"
            event_id = f"{from_state_id}-->{to_state_id}"
            
            # Create event JSON with new structure
            event_json = generate_event_json(
                tag=tag,
                event_id=event_id,
                step=step_num,
                from_state_id=from_state_id,
                to_state_id=to_state_id,
                raw_action=raw_action
            )
            
            # Write event JSON
            event_json_path = output_path / 'events' / f"{tag}.json"
            write_json_file(event_json, event_json_path)
            
            events.append(event_json)
            print(f"Processed event {tag}: step {step_num} ({from_state_id[:8]} -> {to_state_id[:8]})")
    
    # Generate UTG.js and utg.json
    print("Generating UTG files...")
    write_utg_js(states, events, output_path)
    
    # Generate final UTG JSON with new structure
    utg_data = {
        "states": [
            {
                "state_id": state["state_id"],
                "activity": state["activity"],
                "step": state["step"]
            }
            for state in states
        ],
        "events": [
            {
                "tag": event["tag"],
                "event_id": event["event_id"],
                "step": event["step"],
                "from": event["from"],
                "to": event["to"],
                "raw_action": event["raw_action"]
            }
            for event in events
        ]
    }
    
    utg_json_path = output_path / 'utg.json'
    write_json_file(utg_data, utg_json_path)
    
    # Print summary
    print(f"\nParsing complete!")
    print(f"States: {len(states)}")
    print(f"Events: {len(events)}")
    print(f"Output directory: {output_path}")
    print(f"Generated files: utg.js, utg.json")


if __name__ == '__main__':
    main()
