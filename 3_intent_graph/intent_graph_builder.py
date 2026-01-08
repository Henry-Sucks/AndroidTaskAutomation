import json
import os
import re
from typing import List, Dict, Set, Tuple
from dataclasses import dataclass, field, asdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from clients.llm_client import LLMClient


@dataclass
class TIGNode:
    """Task Intent Graph Node"""
    id: str  # hash_id
    intent_label: str
    mapped_utg_ids: List[str] = field(default_factory=list)
    capabilities: Set[str] = field(default_factory=set)
    
    def to_dict(self):
        """Convert to dict for JSON serialization"""
        return {
            "id": self.id,
            "intent_label": self.intent_label,
            "mapped_utg_ids": self.mapped_utg_ids,
            "capabilities": sorted(list(self.capabilities))
        }


@dataclass
class TIGEdge:
    """Task Intent Graph Edge"""
    source_tig_id: str
    target_tig_id: str
    action_signature: str  # e.g., "Play(item_id)"
    description: str = ""
    
    def to_dict(self):
        """Convert to dict for JSON serialization"""
        return {
            "source": self.source_tig_id,
            "target": self.target_tig_id,
            "action": self.action_signature,
            "description": self.description
        }


@dataclass
class UTGNode:
    """User Transition Graph Node"""
    id: str
    summary: Dict
    outgoing_edge_ids: List[str] = field(default_factory=list)


@dataclass
class UTGEdge:
    """User Transition Graph Edge"""
    id: str
    source_id: str
    target_id: str
    summary: Dict


