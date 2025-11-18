#!/usr/bin/env python3
"""
UTG Visualization Generator

This script generates an interactive HTML visualization of the User Transition Graph (UTG)
and starts a local HTTP server to serve it.

Usage:
    python visualize/generate_utg_view.py [output_dir] [port]

Arguments:
    output_dir: Directory containing UTG data (default: "1_exploration/output_test")
    port: HTTP server port (default: 8000)

Dependencies: Only Python 3 standard library
"""

import json
import re
import http.server
import socketserver
import webbrowser
import threading
import time
import sys
from pathlib import Path


class UTGDataLoader:
    """Loads UTG data from utg.js or utg.json"""
    
    def __init__(self, output_dir: Path):
        self.output_dir = Path(output_dir)
        self.nodes = []
        self.edges = []
        
    def load_data(self):
        """Load UTG data from available files"""
        js_path = self.output_dir / "utg.js"
        
        if js_path.exists():
            print(f"Loading UTG data from {js_path}")
            self._load_from_js(js_path)
        else:
            raise FileNotFoundError(f"No UTG data found in {self.output_dir}")
            
        print(f"Loaded {len(self.nodes)} nodes and {len(self.edges)} edges")
        return self.nodes, self.edges
    
    def _load_from_json(self, json_path: Path):
        """Load from utg.json format"""
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        self.nodes = data.get('states', [])
        self.edges = data.get('events', [])
        
        # Convert to vis-network format
        self._convert_nodes_format()
        self._convert_edges_format()
    
    def _load_from_js(self, js_path: Path):
        """Load from utg.js format with var nodes = [...]; var edges = [...]"""
        print("Note: Skipping JS parsing, will use external file loading in HTML")
        # For now, we'll just set empty arrays and let the HTML load the JS directly
        # This avoids the complex JS-to-Python parsing issues
        self.nodes = []
        self.edges = []
    
    def _convert_nodes_format(self):
        """Convert nodes to vis-network format"""
        for node in self.nodes:
            # Ensure required fields for vis-network
            if 'id' not in node and 'state_id' in node:
                node['id'] = node['state_id']
            
            # Create label from step and activity
            step = node.get('step', '?')
            activity = node.get('activity', 'Unknown')
            activity_short = activity.split('.')[-1] if activity else 'Unknown'
            node['label'] = f"s{step:04d}\n{activity_short}"
            
            # Set image path (relative to HTML file)
            if 'image' not in node and 'screenshot_path' in node:
                image_name = Path(node['screenshot_path']).name
                node['image'] = f"../states/{image_name}"
            elif 'image' not in node:
                # Generate image path from step
                node['image'] = f"../states/s{step:04d}.png"
            else:
                # Ensure relative path
                if not node['image'].startswith('../'):
                    node['image'] = f"../{node['image']}"
    
    def _convert_edges_format(self):
        """Convert edges to vis-network format"""
        for edge in self.edges:
            # Ensure required fields for vis-network
            if 'id' not in edge and 'event_id' in edge:
                edge['id'] = edge['event_id']
            elif 'id' not in edge and 'tag' in edge:
                edge['id'] = edge['tag']
            
            # Set from/to for vis-network
            if 'from' not in edge and 'source' in edge:
                edge['from'] = edge['source']
            if 'to' not in edge and 'target' in edge:
                edge['to'] = edge['target']
            
            # Create label from step or tag
            step = edge.get('step', '')
            tag = edge.get('tag', '')
            if step:
                edge['label'] = f"e{step:04d}"
            elif tag:
                edge['label'] = tag
            else:
                edge['label'] = ""


