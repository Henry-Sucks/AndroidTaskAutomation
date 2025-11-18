// Clustered UI JavaScript for Enhanced UTG Visualization
// Extends the original droidbotUI.js functionality with clustering features

var network = null;
var currentView = 'clustered';
var selectedCluster = null;

function draw() {
  var utg_div = document.getElementById('utg_div');
  var utg_details = document.getElementById('utg_details');

  // Initialize with clustered view
  currentView = 'clustered';

  // Create virtual center nodes for each cluster
  var clusterCenters = [];
  var clusterConnections = [];
  var allClusterIds = [...new Set(nodes.map(node => node.cluster_id))];
  
  allClusterIds.forEach(clusterId => {
    var centerId = 'center_' + clusterId;
    clusterCenters.push({
      id: centerId,
      label: '',
      shape: 'dot',
      size: 1,
      color: {
        background: clusterColors[clusterId] || '#2B7CE9',
        border: clusterColors[clusterId] || '#2B7CE9'
      },
      physics: true,
      hidden: true  // 虚拟节点不可见
    });
    
    // Connect all nodes in this cluster to the center
    nodes.filter(node => node.cluster_id === clusterId).forEach(node => {
      clusterConnections.push({
        from: node.id,
        to: centerId,
        length: 50,  // 短连接长度
        color: { opacity: 0 },  // 不可见连接
        physics: true,
        smooth: false
      });
    });
  });

  var options = {
    autoResize: true,
    height: '100%',
    width: '100%',
    locale: 'en',

    nodes: {
      shape: 'image',
      shapeProperties: {
        useBorderWithImage: true
      },
      borderWidth: 4,
      borderWidthSelected: 6,
      size: 40,
      imagePadding: {
        left: 2,
        top: 2,
        right: 2,
        bottom: 2
      },
      font: {
        size: 10,
        color: '#000'
      }
    },
    edges: {
      color: '#666666',
      arrows: {
        to: {
          enabled: true,
          scaleFactor: 0.5
        }
      },
      font: {
        size: 10,
        color: '#000'
      },
      smooth: {
        type: 'curvedCW',
        roundness: 0.1
      }
    },
    physics: {
      enabled: true,
      stabilization: { iterations: 200 },
      barnesHut: {
        gravitationalConstant: -15000,  // 增强节点间排斥力
        centralGravity: 0.05,           // 轻微中心重力
        springLength: 200,              // 默认边长度
        springConstant: 0.0003,         // 弱化普通边的弹簧力
        damping: 0.95                   // 增强阻尼
      }
    },
    interaction: {
      hover: true,
      tooltipDelay: 300
    }
  };

  // Apply cluster colors to nodes at startup
  var clusteredNodes = nodes.map(node => {
    var clusterColor = clusterColors[node.cluster_id] || '#2B7CE9';
    return {
      ...node,
      color: {
        border: clusterColor,
        highlight: {
          border: clusterColor
        }
      },
      borderWidth: 4
    };
  });

  // Combine all nodes (real + virtual centers)
  var allNodes = [...clusteredNodes, ...clusterCenters];
  
  // Combine all edges (original + cluster connections)
  var allEdges = [...edges, ...clusterConnections];

  network = new vis.Network(utg_div, { nodes: allNodes, edges: allEdges }, options);
  
  // Update details panel
  utg_details.innerHTML = getClusteredUTGInfo();

  network.on("click", function (params) {
    if (params.nodes.length > 0) {
      var nodeId = params.nodes[0];
      utg_details.innerHTML = getNodeDetails(nodeId);
    } else if (params.edges.length > 0) {
      var edgeId = params.edges[0];
      utg_details.innerHTML = getEdgeDetails(edgeId);
    }
  });

  network.on("hoverNode", function (params) {
    var nodeId = params.node;
    var node = nodes.find(n => n.id === nodeId);
    if (node && node.cluster_id) {
      highlightCluster(node.cluster_id);
    }
  });

  network.on("blurNode", function (params) {
    clearClusterHighlight();
  });
}

function showOverall() {
  currentView = 'overall';
  var utg_details = document.getElementById('utg_details');
  utg_details.innerHTML = getOverallResult();
}

