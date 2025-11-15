"""
UTG聚类结果可视化工具

基于Louvain聚类结果生成可交互的网页可视化界面，
展示不同聚类的状态节点和转换边。
"""

import json
import os
from pathlib import Path
from typing import Dict, List, Any, Set
from collections import defaultdict
import colorsys

class UTGClusterVisualizer:
    """
    UTG聚类结果可视化器
    
    生成基于vis.js的交互式网页可视化界面
    """
    
    def __init__(self, clustered_folder: str, original_folder: str = None):
        """
        初始化可视化器
        
        Args:
            clustered_folder: 聚类结果文件夹路径
            original_folder: 原始UTG文件夹路径（可选，用于获取更多状态信息）
        """
        self.clustered_folder = Path(clustered_folder)
        self.original_folder = Path(original_folder) if original_folder else None
        
        # 数据存储
        self.cluster_states: Dict[str, Dict[str, Any]] = {}  # state_str -> cluster_data
        self.cluster_events: List[Dict[str, Any]] = []  # 聚类事件列表
        self.original_states: Dict[str, Dict[str, Any]] = {}  # 原始状态数据
        
        # 聚类统计
        self.clusters: Dict[str, List[str]] = defaultdict(list)  # cluster_id -> [state_strs]
        self.cluster_colors: Dict[str, str] = {}  # cluster_id -> color
        
        # 验证输入路径
        self._validate_paths()
    
    def _validate_paths(self):
        """验证输入路径"""
        if not self.clustered_folder.exists():
            raise FileNotFoundError(f"聚类文件夹不存在: {self.clustered_folder}")
        
        states_folder = self.clustered_folder / "states"
        events_folder = self.clustered_folder / "events"
        
        if not states_folder.exists():
            raise FileNotFoundError(f"states文件夹不存在: {states_folder}")
        if not events_folder.exists():
            raise FileNotFoundError(f"events文件夹不存在: {events_folder}")
    
    def load_cluster_data(self):
        """加载聚类数据"""
        print("正在加载聚类数据...")
        
        # 加载聚类状态数据
        self._load_cluster_states()
        
        # 加载聚类事件数据
        self._load_cluster_events()
        
        # 加载原始状态数据（如果提供）
        if self.original_folder:
            self._load_original_states()
        
        # 生成聚类颜色
        self._generate_cluster_colors()
        
        print(f"数据加载完成: {len(self.cluster_states)} 个状态, "
              f"{len(self.cluster_events)} 个事件, "
              f"{len(self.clusters)} 个聚类")
    
    def _load_cluster_states(self):
        """加载聚类状态文件"""
        states_folder = self.clustered_folder / "states"
        state_files = list(states_folder.glob("state_*.json"))
        
        for state_file in state_files:
            try:
                with open(state_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    state_str = data.get("state_str")
                    cluster_id = data.get("state_cluster_id")
                    
                    if state_str and cluster_id:
                        self.cluster_states[state_str] = data
                        self.clusters[cluster_id].append(state_str)
                        
            except Exception as e:
                print(f"警告: 加载聚类状态文件失败 {state_file}: {e}")
    
    def _load_cluster_events(self):
        """加载聚类事件文件"""
        events_folder = self.clustered_folder / "events"
        event_files = list(events_folder.glob("event_*.json"))
        
        for event_file in event_files:
            try:
                with open(event_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    
                    # 验证必要字段
                    required_fields = ['start_state', 'stop_state', 'start_cluster', 'stop_cluster']
                    if all(field in data for field in required_fields):
                        # 只保留有效的边（两个状态都存在）
                        if (data['start_state'] in self.cluster_states and 
                            data['stop_state'] in self.cluster_states):
                            self.cluster_events.append(data)
                            
            except Exception as e:
                print(f"警告: 加载聚类事件文件失败 {event_file}: {e}")
    
    def _load_original_states(self):
        """加载原始状态数据（获取更多详细信息）"""
        if not self.original_folder:
            return
            
        original_states_folder = self.original_folder / "states"
        if not original_states_folder.exists():
            return
        
        state_files = list(original_states_folder.glob("state_*.json"))
        
        for state_file in state_files:
            try:
                with open(state_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    state_str = data.get("state_str")
                    
                    if state_str and state_str in self.cluster_states:
                        self.original_states[state_str] = data
                        
            except Exception as e:
                print(f"警告: 加载原始状态文件失败 {state_file}: {e}")
    
    def _generate_cluster_colors(self):
        """为每个聚类生成不同的颜色"""
        cluster_ids = list(self.clusters.keys())
        cluster_count = len(cluster_ids)
        
        if cluster_count == 0:
            return
        
        # 使用HSV颜色空间生成均匀分布的颜色
        for i, cluster_id in enumerate(cluster_ids):
            if cluster_id == "unknown_cluster":
                # unknown_cluster使用灰色
                self.cluster_colors[cluster_id] = "#999999"
            else:
                # 计算色调值，确保颜色分布均匀
                hue = i / cluster_count
                # 高饱和度和亮度，确保颜色鲜艳易区分
                saturation = 0.8
                value = 0.9
                
                # 转换为RGB
                rgb = colorsys.hsv_to_rgb(hue, saturation, value)
                # 转换为16进制颜色
                hex_color = "#{:02x}{:02x}{:02x}".format(
                    int(rgb[0] * 255),
                    int(rgb[1] * 255), 
                    int(rgb[2] * 255)
                )
                self.cluster_colors[cluster_id] = hex_color
    
    def generate_vis_data(self) -> Dict[str, Any]:
        """
        生成vis.js可视化所需的数据结构
        
        Returns:
            包含nodes和edges的字典
        """
        nodes = []
        edges = []
        
        # 生成节点数据
        for state_str, cluster_data in self.cluster_states.items():
            cluster_id = cluster_data.get("state_cluster_id", "unknown_cluster")
            color = self.cluster_colors.get(cluster_id, "#999999")
            
            # 获取原始状态的详细信息
            original_data = self.original_states.get(state_str, {})
            activity = original_data.get("foreground_activity", "Unknown")
            views_count = len(original_data.get("views", []))
            
            # 简化activity名称用于显示
            activity_name = activity.split('.')[-1] if activity else "Unknown"
            
            node = {
                "id": state_str,
                "label": f"{activity_name}\\n({views_count} views)",
                "color": {
                    "background": color,
                    "border": "#2B7CE9",
                    "highlight": {
                        "background": color,
                        "border": "#FF0000"
                    }
                },
                "title": self._generate_node_tooltip(state_str, cluster_id, original_data),
                "cluster_id": cluster_id,
                "activity": activity,
                "views_count": views_count,
                "font": {
                    "color": "#000000",
                    "size": 12
                },
                "size": max(15, min(30, views_count * 2))  # 根据视图数量调整节点大小
            }
            nodes.append(node)
        
        # 生成边数据
        edge_counts = defaultdict(int)  # 统计重复边的数量
        
        for event_data in self.cluster_events:
            start_state = event_data.get("start_state")
            stop_state = event_data.get("stop_state")
            start_cluster = event_data.get("start_cluster")
            stop_cluster = event_data.get("stop_cluster")
            
            if start_state and stop_state:
                edge_key = (start_state, stop_state)
                edge_counts[edge_key] += 1
        
        # 为每条唯一边创建边对象
        for (start_state, stop_state), count in edge_counts.items():
            # 查找对应的事件数据
            sample_event = None
            for event_data in self.cluster_events:
                if (event_data.get("start_state") == start_state and 
                    event_data.get("stop_state") == stop_state):
                    sample_event = event_data
                    break
            
            if sample_event:
                start_cluster = sample_event.get("start_cluster")
                stop_cluster = sample_event.get("stop_cluster")
                
                # 根据是否跨聚类设置不同的边样式
                if start_cluster == stop_cluster:
                    # 聚类内部的边
                    edge_color = self.cluster_colors.get(start_cluster, "#999999")
                    edge_width = min(8, 2 + count)
                    edge_style = "solid"
                else:
                    # 跨聚类的边
                    edge_color = "#FF6B6B"  # 红色表示跨聚类连接
                    edge_width = min(10, 3 + count)
                    edge_style = "dashed"
                
                edge = {
                    "from": start_state,
                    "to": stop_state,
                    "color": {
                        "color": edge_color,
                        "highlight": "#FF0000"
                    },
                    "width": edge_width,
                    "dashes": edge_style == "dashed",
                    "title": self._generate_edge_tooltip(sample_event, count),
                    "arrows": {
                        "to": {
                            "enabled": True,
                            "scaleFactor": 0.8
                        }
                    },
                    "count": count,
                    "start_cluster": start_cluster,
                    "stop_cluster": stop_cluster
                }
                edges.append(edge)
        
        return {
            "nodes": nodes,
            "edges": edges,
            "clusters": dict(self.clusters),
            "cluster_colors": self.cluster_colors
        }
    
    def _generate_node_tooltip(self, state_str: str, cluster_id: str, original_data: Dict[str, Any]) -> str:
        """生成节点悬停提示信息"""
        activity = original_data.get("foreground_activity", "Unknown")
        views_count = len(original_data.get("views", []))
        
        tooltip = f"""
        <b>State:</b> {state_str[:16]}...<br>
        <b>Cluster:</b> {cluster_id}<br>
        <b>Activity:</b> {activity}<br>
        <b>Views:</b> {views_count}
        """
        return tooltip.strip()
    
    def _generate_edge_tooltip(self, event_data: Dict[str, Any], count: int) -> str:
        """生成边悬停提示信息"""
        event_str = event_data.get("event_str", "Unknown event")
        start_cluster = event_data.get("start_cluster")
        stop_cluster = event_data.get("stop_cluster")
        
        # 简化事件描述
        if "TouchEvent" in event_str:
            event_type = "Touch"
        elif "KeyEvent" in event_str:
            event_type = "Key"
        elif "IntentEvent" in event_str:
            event_type = "Intent"
        else:
            event_type = "Unknown"
        
        cross_cluster = "Yes" if start_cluster != stop_cluster else "No"
        
        tooltip = f"""
        <b>Event Type:</b> {event_type}<br>
        <b>Count:</b> {count}<br>
        <b>Cross-cluster:</b> {cross_cluster}<br>
        <b>From:</b> {start_cluster}<br>
        <b>To:</b> {stop_cluster}
        """
        return tooltip.strip()
    
    def generate_html_visualization(self, output_file: str = "utg_cluster_visualization.html"):
        """
        生成HTML可视化文件
        
        Args:
            output_file: 输出HTML文件名
        """
        print("正在生成可视化数据...")
        vis_data = self.generate_vis_data()
        
        print("正在生成HTML文件...")
        html_template = self._get_html_template()
        
        # 将数据注入到HTML模板中
        html_content = html_template.format(
            vis_data_json=json.dumps(vis_data, indent=2, ensure_ascii=False),
            total_nodes=len(vis_data['nodes']),
            total_edges=len(vis_data['edges']),
            total_clusters=len(vis_data['clusters'])
        )
        
        # 写入文件
        output_path = Path(output_file)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        print(f"可视化文件已生成: {output_path.absolute()}")
        print(f"  - 节点数量: {len(vis_data['nodes'])}")
        print(f"  - 边数量: {len(vis_data['edges'])}")
        print(f"  - 聚类数量: {len(vis_data['clusters'])}")
        
        return str(output_path.absolute())
    
    def _get_html_template(self) -> str:
        """获取HTML模板"""
        return '''<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta http-equiv="X-UA-Compatible" content="IE=edge">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>UTG Cluster Visualization</title>
    
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <script src="https://unpkg.com/vis-network/standalone/umd/vis-network.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js"></script>
    
    <style>
        body {{
            font-family: Arial, sans-serif;
            margin: 0;
            padding: 0;
        }}
        
        .navbar {{
            background-color: #2c3e50 !important;
        }}
        
        .navbar-brand {{
            color: white !important;
            font-weight: bold;
        }}
        
        .navbar-nav .nav-link {{
            color: #ecf0f1 !important;
        }}
        
        .navbar-nav .nav-link:hover {{
            color: #3498db !important;
        }}
        
        #network-container {{
            width: 100%;
            height: calc(100vh - 120px);
            border: 1px solid #ddd;
            border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }}
        
        .stats-card {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border-radius: 10px;
            padding: 15px;
            margin-bottom: 15px;
            box-shadow: 0 4px 15px rgba(0,0,0,0.1);
        }}
        
        .cluster-legend {{
            max-height: 400px;
            overflow-y: auto;
            border: 1px solid #ddd;
            border-radius: 8px;
            padding: 15px;
            background-color: #f8f9fa;
        }}
        
        .cluster-item {{
            display: flex;
            align-items: center;
            margin-bottom: 8px;
            padding: 5px;
            border-radius: 5px;
            background-color: white;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        }}
        
        .cluster-color {{
            width: 20px;
            height: 20px;
            border-radius: 50%;
            margin-right: 10px;
            border: 2px solid #333;
        }}
        
        .cluster-info {{
            flex-grow: 1;
        }}
        
        .cluster-name {{
            font-weight: bold;
            font-size: 14px;
        }}
        
        .cluster-count {{
            font-size: 12px;
            color: #666;
        }}
        
        .control-panel {{
            background-color: #f8f9fa;
            border-radius: 8px;
            padding: 15px;
            margin-bottom: 15px;
        }}
        
        .btn-custom {{
            background-color: #3498db;
            border-color: #3498db;
            color: white;
            margin: 2px;
        }}
        
        .btn-custom:hover {{
            background-color: #2980b9;
            border-color: #2980b9;
            color: white;
        }}
        
        #searchBox {{
            width: 100%;
            padding: 8px;
            border: 1px solid #ddd;
            border-radius: 4px;
            margin-bottom: 10px;
        }}
    </style>
</head>

<body>
    <!-- Navigation -->
    <nav class="navbar navbar-expand-lg navbar-dark">
        <div class="container-fluid">
            <a class="navbar-brand" href="#">🎯 UTG Cluster Visualization</a>
            <button class="navbar-toggler" type="button" data-bs-toggle="collapse" data-bs-target="#navbarNav">
                <span class="navbar-toggler-icon"></span>
            </button>
            <div class="collapse navbar-collapse" id="navbarNav">
                <ul class="navbar-nav ms-auto">
                    <li class="nav-item">
                        <a class="nav-link" href="#" onclick="resetView()">🏠 Reset View</a>
                    </li>
                    <li class="nav-item">
                        <a class="nav-link" href="#" onclick="fitNetwork()">🔍 Fit Network</a>
                    </li>
                    <li class="nav-item">
                        <a class="nav-link" href="#" onclick="togglePhysics()">⚡ Toggle Physics</a>
                    </li>
                </ul>
            </div>
        </div>
    </nav>

    <!-- Main Content -->
    <div class="container-fluid mt-3">
        <div class="row">
            <!-- Network Visualization -->
            <div class="col-lg-8">
                <!-- Statistics -->
                <div class="stats-card">
                    <div class="row text-center">
                        <div class="col-md-4">
                            <h3 id="nodeCount">{total_nodes}</h3>
                            <p>States</p>
                        </div>
                        <div class="col-md-4">
                            <h3 id="edgeCount">{total_edges}</h3>
                            <p>Transitions</p>
                        </div>
                        <div class="col-md-4">
                            <h3 id="clusterCount">{total_clusters}</h3>
                            <p>Clusters</p>
                        </div>
                    </div>
                </div>
                
                <!-- Network Container -->
                <div id="network-container"></div>
            </div>
            
            <!-- Control Panel -->
            <div class="col-lg-4">
                <!-- Search and Filters -->
                <div class="control-panel">
                    <h5>🔍 Search & Filter</h5>
                    <input type="text" id="searchBox" placeholder="Search states..." onkeyup="searchStates()">
                    
                    <div class="d-grid gap-2">
                        <button class="btn btn-custom btn-sm" onclick="showAllNodes()">Show All</button>
                        <button class="btn btn-custom btn-sm" onclick="hideIsolatedNodes()">Hide Isolated</button>
                        <button class="btn btn-custom btn-sm" onclick="highlightCrossClusters()">Highlight Cross-cluster</button>
                    </div>
                </div>
                
                <!-- Cluster Legend -->
                <div class="cluster-legend">
                    <h5>📊 Cluster Legend</h5>
                    <div id="clusterLegend"></div>
                </div>
                
                <!-- Selected Node Info -->
                <div class="control-panel">
                    <h5>ℹ️ Selected Node</h5>
                    <div id="nodeInfo">
                        <p class="text-muted">Click on a node to see details</p>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <script>
        // Global variables
        let network;
        let nodes, edges;
        let allNodes, allEdges;
        let physicsEnabled = true;
        
        // Visualization data
        const visData = {vis_data_json};
        
        // Initialize the network
        function initNetwork() {{
            const container = document.getElementById('network-container');
            
            // Prepare data
            allNodes = new vis.DataSet(visData.nodes);
            allEdges = new vis.DataSet(visData.edges);
            
            nodes = allNodes;
            edges = allEdges;
            
            const data = {{
                nodes: nodes,
                edges: edges
            }};
            
            // Network options
            const options = {{
                nodes: {{
                    shape: 'dot',
                    scaling: {{
                        min: 10,
                        max: 30
                    }},
                    font: {{
                        size: 12,
                        face: 'Arial'
                    }},
                    borderWidth: 2,
                    shadow: true
                }},
                edges: {{
                    width: 2,
                    color: {{
                        inherit: 'from'
                    }},
                    smooth: {{
                        type: 'continuous'
                    }},
                    arrows: {{
                        to: {{
                            enabled: true,
                            scaleFactor: 0.8
                        }}
                    }}
                }},
                physics: {{
                    enabled: true,
                    stabilization: {{
                        iterations: 200
                    }},
                    barnesHut: {{
                        gravitationalConstant: -8000,
                        springConstant: 0.001,
                        springLength: 200
                    }}
                }},
                interaction: {{
                    hover: true,
                    selectConnectedEdges: false
                }},
                layout: {{
                    improvedLayout: false
                }}
            }};
            
            // Create network
            network = new vis.Network(container, data, options);
            
            // Event listeners
            network.on('select', onNodeSelect);
            network.on('hoverNode', onNodeHover);
            
            // Generate cluster legend
            generateClusterLegend();
            
            console.log('Network initialized with', visData.nodes.length, 'nodes and', visData.edges.length, 'edges');
        }}
        
        // Event handlers
        function onNodeSelect(params) {{
            if (params.nodes.length > 0) {{
                const nodeId = params.nodes[0];
                const nodeData = allNodes.get(nodeId);
                showNodeInfo(nodeData);
            }} else {{
                clearNodeInfo();
            }}
        }}
        
        function onNodeHover(params) {{
            // Optional: Add hover effects
        }}
        
        function showNodeInfo(nodeData) {{
            const infoDiv = document.getElementById('nodeInfo');
            infoDiv.innerHTML = `
                <h6>${{nodeData.label}}</h6>
                <p><strong>ID:</strong> ${{nodeData.id.substring(0, 16)}}...</p>
                <p><strong>Cluster:</strong> ${{nodeData.cluster_id}}</p>
                <p><strong>Activity:</strong> ${{nodeData.activity.split('.').pop()}}</p>
                <p><strong>Views:</strong> ${{nodeData.views_count}}</p>
            `;
        }}
        
        function clearNodeInfo() {{
            const infoDiv = document.getElementById('nodeInfo');
            infoDiv.innerHTML = '<p class="text-muted">Click on a node to see details</p>';
        }}
        
        function generateClusterLegend() {{
            const legendDiv = document.getElementById('clusterLegend');
            let legendHTML = '';
            
            const sortedClusters = Object.entries(visData.clusters)
                .sort((a, b) => b[1].length - a[1].length); // Sort by size
            
            sortedClusters.forEach(([clusterId, states]) => {{
                const color = visData.cluster_colors[clusterId] || '#999999';
                legendHTML += `
                    <div class="cluster-item" onclick="focusCluster('${{clusterId}}')">
                        <div class="cluster-color" style="background-color: ${{color}};"></div>
                        <div class="cluster-info">
                            <div class="cluster-name">${{clusterId}}</div>
                            <div class="cluster-count">${{states.length}} states</div>
                        </div>
                    </div>
                `;
            }});
            
            legendDiv.innerHTML = legendHTML;
        }}
        
        // Network control functions
        function resetView() {{
            network.fit();
            showAllNodes();
        }}
        
        function fitNetwork() {{
            network.fit();
        }}
        
        function togglePhysics() {{
            physicsEnabled = !physicsEnabled;
            network.setOptions({{ physics: physicsEnabled }});
        }}
        
        function showAllNodes() {{
            nodes.update(allNodes.get());
            edges.update(allEdges.get());
        }}
        
        function hideIsolatedNodes() {{
            const connectedNodes = new Set();
            allEdges.forEach(edge => {{
                connectedNodes.add(edge.from);
                connectedNodes.add(edge.to);
            }});
            
            const filteredNodes = allNodes.get().filter(node => 
                connectedNodes.has(node.id)
            );
            
            nodes.update(filteredNodes);
        }}
        
        function highlightCrossClusters() {{
            const crossClusterEdges = allEdges.get().filter(edge => 
                edge.start_cluster !== edge.stop_cluster
            );
            
            edges.update(crossClusterEdges);
        }}
        
        function focusCluster(clusterId) {{
            const clusterStates = visData.clusters[clusterId] || [];
            const clusterNodes = allNodes.get().filter(node => 
                clusterStates.includes(node.id)
            );
            
            const clusterEdges = allEdges.get().filter(edge => 
                clusterStates.includes(edge.from) && clusterStates.includes(edge.to)
            );
            
            nodes.update(clusterNodes);
            edges.update(clusterEdges);
            
            if (clusterNodes.length > 0) {{
                network.fit({{
                    nodes: clusterNodes.map(n => n.id)
                }});
            }}
        }}
        
        function searchStates() {{
            const query = document.getElementById('searchBox').value.toLowerCase();
            
            if (query === '') {{
                showAllNodes();
                return;
            }}
            
            const filteredNodes = allNodes.get().filter(node => 
                node.label.toLowerCase().includes(query) ||
                node.id.toLowerCase().includes(query) ||
                node.activity.toLowerCase().includes(query) ||
                node.cluster_id.toLowerCase().includes(query)
            );
            
            const filteredNodeIds = filteredNodes.map(n => n.id);
            const filteredEdges = allEdges.get().filter(edge => 
                filteredNodeIds.includes(edge.from) && 
                filteredNodeIds.includes(edge.to)
            );
            
            nodes.update(filteredNodes);
            edges.update(filteredEdges);
        }}
        
        // Initialize when page loads
        document.addEventListener('DOMContentLoaded', function() {{
            initNetwork();
        }});
    </script>
</body>
</html>'''
    
    def generate_cluster_statistics(self) -> Dict[str, Any]:
        """生成聚类统计信息"""
        stats = {
            'total_states': len(self.cluster_states),
            'total_events': len(self.cluster_events),
            'total_clusters': len(self.clusters),
            'clusters': {}
        }
        
        # 计算每个聚类的统计信息
        for cluster_id, states in self.clusters.items():
            cluster_events = [e for e in self.cluster_events 
                            if e.get('start_cluster') == cluster_id or e.get('stop_cluster') == cluster_id]
            
            internal_events = [e for e in cluster_events 
                             if e.get('start_cluster') == cluster_id and e.get('stop_cluster') == cluster_id]
            
            stats['clusters'][cluster_id] = {
                'state_count': len(states),
                'total_events': len(cluster_events),
                'internal_events': len(internal_events),
                'external_events': len(cluster_events) - len(internal_events),
                'color': self.cluster_colors.get(cluster_id, '#999999')
            }
        
        return stats


def main():
    """主函数：生成UTG聚类可视化"""
    # 设置路径
    clustered_folder = r"c:\Projects\AndroidTaskAutomation\2_utg_clustering\utg\original_greedy_dfs_20251106_160351_louvain_clustered"
    original_folder = r"c:\Projects\AndroidTaskAutomation\2_utg_clustering\utg\original_greedy_dfs_20251106_160351"
    
    # 创建可视化器
    visualizer = UTGClusterVisualizer(clustered_folder, original_folder)
    
    # 加载数据
    visualizer.load_cluster_data()
    
    # 生成可视化
    html_file = visualizer.generate_html_visualization("utg_cluster_visualization.html")
    
    # 生成统计信息
    stats = visualizer.generate_cluster_statistics()
    
    print(f"\n=== 聚类可视化统计 ===")
    print(f"总状态数: {stats['total_states']}")
    print(f"总转换数: {stats['total_events']}")
    print(f"聚类数量: {stats['total_clusters']}")
    
    print(f"\n前5个最大的聚类:")
    sorted_clusters = sorted(stats['clusters'].items(), 
                           key=lambda x: x[1]['state_count'], reverse=True)
    
    for i, (cluster_id, cluster_stats) in enumerate(sorted_clusters[:5]):
        print(f"  {i+1}. {cluster_id}: {cluster_stats['state_count']} 个状态, "
              f"{cluster_stats['internal_events']} 个内部转换")
    
    print(f"\n可视化文件已生成: {html_file}")
    print("在浏览器中打开HTML文件即可查看交互式可视化界面")


if __name__ == "__main__":
    main()