class IntentGraphBuilder:
    """Build Task Intent Graph from User Transition Graph"""
    
    def __init__(self, llm_client: LLMClient = None, max_workers: int = 10):
        """
        Initialize Intent Graph Builder
        
        Args:
            llm_client: LLM client for semantic analysis
            max_workers: Maximum number of parallel LLM calls (default: 10)
        """
        self.llm_client = llm_client or LLMClient()
        self.max_workers = max_workers
        
    def load_utg_data(self, utg_js_path: str, edge_analysis_path: str, node_analysis_path: str):
        """
        Load UTG data from files
        
        Args:
            utg_js_path: Path to utg.js file
            edge_analysis_path: Path to edge_analysis.json file
            node_analysis_path: Path to node_analysis.json file
            
        Returns:
            Tuple of (utg_nodes, utg_edges)
        """
        print(f"Loading UTG data from {utg_js_path}...")
        
        # Load edge analysis
        with open(edge_analysis_path, 'r', encoding='utf-8') as f:
            edge_data = json.load(f)
        
        # Load node analysis
        with open(node_analysis_path, 'r', encoding='utf-8') as f:
            node_data = json.load(f)
        
        # Load UTG structure from utg.js
        with open(utg_js_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Parse nodes and edges from utg.js
        utg_nodes = []
        utg_edges = []
        
        # Extract nodes section (JavaScript format: var nodes = [...])
        nodes_match = re.search(r'var\s+nodes\s*=\s*\[(.*?)\];', content, re.DOTALL)
        if nodes_match:
            nodes_str = nodes_match.group(1)
            # Parse node IDs (field name is "id", not "state_str")
            node_ids = re.findall(r'id:\s*"([^"]+)"', nodes_str)
            
            for node_id in node_ids:
                if node_id in node_data.get('nodes', {}):
                    node_info = node_data['nodes'][node_id]
                    utg_nodes.append(UTGNode(
                        id=node_id,
                        summary=node_info,
                        outgoing_edge_ids=[]
                    ))
        
        # Extract edges section (JavaScript format: var edges = [...])
        edges_match = re.search(r'var\s+edges\s*=\s*\[(.*?)\];', content, re.DOTALL)
        if edges_match:
            edges_str = edges_match.group(1)
            # Parse edge objects
            edge_objects = re.findall(r'\{[^}]+\}', edges_str)
            
            for edge_obj_str in edge_objects:
                from_match = re.search(r'from:\s*"([^"]+)"', edge_obj_str)
                to_match = re.search(r'to:\s*"([^"]+)"', edge_obj_str)
                
                if from_match and to_match:
                    from_id = from_match.group(1)
                    to_id = to_match.group(1)
                    edge_id = f"{from_id}#{to_id}"
                    
                    if edge_id in edge_data.get('edges', {}):
                        edge_info = edge_data['edges'][edge_id]
                        utg_edges.append(UTGEdge(
                            id=edge_id,
                            source_id=from_id,
                            target_id=to_id,
                            summary=edge_info
                        ))
                        
                        # Add to outgoing edges
                        for node in utg_nodes:
                            if node.id == from_id:
                                node.outgoing_edge_ids.append(edge_id)
        
        print(f"Loaded {len(utg_nodes)} nodes and {len(utg_edges)} edges")
        return utg_nodes, utg_edges
    
    def llm_analyze_semantics(self, node_summary: Dict, edge_summaries: List[Dict]) -> Dict:
        """
        Phase 1: Analyze node intent and capabilities using LLM
        
        Args:
            node_summary: Summary of the current node
            edge_summaries: Summaries of all outgoing edges
            
        Returns:
            Dict with "intent_label" and "capabilities"
        """
        # Build prompt
        prompt = f"""You are analyzing a UI screen in an Android app to determine its semantic intent.

**Current Screen:**
- Screen Type: {node_summary.get('screen_type', 'Unknown')}
- Primary Intent: {node_summary.get('primary_intent', 'Unknown')}
- Main Content: {node_summary.get('main_content', 'Unknown')}
- State Summary: {node_summary.get('state_summary', 'Unknown')}

**Available Actions from this screen:**
"""
        
        for i, edge_sum in enumerate(edge_summaries, 1):
            prompt += f"\n{i}. {edge_sum.get('intent_summary', 'Unknown action')}"
            if 'semantic_edge' in edge_sum:
                prompt += f" (Function: {edge_sum['semantic_edge'].get('function_signature', 'N/A')})"
        
        prompt += """

**Task:**
1. Determine a high-level **intent_label** that describes this screen's primary purpose (e.g., "Playback_Control", "Search_Mode", "Settings_Menu", "Library_Browse").
2. If this screen is purely decorative, loading, or advertising content with no functional purpose, return "NOISE" as the intent_label.
3. Extract a list of **capabilities** - functional actions the user can perform from this screen (e.g., "Play_Song", "Search_Music", "Adjust_Equalizer").

**Output Format (JSON only, no additional text):**
{{
  "intent_label": "Playback_Control",
  "capabilities": ["Play_Song", "Pause_Song", "Next_Track", "Previous_Track", "Adjust_Volume"]
}}"""
        
        try:
            response = self.llm_client.run(prompt, temperature=0.3)
            # Extract JSON from response
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
                return result
            else:
                print(f"Warning: Could not parse LLM response for node")
                return {"intent_label": "UNKNOWN", "capabilities": []}
        except Exception as e:
            print(f"Error in LLM analysis: {e}")
            return {"intent_label": "ERROR", "capabilities": []}
    
    def llm_analyze_semantics(self, node_summary: Dict, edge_summaries: List[Dict]) -> Dict:
        """
        Phase 1: Analyze node intent and capabilities using LLM
        
        Args:
            node_summary: Summary of the current node
            edge_summaries: Summaries of all outgoing edges
            
        Returns:
            Dict with "intent_label" and "capabilities"
        """
        # Build prompt
        prompt = f"""You are analyzing a UI screen in an Android app to determine its semantic intent.

**Current Screen:**
- Screen Type: {node_summary.get('screen_type', 'Unknown')}
- Primary Intent: {node_summary.get('primary_intent', 'Unknown')}
- Main Content: {node_summary.get('main_content', 'Unknown')}
- State Summary: {node_summary.get('state_summary', 'Unknown')}

**Available Actions from this screen:**
"""
        
        for i, edge_sum in enumerate(edge_summaries, 1):
            prompt += f"\n{i}. {edge_sum.get('intent_summary', 'Unknown action')}"
            if 'semantic_edge' in edge_sum:
                prompt += f" (Function: {edge_sum['semantic_edge'].get('function_signature', 'N/A')})"
        
        prompt += """

**Task:**
1. Determine a high-level **intent_label** that describes this screen's primary purpose (e.g., "Playback_Control", "Search_Mode", "Settings_Menu", "Library_Browse").
2. If this screen is purely decorative, loading, or advertising content with no functional purpose, return "NOISE" as the intent_label.
3. Extract a list of **capabilities** based on the available actions.

**Output Format (JSON only, no additional text):**
{{
  "intent_label": "Playback_Control",
  "capabilities": ["Play_Song", "Pause_Song", "Next_Track", "Adjust_Volume"]
}}"""
        
        try:
            response = self.llm_client.run(prompt, temperature=0.3)
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
            else:
                print(f"Warning: Could not parse LLM response for node")
                return {"intent_label": "UNKNOWN", "capabilities": []}
        except Exception as e:
            print(f"Error in LLM analysis: {e}")
            return {"intent_label": "ERROR", "capabilities": []}
    
    def llm_analyze_action(self, edge_summary: Dict, source_tig: TIGNode, target_tig: TIGNode) -> Tuple[str, str]:
        """
        Phase 3: Analyze edge action signature using LLM.
        
        Key Goal: Distinguish between meaningful self-loops (keep as edges) and noise (discard).
        
        Args:
            edge_summary: Summary of the edge
            source_tig: Source TIG node
            target_tig: Target TIG node
            
        Returns:
            Tuple of (action_signature, edge_category)
        """
        prompt = f"""You are analyzing a user interaction between two screens in an Android app to define a TIG (Task Intent Graph) Edge.

**Source Screen:** {source_tig.intent_label}
**Target Screen:** {target_tig.intent_label}

**Interaction Details:**
- Visual Change: {edge_summary.get('visual_delta', 'Unknown')}
- Transition Type: {edge_summary.get('transition_type', 'Unknown')}
- User Intent: {edge_summary.get('intent_summary', 'Unknown')}
- Function: {edge_summary.get('semantic_edge', {}).get('function_signature', 'Unknown')}

**Task:**
1. Generate a standardized **action_signature** (e.g., "Play(song)", "Navigate(Settings)", "Toggle(Shuffle)").
2. Classify the **edge_category**. This is critical for graph construction:

   - **"TRANSITION"**: The user moves to a DIFFERENT logical screen (Source Intent != Target Intent).
   - **"STATE_MODIFICATION"**: The user stays on the SAME logical screen (Source == Target), BUT performs a meaningful action that changes data or state (e.g., Play/Pause, Like, Delete, Sort, Filter). **KEEP THIS AS AN EDGE.**
   - **"NOISE"**: The user stays on the SAME screen, and the action is trivial or accidental (e.g., Scrolling, clicking whitespace, refreshing unchanged content). **DISCARD THIS.**

**Output Format (JSON only):**
{{
  "action_signature": "Toggle(PlayState)",
  "edge_category": "STATE_MODIFICATION" 
}}"""
        
        try:
            response = self.llm_client.run(prompt, temperature=0.3)
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
                return result.get("action_signature", "Unknown"), result.get("edge_category", "NOISE")
            else:
                print(f"Warning: Could not parse LLM response for edge")
                return "Unknown", "NOISE"
        except Exception as e:
            print(f"Error in LLM analysis: {e}")
            return "Unknown", "NOISE"
    
    def lookup_tig_node(self, utg_node_id: str, tig_nodes_dict: Dict[str, TIGNode], 
                        node_analysis_map: Dict[str, Dict]) -> TIGNode:
        """
        Find the TIG node that contains a specific UTG node
        
        Args:
            utg_node_id: ID of the UTG node
            tig_nodes_dict: Dictionary of TIG nodes
            node_analysis_map: Mapping of UTG nodes to their semantic info
            
        Returns:
            The TIG node or None if not found
        """
        if utg_node_id not in node_analysis_map:
            return None
            
        intent_label = node_analysis_map[utg_node_id].get('intent_label')
        return tig_nodes_dict.get(intent_label)
    
    def generate_tig_from_utg(self, utg_nodes: List[UTGNode], utg_edges: List[UTGEdge]) -> Dict:
        """
        Main function: Generate Task Intent Graph from User Transition Graph
        
        Args:
            utg_nodes: List of UTG nodes
            utg_edges: List of UTG edges
            
        Returns:
            Dict with "nodes" and "edges" for TIG
        """
        # -------------------------------------------------
        # Phase 1: Analyzing Node Intents (PARALLELIZED)
        # -------------------------------------------------
        print(f"\n>>> Phase 1: Analyzing Node Intents (parallel, max_workers={self.max_workers})...")
        node_analysis_map = {}
        
        def analyze_node(u_node):
            """Helper function for parallel node analysis"""
            # Collect context: current node summary + all outgoing edge summaries
            out_edges = [e for e in utg_edges if e.id in u_node.outgoing_edge_ids]
            edge_summaries = [e.summary for e in out_edges]
            
            # LLM call: generate semantic unit
            semantic_info = self.llm_analyze_semantics(u_node.summary, edge_summaries)
            return u_node.id, semantic_info
        
        # Parallel execution
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {executor.submit(analyze_node, u_node): u_node for u_node in utg_nodes}
            
            completed = 0
            for future in as_completed(futures):
                u_node = futures[future]
                try:
                    node_id, semantic_info = future.result()
                    node_analysis_map[node_id] = semantic_info
                    completed += 1
                    print(f"  [{completed}/{len(utg_nodes)}] Analyzed node: {node_id[:20]}... "
                          f"-> Intent: {semantic_info.get('intent_label')}, "
                          f"Capabilities: {len(semantic_info.get('capabilities', []))}")
                except Exception as e:
                    print(f"  Error analyzing node {u_node.id}: {e}")
        
        # -------------------------------------------------
        # Phase 2: Merging Nodes
        # -------------------------------------------------
        print("\n>>> Phase 2: Merging Nodes...")
        tig_nodes_dict = {}  # Intent_Label -> TIGNode
        
        for u_node_id, info in node_analysis_map.items():
            label = info['intent_label']
            
            # Skip noise nodes (ads, loading screens, etc.)
            if label == "NOISE":
                print(f"  Skipping noise node: {u_node_id}")
                continue
            
            # Create or update TIG node
            if label not in tig_nodes_dict:
                # Create new TIG node
                tig_nodes_dict[label] = TIGNode(
                    id=f"TIG_{label.upper()}",
                    intent_label=label,
                    mapped_utg_ids=[],
                    capabilities=set()
                )
                print(f"  Created TIG node: {label}")
            
            # Map physical node to logical node
            tig_node = tig_nodes_dict[label]
            tig_node.mapped_utg_ids.append(u_node_id)
            tig_node.capabilities.update(info.get('capabilities', []))
        
        print(f"  Total TIG nodes created: {len(tig_nodes_dict)}")
        
        # -------------------------------------------------
        # Phase 3: Edge Abstraction and Connection (PARALLELIZED)
        # -------------------------------------------------
        print(f"\n>>> Phase 3: Constructing Edges (parallel, max_workers={self.max_workers})...")
        
        final_tig_edges = []
        seen_connections = set()  # For deduplication (Source, Target, Action)
        
        def analyze_edge(u_edge):
            """Helper function for parallel edge analysis"""
            # Find the corresponding TIG nodes
            source_tig = self.lookup_tig_node(u_edge.source_id, tig_nodes_dict, node_analysis_map)
            target_tig = self.lookup_tig_node(u_edge.target_id, tig_nodes_dict, node_analysis_map)
            
            if not source_tig or not target_tig:
                return None
            
            # Generate action signature
            action_sig, action_type = self.llm_analyze_action(u_edge.summary, source_tig, target_tig)
            
            return {
                'edge': u_edge,
                'source_tig': source_tig,
                'target_tig': target_tig,
                'action_sig': action_sig,
                'action_type': action_type
            }
        
        # Parallel execution
        edge_results = []
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {executor.submit(analyze_edge, u_edge): u_edge for u_edge in utg_edges}
            
            completed = 0
            for future in as_completed(futures):
                u_edge = futures[future]
                try:
                    result = future.result()
                    if result:
                        edge_results.append(result)
                    completed += 1
                    print(f"  [{completed}/{len(utg_edges)}] Analyzed edge: {u_edge.id[:40]}...")
                except Exception as e:
                    print(f"  Error analyzing edge {u_edge.id}: {e}")
        
        # Process results
        for result in edge_results:
            source_tig = result['source_tig']
            target_tig = result['target_tig']
            action_sig = result['action_sig']
            action_type = result['action_type']
            u_edge = result['edge']
            
            # Handle self-loops
            # 1. 优先过滤噪音
            # 无论是自环还是跳转，如果 LLM 判定为 NAVIGATION_NOISE (如滑动、误触)，直接丢弃
            if action_type == "NAVIGATION_NOISE":
                continue

            # 2. 生成边 (Edge Construction)
            # 包含：
            #   Case A: 正常的跳转 (source != target)
            #   Case B: 功能性自环 (source == target, type == FUNCTIONAL_INTERACTION)
            connection_key = (source_tig.id, target_tig.id, action_sig)

            if connection_key not in seen_connections:
                new_edge = TIGEdge(
                    source_tig_id=source_tig.id,
                    target_tig_id=target_tig.id,
                    action_signature=action_sig,
                    description=u_edge.summary.get('intent_summary', '')
                )
                final_tig_edges.append(new_edge)
                seen_connections.add(connection_key)

                # 3. 日志与辅助处理
                if source_tig.id == target_tig.id:
                    # 即使作为 Edge 存在，将其加入 capabilities 集合依然是一个好习惯
                    # 这样 Agent 在查询 "Current Node Capabilities" 时能快速索引
                    source_tig.capabilities.add(action_sig)
                    print(f"  [Self-Loop Edge] {source_tig.id} --[{action_sig}]--> {source_tig.id}")
                else:
                    print(f"  [Transition Edge] {source_tig.id} --[{action_sig}]--> {target_tig.id}")
        
        print(f"  Total TIG edges created: {len(final_tig_edges)}")
        
        # -------------------------------------------------
        # Return final graph structure
        # -------------------------------------------------
        return {
            "nodes": list(tig_nodes_dict.values()),
            "edges": final_tig_edges
        }
    
    def save_tig(self, tig_data: Dict, output_path: str):
        """
        Save TIG to JSON file
        
        Args:
            tig_data: TIG data with nodes and edges
            output_path: Path to save the TIG JSON file
        """
        # Convert to serializable format
        output_data = {
            "metadata": {
                "total_nodes": len(tig_data["nodes"]),
                "total_edges": len(tig_data["edges"])
            },
            "nodes": [node.to_dict() for node in tig_data["nodes"]],
            "edges": [edge.to_dict() for edge in tig_data["edges"]]
        }
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, ensure_ascii=False, indent=2)
        
        print(f"\nTIG saved to: {output_path}")