function showOriginalUTG() {
  currentView = 'original';
  if (network) {
    // Reset all nodes to uniform border colors while keeping screenshots
    var updatedNodes = nodes.map(node => ({
      ...node,
      color: {
        border: '#2B7CE9',
        highlight: {
          border: '#2B7CE9'
        }
      },
      borderWidth: 2
    }));
    // Use only original edges, no cluster connections
    network.setData({ nodes: updatedNodes, edges: edges });
  }
  document.getElementById('utg_details').innerHTML = getOriginalUTGInfo();
}

function showClusteredUTG() {
  currentView = 'clustered';
  if (network) {
    // Recreate cluster centers and connections
    var clusterCenters = [];
    var clusterConnections = [];
    var allClusterIds = [...new Set(nodes.map(node => node.cluster_id))];
    
    allClusterIds.forEach(clusterId => {
      var centerId = 'center_' + clusterId;
      clusterCenters.push({
        id: centerId,
        label: '',
        shape: 'dot',
        size: 1,
        color: {
          background: clusterColors[clusterId] || '#2B7CE9',
          border: clusterColors[clusterId] || '#2B7CE9'
        },
        physics: true,
        hidden: true
      });
      
      nodes.filter(node => node.cluster_id === clusterId).forEach(node => {
        clusterConnections.push({
          from: node.id,
          to: centerId,
          length: 50,
          color: { opacity: 0 },
          physics: true,
          smooth: false
        });
      });
    });
    
    // Apply cluster colors to node borders
    var clusteredNodes = nodes.map(node => {
      var clusterColor = clusterColors[node.cluster_id] || '#2B7CE9';
      return {
        ...node,
        color: {
          border: clusterColor,
          highlight: {
            border: clusterColor
          }
        },
        borderWidth: 4
      };
    });
    
    var allNodes = [...clusteredNodes, ...clusterCenters];
    var allEdges = [...edges, ...clusterConnections];
    
    network.setData({ nodes: allNodes, edges: allEdges });
  }
  document.getElementById('utg_details').innerHTML = getClusteredUTGInfo();
}

function showClusterStatistics() {
  currentView = 'statistics';
  document.getElementById('utg_details').innerHTML = getClusterStatistics();
}

function showAbout() {
  currentView = 'about';
  document.getElementById('utg_details').innerHTML = getAboutInfo();
}

function getOverallResult() {
  var overallInfo = "<div class='cluster-stats'>";
  overallInfo += "<h4><i class='glyphicon glyphicon-stats'></i> Clustering Statistics</h4>";
  overallInfo += "<p><strong>Total Communities:</strong> " + clusteringStats.num_communities + "</p>";
  overallInfo += "<p><strong>Modularity Score:</strong> " + clusteringStats.final_modularity.toFixed(3) + "</p>";
  overallInfo += "<p><strong>Largest Cluster:</strong> " + clusteringStats.largest_community_size + " states</p>";
  overallInfo += "</div>";

  overallInfo += "<hr />";
  overallInfo += "<table class=\"table\">";

  overallInfo += "<tr class=\"active\"><th colspan=\"2\"><h4>App Information</h4></th></tr>";
  overallInfo += "<tr><th>Package</th><td>" + utg.app_package + "</td></tr>";
  overallInfo += "<tr><th>SHA-256</th><td>" + utg.app_sha256 + "</td></tr>";
  overallInfo += "<tr><th>Main Activity</th><td>" + utg.app_main_activity + "</td></tr>";
  overallInfo += "<tr><th># Activities</th><td>" + utg.app_num_total_activities + "</td></tr>";

  overallInfo += "<tr class=\"active\"><th colspan=\"2\"><h4>Device Information</h4></th></tr>";
  overallInfo += "<tr><th>Device Serial</th><td>" + utg.device_serial + "</td></tr>";
  overallInfo += "<tr><th>Model Number</th><td>" + utg.device_model_number + "</td></tr>";
  overallInfo += "<tr><th>SDK Version</th><td>" + utg.device_sdk_version + "</td></tr>";

  overallInfo += "<tr class=\"active\"><th colspan=\"2\"><h4>DroidBot Result</h4></th></tr>";
  overallInfo += "<tr><th>Test Date</th><td>" + utg.test_date + "</td></tr>";
  overallInfo += "<tr><th>Time Spent (s)</th><td>" + utg.time_spent + "</td></tr>";
  overallInfo += "<tr><th># Input Events</th><td>" + utg.num_input_events + "</td></tr>";
  overallInfo += "<tr><th># UTG States</th><td>" + utg.num_nodes + "</td></tr>";
  overallInfo += "<tr><th># Transitions</th><td>" + utg.num_edges + "</td></tr>";

  overallInfo += "</table>";
  return overallInfo;
}

