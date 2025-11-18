import json
import re

# Read the current file
with open(r'C:\Projects\AndroidTaskAutomation\2_utg_clustering\utg\original_greedy_dfs_20251106_160351_louvain_clustered\utg_clustered.js', 'r', encoding='utf-8') as f:
    content = f.read()

# Cluster colors mapping
cluster_colors = {
    "91": "#FF6B6B", "88": "#4ECDC4", "117": "#45B7D1", "135": "#96CEB4", "132": "#FFEAA7",
    "55": "#DDA0DD", "25": "#98D8C8", "44": "#F7DC6F", "62": "#BB8FCE", "115": "#85C1E9",
    "108": "#F8C471", "69": "#82E0AA", "46": "#F1948A", "103": "#AED6F1", "35": "#A9DFBF",
    "120": "#F9E79F", "75": "#D7BDE2", "64": "#A3E4D7", "73": "#FCF3CF", "107": "#FADBD8",
    "30": "#D5DBDB", "10": "#EBDEF0"
}

# Community sizes
community_sizes = {
    "91": 46, "88": 24, "117": 3, "135": 10, "132": 8, "55": 16, "25": 16, "44": 8, "62": 8, "115": 20,
    "108": 4, "69": 24, "46": 28, "103": 2, "35": 6, "120": 2, "75": 42, "64": 9, "73": 10, "107": 4, "30": 2, "10": 2
}

# Extract the nodes array using regex
nodes_pattern = r'var nodes = \[(.*?)\];'
nodes_match = re.search(nodes_pattern, content, re.DOTALL)

if nodes_match:
    nodes_content = nodes_match.group(1)
    
    # Parse individual node objects
    node_pattern = r'\{"id": "([^"]+)", "image": "([^"]+)", "cluster_id": "([^"]+)"[^}]*\}'
    nodes = re.findall(node_pattern, nodes_content)
    
    # Generate enhanced nodes
    enhanced_nodes = []
    for node_id, image, cluster_id in nodes:
        # Ensure states/ prefix
        if not image.startswith('states/'):
            image = 'states/' + image
        
        # Get cluster info
        color = cluster_colors.get(cluster_id, "#CCCCCC")
        size = community_sizes.get(cluster_id, 1)
        
        # Create enhanced node
        enhanced_node = {
            "id": node_id,
            "image": image,
            "cluster_id": cluster_id,
            "color": {"background": color, "border": color},
            "title": f"Cluster {cluster_id} ({size} states)"
        }
        enhanced_nodes.append(enhanced_node)
    
    # Convert to JavaScript format
    js_nodes = "var nodes = [\n"
    for i, node in enumerate(enhanced_nodes):
        js_nodes += "  " + json.dumps(node, separators=(',', ': '))
        if i < len(enhanced_nodes) - 1:
            js_nodes += ","
        js_nodes += "\n"
    js_nodes += "];"
    
    # Replace in content
    new_content = re.sub(nodes_pattern, js_nodes, content, flags=re.DOTALL)
    
    # Write back to file
    with open(r'C:\Projects\AndroidTaskAutomation\2_utg_clustering\utg\original_greedy_dfs_20251106_160351_louvain_clustered\utg_clustered.js', 'w', encoding='utf-8') as f:
        f.write(new_content)
    
    print(f"Successfully updated {len(enhanced_nodes)} nodes with cluster information")
else:
    print("Could not find nodes array in the file")