def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Build Task Intent Graph from UTG')
    parser.add_argument('--utg_dir', type=str, required=True,
                        help='Directory containing utg.js, edge_analysis.json, and node_analysis.json')
    parser.add_argument('--output', type=str, default='tig.json',
                        help='Output path for tig.json (default: tig.json)')
    parser.add_argument('--max_workers', type=int, default=10,
                        help='Maximum number of parallel LLM calls (default: 10)')
    
    args = parser.parse_args()
    
    # Construct file paths
    utg_js_path = os.path.join(args.utg_dir, 'utg.js')
    edge_analysis_path = os.path.join(args.utg_dir, 'edge_analysis.json')
    node_analysis_path = os.path.join(args.utg_dir, 'node_analysis.json')
    output_path = os.path.join(args.utg_dir, args.output)
    
    # Verify files exist
    for path in [utg_js_path, edge_analysis_path, node_analysis_path]:
        if not os.path.exists(path):
            print(f"Error: File not found: {path}")
            return
    
    # Build TIG
    builder = IntentGraphBuilder(max_workers=args.max_workers)
    
    # Load UTG data
    utg_nodes, utg_edges = builder.load_utg_data(
        utg_js_path, edge_analysis_path, node_analysis_path
    )
    
    # Generate TIG
    tig_data = builder.generate_tig_from_utg(utg_nodes, utg_edges)
    
    # Save TIG
    builder.save_tig(tig_data, output_path)
    
    print("\n=== TIG Generation Complete ===")
    print(f"Nodes: {len(tig_data['nodes'])}")
    print(f"Edges: {len(tig_data['edges'])}")
    print(f"Max Workers: {args.max_workers}")


if __name__ == '__main__':
    main()