function getClusteredUTGInfo() {
  var info = "<div class='cluster-info'>";
  info += "<h4><i class='glyphicon glyphicon-th'></i> Clustered UTG View</h4>";
  info += "<p>States are grouped into <strong>" + clusteringStats.num_communities + " clusters</strong> using Louvain community detection.</p>";
  info += "</div>";

  // Cluster legend
  info += "<div class='cluster-legend'>";
  info += "<h5>Cluster Legend:</h5>";
  var sortedClusters = Object.keys(clusteringStats.community_sizes).sort((a, b) => 
    clusteringStats.community_sizes[b] - clusteringStats.community_sizes[a]
  );
  
  sortedClusters.forEach(clusterId => {
    var size = clusteringStats.community_sizes[clusterId];
    var color = clusterColors[clusterId];
    info += "<div class='cluster-item' onclick='filterByCluster(\"" + clusterId + "\")'>";
    info += "<div class='cluster-color' style='background-color: " + color + "'></div>";
    info += "Cluster " + clusterId + " (" + size + " states)";
    info += "</div>";
  });
  info += "</div>";

  info += "<div class='cluster-filter'>";
  info += "<button class='btn btn-primary btn-sm' onclick='showAllClusters()'>Show All</button> ";
  info += "<button class='btn btn-info btn-sm' onclick='showLargeClusters()'>Large Clusters (>20)</button> ";
  info += "<button class='btn btn-warning btn-sm' onclick='showSmallClusters()'>Small Clusters (<5)</button>";
  info += "</div>";

  info += "<p><small>Click on nodes to see state details. Hover over nodes to highlight cluster members.</small></p>";

  return info;
}

function getOriginalUTGInfo() {
  return "<h4>Original UTG View</h4><p>All states shown without clustering. Node colors are reset to default.</p>";
}

function getClusterStatistics() {
  var stats = "<div class='cluster-stats'>";
  stats += "<h4><i class='glyphicon glyphicon-signal'></i> Detailed Cluster Statistics</h4>";
  
  stats += "<table class='table table-striped'>";
  stats += "<tr><th>Metric</th><th>Value</th></tr>";
  stats += "<tr><td>Total States</td><td>" + clusteringStats.total_states + "</td></tr>";
  stats += "<tr><td>Total Transitions</td><td>" + clusteringStats.total_transitions + "</td></tr>";
  stats += "<tr><td>Communities Found</td><td>" + clusteringStats.num_communities + "</td></tr>";
  stats += "<tr><td>Modularity Score</td><td>" + clusteringStats.final_modularity.toFixed(4) + "</td></tr>";
  stats += "<tr><td>Largest Cluster Size</td><td>" + clusteringStats.largest_community_size + " states</td></tr>";
  stats += "<tr><td>Smallest Cluster Size</td><td>" + clusteringStats.smallest_community_size + " states</td></tr>";
  stats += "<tr><td>Average Cluster Size</td><td>" + clusteringStats.average_community_size.toFixed(2) + " states</td></tr>";
  stats += "<tr><td>Screenshot Coverage</td><td>" + (clusteringStats.screenshot_coverage_rate * 100).toFixed(1) + "%</td></tr>";
  stats += "</table>";
  stats += "</div>";

  // Cluster size distribution
  stats += "<h5>Cluster Size Distribution</h5>";
  stats += "<table class='table table-condensed'>";
  stats += "<tr><th>Cluster ID</th><th>Size</th><th>Color</th><th>Actions</th></tr>";
  
  var sortedClusters = Object.keys(clusteringStats.community_sizes).sort((a, b) => 
    clusteringStats.community_sizes[b] - clusteringStats.community_sizes[a]
  );
  
  sortedClusters.forEach(clusterId => {
    var size = clusteringStats.community_sizes[clusterId];
    var color = clusterColors[clusterId];
    stats += "<tr>";
    stats += "<td>Cluster " + clusterId + "</td>";
    stats += "<td>" + size + " states</td>";
    stats += "<td><div class='cluster-color' style='background-color: " + color + "'></div></td>";
    stats += "<td><button class='btn btn-xs btn-primary' onclick='focusOnCluster(\"" + clusterId + "\")'>Focus</button></td>";
    stats += "</tr>";
  });
  stats += "</table>";

  return stats;
}

