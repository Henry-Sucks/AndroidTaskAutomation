"""Generate node descriptions with cluster context.

This script parses `utg_clustered.js` to obtain all nodes along with their
`cluster_id`, associates each node with a functional cluster summary from
`cluster_info.json`, builds an English prompt, queries a VLM, and writes
newline-delimited JSON objects to `node_desc.jsonl`:

{
  "node_id": ..., 
  "description": ..., 
  "cluster_id": ..., 
  "image": ..., 
  "xml": ...
}

Assumptions:
- `utg_clustered.js` uses JSON-like objects for `var nodes = [ ... ];`.
- Images reside either in `<UTG_DIR>/screenshot/` or directly in `<UTG_DIR>`.
- XML files reside either in `<UTG_DIR>/xml/` or directly in `<UTG_DIR>`.
- Cluster summaries (if present) are stored in `cluster_info.json` under
  `clusters[cluster_id]['summary']` potentially as a fenced JSON block.

If a cluster has no summary, a placeholder is used. If an image file is
missing, the description will record the absence and skip the VLM call.
"""

import os
import re
import json
import sys
from typing import Dict, List, Any

current_path = os.getcwd()
sys.path.append(current_path)

from utils import load_json  # Provided by existing project
from clients.vlm_client import VLMClient  # VLM client
from tqdm import tqdm

UTG_DIR_DEFAULT = os.path.join(
    os.path.dirname(__file__), '..', 'utg', 'NetEase Cloud Music'
)

UTG_CLUSTERED_FILENAME = 'utg_clustered.js'
CLUSTER_INFO_FILENAME = 'cluster_info.json'
OUTPUT_JSONL = 'node_desc.jsonl'


def load_cluster_summaries(cluster_info_path: str) -> Dict[str, str]:
    data = load_json(cluster_info_path)
    summaries: Dict[str, str] = {}
    clusters = data.get('clusters', {})
    for cid, cobj in clusters.items():
        raw = cobj.get('summary')
        if not raw:
            summaries[cid] = 'No functional summary available.'
            continue
        # Extract fenced JSON if present
        match = re.search(r'```json\s*(\{.*?\})\s*```', raw, re.DOTALL)
        summary_text = ''
        if match:
            block = match.group(1)
            try:
                parsed = json.loads(block)
                overall = parsed.get('cluster_overall_function')
                caps = parsed.get('key_functional_capabilities', [])
                parts = []
                if overall:
                    parts.append(f"Overall function: {overall}.")
                if caps:
                    parts.append("Key capabilities: " + '; '.join(caps))
                summary_text = ' '.join(parts) if parts else block
            except Exception:
                summary_text = raw.replace('\n', ' ').strip()
        else:
            summary_text = raw.replace('\n', ' ').strip()
        summaries[cid] = summary_text or 'No functional summary available.'
    return summaries


def parse_nodes(utg_clustered_path: str) -> List[Dict[str, Any]]:
    text = open(utg_clustered_path, 'r', encoding='utf-8').read()
    # Capture content between var nodes = [ and the closing ];
    match = re.search(r'var\s+nodes\s*=\s*\[(.*?)\]\s*;', text, re.DOTALL)
    if not match:
        raise ValueError('Could not locate nodes array in utg_clustered.js')
    array_body = match.group(1)
    # Remove trailing commas after last object (defensive)
    array_body = re.sub(r',\s*$', '', array_body.strip())
    json_text = '[' + array_body + ']'
    try:
        return json.loads(json_text)
    except json.JSONDecodeError:
        # Fallback: extract each object manually
        objs = []
        for obj_match in re.finditer(r'\{.*?\}', array_body, re.DOTALL):
            obj_text = obj_match.group(0)
            # Attempt to coerce to JSON by removing trailing commas within keys
            # Basic cleanup (no comments expected)
            try:
                objs.append(json.loads(obj_text))
            except Exception:
                continue
        if not objs:
            raise
        return objs