def generate_html(nodes, edges, output_path: Path, use_external_js=False):
    """Generate the interactive HTML visualization"""
    
    # Choose data source based on whether to use external JS
    if use_external_js:
        utg_data_script = """
    <!-- Load UTG data from external utg.js file -->
    <script src="utg.js"></script>
    
    <script>
        // UTG Data from external file
        const utg_nodes = (typeof nodes !== 'undefined') ? nodes : [];
        const utg_edges = (typeof edges !== 'undefined') ? edges : [];
        """
    else:
        utg_data_script = f"""
    <script>
        // UTG Data embedded by Python script
        const utg_nodes = {json.dumps(nodes, indent=2)};
        const utg_edges = {json.dumps(edges, indent=2)};
        """
    
    html_content = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>UTG Viewer - User Transition Graph</title>
    
    <!-- vis-network from CDN -->
    <script src="https://unpkg.com/vis-network@9.1.2/dist/vis-network.min.js"></script>
    <link href="https://unpkg.com/vis-network/styles/vis-network.min.css" rel="stylesheet" />
    
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: Arial, sans-serif;
            background: #f5f5f5;
        }
        
        #toolbar {
            background: white;
            padding: 10px;
            border-bottom: 1px solid #ddd;
            display: flex;
            align-items: center;
            gap: 15px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        
        #toolbar h1 {
            font-size: 18px;
            color: #333;
            margin-right: 20px;
        }
        
        #toolbar button {
            padding: 8px 16px;
            border: 1px solid #ddd;
            background: white;
            border-radius: 4px;
            cursor: pointer;
            font-size: 14px;
        }
        
        #toolbar button:hover {
            background: #f0f0f0;
        }
        
        #searchInput {
            padding: 8px;
            border: 1px solid #ddd;
            border-radius: 4px;
            width: 200px;
        }
        
        #filterSelect {
            padding: 8px;
            border: 1px solid #ddd;
            border-radius: 4px;
            width: 150px;
        }
        
        .main-container {
            display: flex;
            height: calc(100vh - 60px);
        }
        
        #network {
            flex: 1;
            background: white;
            border-right: 1px solid #ddd;
        }
        
        #sidebar {
            width: 350px;
            background: white;
            overflow-y: auto;
            padding: 20px;
            border-left: 1px solid #ddd;
        }
        
        .sidebar-section {
            margin-bottom: 20px;
        }
        
        .sidebar-section h3 {
            margin-bottom: 10px;
            color: #333;
            border-bottom: 1px solid #eee;
            padding-bottom: 5px;
        }
        
        .detail-item {
            margin-bottom: 8px;
            display: flex;
            flex-wrap: wrap;
        }
        
        .detail-label {
            font-weight: bold;
            color: #666;
            min-width: 80px;
            margin-right: 10px;
        }
        
        .detail-value {
            color: #333;
            word-break: break-all;
        }
        
        .screenshot-container {
            text-align: center;
            margin: 15px 0;
        }
        
        .screenshot-container img {
            max-width: 100%;
            max-height: 300px;
            border: 1px solid #ddd;
            border-radius: 4px;
        }
        
        .action-buttons {
            display: flex;
            gap: 10px;
            margin-top: 10px;
        }
        
        .btn {
            padding: 6px 12px;
            border: 1px solid #ddd;
            background: #f8f9fa;
            border-radius: 4px;
            cursor: pointer;
            text-decoration: none;
            font-size: 12px;
            color: #333;
        }
        
        .btn:hover {
            background: #e9ecef;
        }
        
        .list-panel {
            max-height: 300px;
            overflow-y: auto;
            border: 1px solid #eee;
            border-radius: 4px;
        }
        
        .list-item {
            padding: 8px 12px;
            border-bottom: 1px solid #f0f0f0;
            cursor: pointer;
            font-size: 13px;
        }
        
        .list-item:hover {
            background: #f8f9fa;
        }
        
        .list-item.selected {
            background: #e3f2fd;
        }
        
        .no-selection {
            color: #999;
            font-style: italic;
            text-align: center;
            padding: 40px 20px;
        }
    </style>
</head>
<body>
    <div id="toolbar">
        <h1>UTG Viewer</h1>
        <button onclick="fitNetwork()">Fit All</button>
        <input type="text" id="searchInput" placeholder="Search by step, activity, state_id..." onkeyup="searchNodes()">
        <select id="filterSelect" onchange="filterByActivity()">
            <option value="">All Activities</option>
        </select>
        <button onclick="togglePanel('nodes')">Nodes</button>
        <button onclick="togglePanel('edges')">Edges</button>
        <span style="margin-left: auto; font-size: 12px; color: #666;">
            Nodes: <span id="nodeCount">0</span> | Edges: <span id="edgeCount">0</span>
        </span>
    </div>
    
    <div class="main-container">
        <div id="network"></div>
        <div id="sidebar">
            <div class="no-selection">
                Click on a node or edge to view details
            </div>
        </div>
    </div>