function getNodeDetails(nodeId) {
  var node = nodes.find(n => n.id === nodeId);
  if (!node) return "<p>Node not found.</p>";

  var details = "<div class='cluster-info'>";
  details += "<h4><i class='glyphicon glyphicon-screenshot'></i> State Details</h4>";
  details += "<p><strong>State ID:</strong> " + nodeId + "</p>";
  details += "<p><strong>Cluster:</strong> " + node.cluster_id + " (" + clusteringStats.community_sizes[node.cluster_id] + " states)</p>";
  
  if (node.image) {
    details += "<p><strong>Screenshot:</strong></p>";
    details += "<img src='" + node.image + "' class='state-screenshot' onclick='openScreenshotModal(\"" + node.image + "\")' />";
  }
  details += "</div>";

  // Find connected states in same cluster
  var clusterStates = nodes.filter(n => n.cluster_id === node.cluster_id);
  if (clusterStates.length > 1) {
    details += "<h5>Other States in Cluster " + node.cluster_id + ":</h5>";
    details += "<div class='row'>";
    clusterStates.slice(0, 6).forEach(state => {
      if (state.id !== nodeId) {
        details += "<div class='col-md-4'>";
        details += "<img src='" + state.image + "' class='img-thumbnail' style='width:60px;height:80px;cursor:pointer;' onclick='focusOnState(\"" + state.id + "\")' title='State " + state.id + "' />";
        details += "</div>";
      }
    });
    if (clusterStates.length > 7) {
      details += "<p><small>... and " + (clusterStates.length - 7) + " more states</small></p>";
    }
    details += "</div>";
  }

  return details;
}

function getEdgeDetails(edgeId) {
  var edge = edges.find(e => e.id === edgeId || (e.from + "_" + e.to) === edgeId);
  if (!edge) return "<p>Edge not found.</p>";

  var details = "<h4><i class='glyphicon glyphicon-arrow-right'></i> Transition Details</h4>";
  details += "<p><strong>From:</strong> " + edge.from + "</p>";
  details += "<p><strong>To:</strong> " + edge.to + "</p>";
  if (edge.event_str) {
    details += "<p><strong>Event:</strong> " + edge.event_str + "</p>";
  }

  return details;
}

function getAboutInfo() {
  return "<h4>About Clustered UTG</h4>" +
         "<p>This is an enhanced visualization of the UI Transition Graph (UTG) with clustering capabilities.</p>" +
         "<p><strong>Clustering Algorithm:</strong> Louvain Community Detection</p>" +
         "<p><strong>Generated:</strong> " + new Date().toLocaleDateString() + "</p>" +
         "<p><strong>Features:</strong></p>" +
         "<ul>" +
         "<li>Interactive cluster visualization</li>" +
         "<li>Screenshot integration</li>" +
         "<li>Cluster-based filtering</li>" +
         "<li>Statistical analysis</li>" +
         "</ul>";
}

// Cluster interaction functions
function filterByCluster(clusterId) {
  selectedCluster = clusterId;
  var clusterNodes = nodes.filter(node => node.cluster_id === clusterId);
  var clusterNodeIds = clusterNodes.map(node => node.id);
  
  // Create virtual center for the filtered cluster
  var centerId = 'center_' + clusterId;
  var clusterCenter = {
    id: centerId,
    label: '',
    shape: 'dot',
    size: 1,
    color: {
      background: clusterColors[clusterId] || '#2B7CE9',
      border: clusterColors[clusterId] || '#2B7CE9'
    },
    physics: true,
    hidden: true
  };
  
  // Apply cluster colors to filtered nodes
  var coloredClusterNodes = clusterNodes.map(node => {
    var clusterColor = clusterColors[node.cluster_id] || '#2B7CE9';
    return {
      ...node,
      color: {
        border: clusterColor,
        highlight: {
          border: clusterColor
        }
      },
      borderWidth: 4
    };
  });
  
  // Create cluster connections for filtered nodes
  var clusterConnections = clusterNodes.map(node => ({
    from: node.id,
    to: centerId,
    length: 50,
    color: { opacity: 0 },
    physics: true,
    smooth: false
  }));
  
  // Filter edges to show only those within or connected to the cluster
  var clusterEdges = edges.filter(edge => 
    clusterNodeIds.includes(edge.from) || clusterNodeIds.includes(edge.to)
  );
  
  // Combine all nodes and edges
  var allNodes = [...coloredClusterNodes, clusterCenter];
  var allEdges = [...clusterEdges, ...clusterConnections];

  network.setData({ nodes: allNodes, edges: allEdges });
  network.fit();
  
  document.getElementById('utg_details').innerHTML = getClusterDetails(clusterId);
}

