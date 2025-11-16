#!/usr/bin/env python3
"""
Script to enhance nodes in UTG clustered JavaScript file with:
1. Correct image paths (add "states/" prefix)
2. Color mapping based on cluster_id
3. Proper title with cluster information
"""

import json
import re

def enhance_utg_nodes():
    # Read the original file
    input_file = r"C:\Projects\AndroidTaskAutomation\2_utg_clustering\utg\original_greedy_dfs_20251106_160351_louvain_clustered\utg_clustered.js"
    
    with open(input_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Extract clusteringStats.community_sizes
    community_sizes_match = re.search(r'"community_sizes":\s*({[^}]+})', content)
    if not community_sizes_match:
        raise ValueError("Could not find community_sizes in the file")
    
    community_sizes_str = community_sizes_match.group(1)
    community_sizes = json.loads(community_sizes_str)
    
    # Extract clusterColors
    cluster_colors_match = re.search(r'var clusterColors = ({[^}]+});', content)
    if not cluster_colors_match:
        raise ValueError("Could not find clusterColors in the file")
    
    cluster_colors_str = cluster_colors_match.group(1)
    cluster_colors = json.loads(cluster_colors_str.replace("'", '"'))
    
    # Extract the nodes array
    nodes_match = re.search(r'var nodes = \[(.*?)\];', content, re.DOTALL)
    if not nodes_match:
        raise ValueError("Could not find nodes array in the file")
    
    nodes_str = nodes_match.group(1)
    
    # Parse nodes - handle JavaScript object notation
    # Split by objects while preserving the structure
    node_objects = []
    brace_count = 0
    current_obj = ""
    
    for char in nodes_str:
        current_obj += char
        if char == '{':
            brace_count += 1
        elif char == '}':
            brace_count -= 1
            if brace_count == 0:
                # Complete object found
                node_objects.append(current_obj.strip())
                current_obj = ""
    
    # Process each node
    enhanced_nodes = []
    
    for node_str in node_objects:
        if not node_str.strip() or node_str.strip() == ',':
            continue
            
        # Clean up the node string
        node_str = node_str.strip().rstrip(',').strip()
        
        # Convert JavaScript object to JSON format for parsing
        json_str = node_str
        json_str = re.sub(r'(\w+):', r'"\1":', json_str)  # Add quotes to keys
        json_str = re.sub(r':\s*([^",\[\{][^,\]\}]*?)([,\]\}])', r': "\1"\2', json_str)  # Add quotes to string values
        json_str = re.sub(r':\s*"([^"]*)"([,\]\}])', r': "\1"\2', json_str)  # Fix double quotes
        
        try:
            node = json.loads(json_str)
        except json.JSONDecodeError:
            # Fallback: manual parsing
            node = {}
            # Extract id
            id_match = re.search(r'"id":\s*"([^"]+)"', node_str)
            if id_match:
                node['id'] = id_match.group(1)
            
            # Extract image
            image_match = re.search(r'"image":\s*"([^"]+)"', node_str)
            if image_match:
                node['image'] = image_match.group(1)
            
            # Extract cluster_id
            cluster_match = re.search(r'"cluster_id":\s*"([^"]+)"', node_str)
            if cluster_match:
                node['cluster_id'] = cluster_match.group(1)
        
        # Skip if missing required fields
        if 'id' not in node or 'cluster_id' not in node:
            continue
            
        # Enhance the node
        cluster_id = node['cluster_id']
        
        # 1. Fix image path (add "states/" prefix if not present)
        if 'image' in node:
            image = node['image']
            if not image.startswith('states/'):
                node['image'] = 'states/' + image
        
        # 2. Add color mapping
        if cluster_id in cluster_colors:
            color = cluster_colors[cluster_id]
            node['color'] = {
                "background": color,
                "border": color
            }
        
        # 3. Add title with cluster information
        community_size = community_sizes.get(cluster_id, 0)
        node['title'] = f"Cluster {cluster_id} ({community_size} states)"
        
        enhanced_nodes.append(node)
    
    # Generate the enhanced nodes array JavaScript code
    nodes_js_lines = []
    
    for i, node in enumerate(enhanced_nodes):
        # Convert back to JavaScript object notation
        obj_parts = []
        
        obj_parts.append(f'"id": "{node["id"]}"')
        
        if 'image' in node:
            obj_parts.append(f'"image": "{node["image"]}"')
            
        obj_parts.append(f'"cluster_id": "{node["cluster_id"]}"')
        
        if 'color' in node:
            color_obj = f'{{"background": "{node["color"]["background"]}", "border": "{node["color"]["border"]}"}}'
            obj_parts.append(f'"color": {color_obj}')
            
        if 'title' in node:
            obj_parts.append(f'"title": "{node["title"]}"')
        
        obj_str = "  {" + ", ".join(obj_parts) + "}"
        
        # Add comma except for last item
        if i < len(enhanced_nodes) - 1:
            obj_str += ","
            
        nodes_js_lines.append(obj_str)
    
    enhanced_nodes_str = "var nodes = [\n" + "\n".join(nodes_js_lines) + "\n];"
    
    print("Enhanced nodes array:")
    print(enhanced_nodes_str)
    
    # Also save to file for reference
    with open('enhanced_nodes.js', 'w', encoding='utf-8') as f:
        f.write(enhanced_nodes_str)
    
    print(f"\nProcessed {len(enhanced_nodes)} nodes")
    print("Enhanced nodes saved to 'enhanced_nodes.js'")

if __name__ == "__main__":
    enhance_utg_nodes()