def build_prompt(cluster_id: str, cluster_summary: str) -> str:
    return f"""You are an accessibility-oriented AI assistant describing a mobile app screen.

Additional context:
This screen belongs to a functional group (cluster {cluster_id}) whose overall purpose can be summarized as:
"{cluster_summary}"
Use this information only to understand the general function of the page, but base your description strictly on what is visually present in the screenshot. Do not invent UI elements or actions that are not visible.

Task:
Describe the screenshot in three sections (Top, Middle, Bottom). Identify and list all interactive UI elements (buttons, tabs, lists, input fields, sliders, actionable icons). Do NOT describe the status bar (time, battery, network). Avoid hallucination and remain faithful to the screenshot.

Finally, provide ONE concise sentence that best summarizes the screen’s core purpose, informed by both the visible UI and the functional theme of its cluster.

Output Format:
Top: <text>
Middle: <text>
Bottom: <text>
Overall: <one concise sentence>
"""


def extract_structured_sections(raw: str) -> Dict[str, str]:
    # Normalize separators
    cleaned = raw.replace('\r', '')
    pattern_map = {
        'top': r'Top\s*:\s*(.*?)\nMiddle\s*:',
        'middle': r'Middle\s*:\s*(.*?)\nBottom\s*:',
        'bottom': r'Bottom\s*:\s*(.*?)\nOverall\s*:',
        'overall': r'Overall\s*:\s*(.*)'
    }
    result = {}
    for key, pat in pattern_map.items():
        try:
            m = re.search(pat, cleaned, re.DOTALL)
            result[key] = (m.group(1).strip() if m else '')
        except Exception:
            result[key] = ''
    return result


def describe_node(image_path: str, prompt: str) -> str:
    if not os.path.exists(image_path):
        return f"Image not found at {image_path}."
    client = VLMClient()
    try:
        resp = client.run(prompt=prompt, image_url=image_path, enable_thinking=False)
        # VLMClient.run returns a dict with key 'content'
        content = resp.get('content', '') if isinstance(resp, dict) else str(resp)
        return content
    except Exception as e:
        return f"VLM client failed: {e}"


def main(utg_dir: str):
    utg_clustered_path = os.path.join(utg_dir, UTG_CLUSTERED_FILENAME)
    cluster_info_path = os.path.join(utg_dir, CLUSTER_INFO_FILENAME)
    output_path = os.path.join(utg_dir, OUTPUT_JSONL)

    cluster_summaries = load_cluster_summaries(cluster_info_path)
    nodes = parse_nodes(utg_clustered_path)

    screenshot_dir = os.path.join(utg_dir, 'screenshot')
    xml_dir = os.path.join(utg_dir, 'xml')

    with open(output_path, 'w', encoding='utf-8') as out_f:
        for node in tqdm(nodes, desc='Describing nodes'):
            node_id = node.get('id')
            cluster_id = str(node.get('cluster_id', ''))
            image_name = node.get('image') or ''
            xml_name = node.get('xml') or ''

            # Resolve image path
            img_path = os.path.join(screenshot_dir, image_name)
            if not os.path.exists(img_path):
                img_path = os.path.join(utg_dir, image_name)

            # Resolve xml path
            xml_path = os.path.join(xml_dir, xml_name)
            if not os.path.exists(xml_path):
                xml_path = os.path.join(utg_dir, xml_name)

            cluster_summary = cluster_summaries.get(cluster_id, 'No functional summary available.')
            prompt = build_prompt(cluster_id, cluster_summary)
            raw_desc = describe_node(img_path, prompt)
            sections = extract_structured_sections(raw_desc)

            # Compose final description (fallback if parsing failed)
            if sections.get('overall') or sections.get('top'):
                description = json.dumps(sections, ensure_ascii=False)
            else:
                description = raw_desc.replace('\n', ' ').strip()

            record = {
                'node_id': node_id,
                'cluster_id': cluster_id,
                'image': image_name,
                'xml': xml_name,
                'description': description
            }
            out_f.write(json.dumps(record, ensure_ascii=False) + '\n')

    print(f'Wrote node descriptions to {output_path}')


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Generate node descriptions with cluster context (JSONL).')
    parser.add_argument('--utg_dir', default=UTG_DIR_DEFAULT, help='Path to UTG directory containing utg_clustered.js and cluster_info.json')
    args = parser.parse_args()
    main(os.path.abspath(args.utg_dir))