function getClusterDetails(clusterId) {
  var clusterNodes = nodes.filter(n => n.cluster_id === clusterId);
  var clusterSize = clusteringStats.community_sizes[clusterId];
  var clusterColor = clusterColors[clusterId];

  var details = "<div class='cluster-info'>";
  details += "<h4 style='color: " + clusterColor + "'><i class='glyphicon glyphicon-th-large'></i> Cluster " + clusterId + " Details</h4>";
  details += "<p><strong>Size:</strong> " + clusterSize + " states</p>";
  details += "<p><strong>Color:</strong> <span class='cluster-color' style='background-color: " + clusterColor + "'></span> " + clusterColor + "</p>";
  details += "</div>";

  details += "<h5>States in this Cluster:</h5>";
  details += "<div class='row'>";
  clusterNodes.slice(0, 12).forEach((node, index) => {
    details += "<div class='col-md-3' style='margin-bottom: 10px;'>";
    details += "<img src='" + node.image + "' class='img-thumbnail' style='width:50px;height:70px;cursor:pointer;' onclick='focusOnState(\"" + node.id + "\")' title='" + node.id + "' />";
    details += "</div>";
  });
  details += "</div>";

  if (clusterNodes.length > 12) {
    details += "<p><small>Showing first 12 of " + clusterNodes.length + " states</small></p>";
  }

  details += "<button class='btn btn-primary btn-sm' onclick='showAllClusters()'>Show All Clusters</button>";

  return details;
}

function showAllClusters() {
  selectedCluster = null;
  
  // Recreate all cluster centers and connections
  var clusterCenters = [];
  var clusterConnections = [];
  var allClusterIds = [...new Set(nodes.map(node => node.cluster_id))];
  
  allClusterIds.forEach(clusterId => {
    var centerId = 'center_' + clusterId;
    clusterCenters.push({
      id: centerId,
      label: '',
      shape: 'dot',
      size: 1,
      color: {
        background: clusterColors[clusterId] || '#2B7CE9',
        border: clusterColors[clusterId] || '#2B7CE9'
      },
      physics: true,
      hidden: true
    });
    
    nodes.filter(node => node.cluster_id === clusterId).forEach(node => {
      clusterConnections.push({
        from: node.id,
        to: centerId,
        length: 50,
        color: { opacity: 0 },
        physics: true,
        smooth: false
      });
    });
  });
  
  // Apply cluster colors to all nodes
  var clusteredNodes = nodes.map(node => {
    var clusterColor = clusterColors[node.cluster_id] || '#2B7CE9';
    return {
      ...node,
      color: {
        border: clusterColor,
        highlight: {
          border: clusterColor
        }
      },
      borderWidth: 4
    };
  });
  
  var allNodes = [...clusteredNodes, ...clusterCenters];
  var allEdges = [...edges, ...clusterConnections];
  
  network.setData({ nodes: allNodes, edges: allEdges });
  network.fit();
  document.getElementById('utg_details').innerHTML = getClusteredUTGInfo();
}

function showLargeClusters() {
  var largeClusterIds = Object.keys(clusteringStats.community_sizes).filter(
    id => clusteringStats.community_sizes[id] > 20
  );
  var largeClusterNodes = nodes.filter(node => largeClusterIds.includes(node.cluster_id));
  
  // Create virtual centers for large clusters
  var clusterCenters = [];
  var clusterConnections = [];
  
  largeClusterIds.forEach(clusterId => {
    var centerId = 'center_' + clusterId;
    clusterCenters.push({
      id: centerId,
      label: '',
      shape: 'dot',
      size: 1,
      color: {
        background: clusterColors[clusterId] || '#2B7CE9',
        border: clusterColors[clusterId] || '#2B7CE9'
      },
      physics: true,
      hidden: true
    });
    
    nodes.filter(node => node.cluster_id === clusterId && largeClusterIds.includes(node.cluster_id)).forEach(node => {
      clusterConnections.push({
        from: node.id,
        to: centerId,
        length: 50,
        color: { opacity: 0 },
        physics: true,
        smooth: false
      });
    });
  });
  
  // Apply cluster colors to large cluster nodes
  var coloredLargeNodes = largeClusterNodes.map(node => {
    var clusterColor = clusterColors[node.cluster_id] || '#2B7CE9';
    return {
      ...node,
      color: {
        border: clusterColor,
        highlight: {
          border: clusterColor
        }
      },
      borderWidth: 4
    };
  });
  
  var largeClusterNodeIds = largeClusterNodes.map(node => node.id);
  var largeClusterEdges = edges.filter(edge =>
    largeClusterNodeIds.includes(edge.from) && largeClusterNodeIds.includes(edge.to)
  );
  
  var allNodes = [...coloredLargeNodes, ...clusterCenters];
  var allEdges = [...largeClusterEdges, ...clusterConnections];
  
  network.setData({ nodes: allNodes, edges: allEdges });
  network.fit();
}