""" + utg_data_script + """
        
        // Global variables
        let network;
        let allNodes = new vis.DataSet(utg_nodes);
        let allEdges = new vis.DataSet(utg_edges);
        let currentNodes = allNodes;
        let currentEdges = allEdges;
        
        // Initialize visualization
        function initNetwork() {
            const container = document.getElementById('network');
            const data = { nodes: currentNodes, edges: currentEdges };
            
            const options = {
                nodes: {
                    shape: 'image',
                    size: 50,
                    font: {
                        size: 12,
                        color: '#333'
                    },
                    borderWidth: 2,
                    borderWidthSelected: 4,
                    borderColor: '#2196F3',
                    borderColorSelected: '#FF9800'
                },
                edges: {
                    arrows: {
                        to: { enabled: true, scaleFactor: 0.8 }
                    },
                    color: {
                        color: '#848484',
                        highlight: '#FF9800'
                    },
                    font: {
                        size: 11,
                        color: '#666'
                    },
                    smooth: {
                        type: 'curvedCW',
                        roundness: 0.1
                    }
                },
                layout: {
                    improvedLayout: true
                },
                physics: {
                    enabled: true,
                    stabilization: { iterations: 100 }
                },
                interaction: {
                    hover: true,
                    tooltipDelay: 200
                }
            };
            
            network = new vis.Network(container, data, options);
            
            // Event handlers
            network.on("click", function(params) {
                handleNetworkClick(params);
            });
            
            network.on("hoverNode", function(params) {
                showTooltip(params.node);
            });
            
            network.on("hoverEdge", function(params) {
                showEdgeTooltip(params.edge);
            });
            
            // Update counts
            updateCounts();
            
            // Populate activity filter
            populateActivityFilter();
        }
        
        function handleNetworkClick(params) {
            if (params.nodes.length > 0) {
                const nodeId = params.nodes[0];
                showNodeDetails(nodeId);
            } else if (params.edges.length > 0) {
                const edgeId = params.edges[0];
                showEdgeDetails(edgeId);
            } else {
                clearSidebar();
            }
        }
        
        function showNodeDetails(nodeId) {
            const node = allNodes.get(nodeId);
            if (!node) return;
            
            const sidebar = document.getElementById('sidebar');
            sidebar.innerHTML = `
                <div class="sidebar-section">
                    <h3>Node Details</h3>
                    <div class="detail-item">
                        <span class="detail-label">ID:</span>
                        <span class="detail-value">${node.id || 'N/A'}</span>
                    </div>
                    <div class="detail-item">
                        <span class="detail-label">Step:</span>
                        <span class="detail-value">${node.step || 'N/A'}</span>
                    </div>
                    <div class="detail-item">
                        <span class="detail-label">Activity:</span>
                        <span class="detail-value">${node.activity || 'N/A'}</span>
                    </div>
                    <div class="detail-item">
                        <span class="detail-label">State ID:</span>
                        <span class="detail-value">${node.state_id || 'N/A'}</span>
                    </div>
                    <div class="detail-item">
                        <span class="detail-label">Tag:</span>
                        <span class="detail-value">${node.tag || 'N/A'}</span>
                    </div>
                    ${node.image ? `
                        <div class="screenshot-container">
                            <h4>Screenshot</h4>
                            <img src="${node.image}" alt="State Screenshot" onerror="this.style.display='none'; this.nextElementSibling.style.display='block';">
                            <div style="display:none; color: #999; font-style: italic;">Screenshot not available</div>
                        </div>
                    ` : ''}
                    <div class="action-buttons">
                        ${node.xml ? `<a href="${node.xml}" target="_blank" class="btn">View XML</a>` : ''}
                        <button class="btn" onclick="focusNode('${nodeId}')">Focus</button>
                        <button class="btn" onclick="highlightConnected('${nodeId}')">Show Connected</button>
                    </div>
                </div>
            `;
        }
        
        function showEdgeDetails(edgeId) {
            const edge = allEdges.get(edgeId);
            if (!edge) return;
            
            const sidebar = document.getElementById('sidebar');
            sidebar.innerHTML = `
                <div class="sidebar-section">
                    <h3>Edge Details</h3>
                    <div class="detail-item">
                        <span class="detail-label">ID:</span>
                        <span class="detail-value">${edge.id || 'N/A'}</span>
                    </div>
                    <div class="detail-item">
                        <span class="detail-label">Tag:</span>
                        <span class="detail-value">${edge.tag || 'N/A'}</span>
                    </div>
                    <div class="detail-item">
                        <span class="detail-label">Step:</span>
                        <span class="detail-value">${edge.step || 'N/A'}</span>
                    </div>
                    <div class="detail-item">
                        <span class="detail-label">From:</span>
                        <span class="detail-value">${edge.from || 'N/A'}</span>
                    </div>
                    <div class="detail-item">
                        <span class="detail-label">To:</span>
                        <span class="detail-value">${edge.to || 'N/A'}</span>
                    </div>
                    <div class="detail-item">
                        <span class="detail-label">Action:</span>
                        <span class="detail-value">${edge.raw_action || edge.action || 'N/A'}</span>
                    </div>
                    <div class="action-buttons">
                        <button class="btn" onclick="focusEdge('${edgeId}')">Focus</button>
                        <button class="btn" onclick="highlightEdgePath('${edgeId}')">Highlight Path</button>
                    </div>
                </div>
            `;
        }
        
        function clearSidebar() {
            const sidebar = document.getElementById('sidebar');
            sidebar.innerHTML = '<div class="no-selection">Click on a node or edge to view details</div>';
        }
        
        function fitNetwork() {
            if (network) {
                network.fit();
            }
        }
        
        function focusNode(nodeId) {
            if (network) {
                network.focus(nodeId, { scale: 1.5, animation: true });
            }
        }
        
        function focusEdge(edgeId) {
            const edge = allEdges.get(edgeId);
            if (edge && network) {
                network.focus(edge.from, { scale: 1.2, animation: true });
            }
        }
        
        function highlightConnected(nodeId) {
            const connectedEdges = allEdges.get().filter(edge => 
                edge.from === nodeId || edge.to === nodeId
            );
            const connectedNodes = new Set([nodeId]);
            
            connectedEdges.forEach(edge => {
                connectedNodes.add(edge.from);
                connectedNodes.add(edge.to);
            });
            
            network.selectNodes([...connectedNodes]);
            network.selectEdges(connectedEdges.map(e => e.id));
        }
        
        function highlightEdgePath(edgeId) {
            network.selectEdges([edgeId]);
            const edge = allEdges.get(edgeId);
            if (edge) {
                network.selectNodes([edge.from, edge.to]);
            }
        }
        
        function searchNodes() {
            const query = document.getElementById('searchInput').value.toLowerCase();
            if (!query) {
                network.selectNodes([]);
                return;
            }
            
            const matchingNodes = allNodes.get().filter(node => {
                return (
                    (node.step && node.step.toString().includes(query)) ||
                    (node.activity && node.activity.toLowerCase().includes(query)) ||
                    (node.state_id && node.state_id.toLowerCase().includes(query)) ||
                    (node.tag && node.tag.toLowerCase().includes(query)) ||
                    (node.id && node.id.toLowerCase().includes(query))
                );
            });
            
            network.selectNodes(matchingNodes.map(n => n.id));
            
            if (matchingNodes.length > 0) {
                network.focus(matchingNodes[0].id, { scale: 1.2, animation: true });
            }
        }
        
        function filterByActivity() {
            const selectedActivity = document.getElementById('filterSelect').value;
            
            if (!selectedActivity) {
                currentNodes = allNodes;
                currentEdges = allEdges;
            } else {
                const filteredNodes = allNodes.get().filter(node => 
                    node.activity === selectedActivity
                );
                const nodeIds = new Set(filteredNodes.map(n => n.id));
                
                const filteredEdges = allEdges.get().filter(edge =>
                    nodeIds.has(edge.from) && nodeIds.has(edge.to)
                );
                
                currentNodes = new vis.DataSet(filteredNodes);
                currentEdges = new vis.DataSet(filteredEdges);
            }
            
            network.setData({ nodes: currentNodes, edges: currentEdges });
            updateCounts();
        }
        
        function populateActivityFilter() {
            const select = document.getElementById('filterSelect');
            const activities = new Set();
            
            allNodes.get().forEach(node => {
                if (node.activity) {
                    activities.add(node.activity);
                }
            });
            
            [...activities].sort().forEach(activity => {
                const option = document.createElement('option');
                option.value = activity;
                option.textContent = activity.split('.').pop(); // Show just class name
                option.title = activity; // Full name in tooltip
                select.appendChild(option);
            });
        }
        
        function updateCounts() {
            document.getElementById('nodeCount').textContent = currentNodes.length;
            document.getElementById('edgeCount').textContent = currentEdges.length;
        }
        
        function showTooltip(nodeId) {
            // Tooltip is handled by vis-network automatically
        }
        
        function showEdgeTooltip(edgeId) {
            // Tooltip is handled by vis-network automatically
        }
        
        function togglePanel(type) {
            // Could implement expandable panels for node/edge lists
            console.log(`Toggle ${type} panel`);
        }
        
        // Initialize when page loads
        window.addEventListener('load', function() {
            initNetwork();
        });
    </script>
</body>
</html>"""
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    print(f"Generated HTML visualization at {output_path}")


class UTGHTTPServer:
    """Simple HTTP server for serving UTG visualization"""
    
    def __init__(self, port=8000, root_dir=None):
        self.port = port
        self.root_dir = Path(root_dir) if root_dir else Path.cwd()
        self.server = None
        self.server_thread = None
    
    def start_server(self):
        """Start HTTP server in a separate thread"""
        root_dir = self.root_dir  # Capture in closure
        
        class Handler(http.server.SimpleHTTPRequestHandler):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, directory=str(root_dir), **kwargs)
        
        try:
            self.server = socketserver.TCPServer(("", self.port), Handler)
            self.server_thread = threading.Thread(target=self.server.serve_forever)
            self.server_thread.daemon = True
            self.server_thread.start()
            
            print(f"HTTP server started on http://localhost:{self.port}")
            return True
        except Exception as e:
            print(f"Failed to start server on port {self.port}: {e}")
            return False
    
    def stop_server(self):
        """Stop the HTTP server"""
        if self.server:
            self.server.shutdown()
            self.server.server_close()
            print("HTTP server stopped")


def main():
    """Main function to generate UTG visualization and start server"""
    
    # Parse command line arguments
    output_dir = sys.argv[1] if len(sys.argv) > 1 else "1_exploration/output_test"
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 8000
    
    # Convert to absolute path
    output_path = Path(output_dir).resolve()
    project_root = Path(__file__).parent.parent
    
    print(f"UTG Visualization Generator")
    print(f"Output directory: {output_path}")
    print(f"Project root: {project_root}")
    
    # Check if output directory exists
    if not output_path.exists():
        print(f"Error: Output directory {output_path} does not exist")
        return 1
    
    try:
        # Load UTG data
        loader = UTGDataLoader(output_path)
        nodes, edges = loader.load_data()
        
        if not nodes:
            print("Warning: No nodes found in UTG data")
        
        # Generate HTML visualization in both visualize and output directories
        visualize_dir = project_root / "visualize"
        html_path_viz = visualize_dir / "utg_view.html"
        html_path_output = output_path / "utg_view.html"
        
        # Generate HTML for visualize directory (with embedded data)
        generate_html(nodes, edges, html_path_viz, use_external_js=False)
        
        # Generate HTML for output directory (uses external utg.js)
        generate_html([], [], html_path_output, use_external_js=True)
        
        print(f"Generated HTML files at:")
        print(f"  - {html_path_viz} (with embedded data)")
        print(f"  - {html_path_output} (uses external utg.js)")
        
        # Start HTTP server in output directory
        server = UTGHTTPServer(port, output_path)
        if not server.start_server():
            return 1
        
        # Open in browser (using the HTML file in output directory)
        url = f"http://localhost:{port}/utg_view.html"
        print(f"Opening browser at: {url}")
        
        time.sleep(1)  # Wait for server to fully start
        webbrowser.open(url)
        
        print("\nVisualization is now running!")
        print("- Use your browser to interact with the UTG")
        print("- Click nodes/edges to see details")
        print("- Use search and filter controls")
        print("- Press Ctrl+C to stop the server")
        
        try:
            # Keep server running until interrupted
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nShutting down...")
            server.stop_server()
            return 0
    
    except Exception as e:
        print(f"Error: {e}")
        return 1


if __name__ == "__main__":
    exit(main())