function showSmallClusters() {
  var smallClusterIds = Object.keys(clusteringStats.community_sizes).filter(
    id => clusteringStats.community_sizes[id] < 5
  );
  var smallClusterNodes = nodes.filter(node => smallClusterIds.includes(node.cluster_id));
  
  // Create virtual centers for small clusters
  var clusterCenters = [];
  var clusterConnections = [];
  
  smallClusterIds.forEach(clusterId => {
    var centerId = 'center_' + clusterId;
    clusterCenters.push({
      id: centerId,
      label: '',
      shape: 'dot',
      size: 1,
      color: {
        background: clusterColors[clusterId] || '#2B7CE9',
        border: clusterColors[clusterId] || '#2B7CE9'
      },
      physics: true,
      hidden: true
    });
    
    nodes.filter(node => node.cluster_id === clusterId && smallClusterIds.includes(node.cluster_id)).forEach(node => {
      clusterConnections.push({
        from: node.id,
        to: centerId,
        length: 50,
        color: { opacity: 0 },
        physics: true,
        smooth: false
      });
    });
  });
  
  // Apply cluster colors to small cluster nodes
  var coloredSmallNodes = smallClusterNodes.map(node => {
    var clusterColor = clusterColors[node.cluster_id] || '#2B7CE9';
    return {
      ...node,
      color: {
        border: clusterColor,
        highlight: {
          border: clusterColor
        }
      },
      borderWidth: 4
    };
  });
  
  var smallClusterNodeIds = smallClusterNodes.map(node => node.id);
  var smallClusterEdges = edges.filter(edge =>
    smallClusterNodeIds.includes(edge.from) && smallClusterNodeIds.includes(edge.to)
  );
  
  var allNodes = [...coloredSmallNodes, ...clusterCenters];
  var allEdges = [...smallClusterEdges, ...clusterConnections];
  
  network.setData({ nodes: allNodes, edges: allEdges });
  network.fit();
}

function focusOnCluster(clusterId) {
  filterByCluster(clusterId);
}

function focusOnState(stateId) {
  network.selectNodes([stateId]);
  network.focus(stateId, { animation: true });
  document.getElementById('utg_details').innerHTML = getNodeDetails(stateId);
}

function highlightCluster(clusterId) {
  // This could be enhanced to temporarily highlight all nodes in the cluster
}

function clearClusterHighlight() {
  // Clear any temporary highlighting
}

// Screenshot modal functions
function openScreenshotModal(imageSrc) {
  var modal = document.getElementById('screenshotModal');
  var modalImg = document.getElementById('modalImage');
  modal.style.display = 'block';
  modalImg.src = imageSrc;
}

function closeScreenshotModal() {
  document.getElementById('screenshotModal').style.display = 'none';
}

// Search functionality
function searchUTG() {
  var searchTerm = document.getElementById('utgSearchBar').value.toLowerCase();
  if (!searchTerm) {
    showAllClusters();
    return;
  }

  var matchingNodes = nodes.filter(node => 
    node.id.toLowerCase().includes(searchTerm) ||
    node.cluster_id.includes(searchTerm) ||
    (node.image && node.image.toLowerCase().includes(searchTerm))
  );

  if (matchingNodes.length > 0) {
    var matchingNodeIds = matchingNodes.map(node => node.id);
    var matchingEdges = edges.filter(edge =>
      matchingNodeIds.includes(edge.from) || matchingNodeIds.includes(edge.to)
    );
    
    network.setData({ nodes: matchingNodes, edges: matchingEdges });
    network.fit();
  }
}

// Close modal when clicking outside of it
window.onclick = function(event) {
  var modal = document.getElementById('screenshotModal');
  if (event.target == modal) {
    closeScreenshotModal();
  }
}