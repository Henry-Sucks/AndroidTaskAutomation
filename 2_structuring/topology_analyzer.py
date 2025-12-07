"""
topology_analyzer.py

读取 `utg_clustered.js` 文件（一个定义了 `nodes` 和 `edges` 数组的JS文件），
提取节点和边数据，为每个聚类计算：
- 聚类大小：包含的节点数量
- 节点列表：聚类内所有节点的ID
- 聚类内边：簇内节点之间的所有边
- 来自其他聚类的边：按源聚类分组的跨聚类边
- 到其他聚类的边：按目标聚类分组的跨聚类边
- 入口点：作为跨聚类边目标的节点
- 出口点：作为跨聚类边源点的节点  
- 中心点：聚类内部度数（入度+出度）最高的节点

将结果写入输入文件同目录下的 `cluster_info.json` 文件。

用法：python topology_analyzer.py /path/to/utg_clustered.js
如果未提供参数，程序将尝试从当前工作目录读取 `utg_clustered.js` 文件。

输出格式：
{
  "clusters": {
    "cluster_id": {
      "size": int,                           # 聚类大小
      "nodes": [node_id, ...],              # 节点列表
      "edges_inside_cluster": [...],        # 聚类内边
      "edges_from_other_clusters": [...],   # 来自其他聚类的边
      "edges_to_other_clusters": [...],     # 到其他聚类的边
      "entry_points": [node_id, ...],       # 入口点
      "exit_points": [node_id, ...],        # 出口点
      "center_point": [node_id]             # 中心点
    }
  }
}
"""

import json
import re
import sys
from pathlib import Path


def read_file_text(path: Path) -> str:
	return path.read_text(encoding="utf-8")


def extract_js_array(text: str, varname: str):
	# match `var nodes = [ ... ];` or `let nodes = [...]` or `const nodes = [...]`
	pattern = re.compile(r"\b(?:var|let|const)\s+%s\s*=\s*(\[.*?\])\s*;" % re.escape(varname), re.S)
	m = pattern.search(text)
	if not m:
		return None
	return m.group(1)

def js_to_json(js_text: str) -> str:
    # 使用更安全的方法处理JavaScript到JSON的转换
    import json
    
    # 方法1：尝试直接解析（可能已经是有效的JSON）
    try:
        json.loads(js_text)
        return js_text
    except:
        pass
    
    # 方法2：手动构建JSON数组
    if js_text.strip().startswith('[') and js_text.strip().endswith(']'):
        # 移除外层的数组括号
        content = js_text.strip()[1:-1].strip()
        
        # 分割对象，但需要小心处理嵌套结构
        objects = []
        current_obj = ""
        brace_count = 0
        in_string = False
        escape_next = False
        
        for char in content + ',':  # 添加逗号确保处理最后一个元素
            if escape_next:
                current_obj += char
                escape_next = False
            elif char == '\\':
                current_obj += char
                escape_next = True
            elif char == '"' and not in_string:
                in_string = True
                current_obj += char
            elif char == '"' and in_string:
                in_string = False
                current_obj += char
            elif char == '{' and not in_string:
                brace_count += 1
                current_obj += char
            elif char == '}' and not in_string:
                brace_count -= 1
                current_obj += char
            elif char == ',' and brace_count == 0 and not in_string:
                if current_obj.strip():
                    objects.append(current_obj.strip())
                current_obj = ""
            else:
                current_obj += char
        
        # 尝试解析每个对象
        valid_objects = []
        for obj in objects:
            obj = obj.strip()
            if not obj:
                continue
                
            # 确保对象有花括号
            if not obj.startswith('{'):
                obj = '{' + obj
            if not obj.endswith('}'):
                obj = obj + '}'
            
            # 修复常见的JavaScript格式问题
            obj = re.sub(r"([\{,])\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*:", r'\1"\2":', obj)
            obj = re.sub(r",\s*}", "}", obj)
            obj = re.sub(r",\s*]", "]", obj)
            
            try:
                valid_objects.append(json.loads(obj))
            except:
                # 如果解析失败，跳过这个对象
                continue
        
        # 返回有效的JSON数组
        return json.dumps(valid_objects)
    
    return "[]"

def parse_js_array_to_list(js_array_text: str):
    json_text = js_to_json(js_array_text)

    try:
        return json.loads(json_text)
    except json.JSONDecodeError as e:
        print(f"JSON解析错误: {e}")
        
        # 显示错误位置附近的上下文
        lines = json_text.split('\n')
        error_line = 2  # 根据错误信息，错误在第2行
        error_col = 6   # 第6列
        
        print(f"错误发生在第{error_line}行，第{error_col}列")
        print(f"错误行内容: {repr(lines[error_line-1])}")
        
        # 显示错误位置标记
        marker = ' ' * (error_col - 1) + '↑'
        print(f"位置标记: {marker}")
        
        # 显示错误位置前后的内容
        start_pos = max(0, e.pos - 20)
        end_pos = min(len(json_text), e.pos + 20)
        print(f"错误位置附近的内容: {repr(json_text[start_pos:end_pos])}")
        
        raise


def resolve_node_ref(ref, nodes_by_index, nodes_by_id):
	# ref can be int (index), or string id, or numeric string
	if isinstance(ref, int):
		if 0 <= ref < len(nodes_by_index):
			return nodes_by_index[ref]['_resolved_id']
		return str(ref)
	if isinstance(ref, str):
		if ref in nodes_by_id:
			return ref
		if ref.isdigit():
			idx = int(ref)
			if 0 <= idx < len(nodes_by_index):
				return nodes_by_index[idx]['_resolved_id']
		return ref
	return str(ref)


def analyze_clusters(nodes, edges):
    print("=== 聚类分析调试 ===")
    print(f"输入节点数: {len(nodes)}")
    print(f"输入边数: {len(edges)}")

    # Normalize node ids and cluster ids
    nodes_by_index = []
    nodes_by_id = {}

    for i, n in enumerate(nodes):
        # try several possible id keys
        nid = None
        for k in ('id', ):
            if k in n:
                nid = n[k]
                break
        if nid is None:
            # fallback to index-based id
            nid = f"n{i}"

        # cluster can be in 'cluster' or 'group' or 'community'
        cluster = None
        for k in ('cluster_id', ):
            if k in n:
                cluster = n[k]
                break
        if cluster is None:
            cluster = 0

        # ensure strings
        nid = str(nid)
        try:
            cluster = int(cluster)
        except Exception:
            cluster = str(cluster)

        entry = {'_resolved_id': nid, 'cluster': cluster}
        entry.update(n)
        nodes_by_index.append(entry)
        nodes_by_id[nid] = entry

    # Prepare node cluster mapping
    node_cluster = {nid: entry['cluster'] for nid, entry in nodes_by_id.items()}

    # Determine edge endpoints, normalize ids
    normalized_edges = []
    for i, e in enumerate(edges):
        # possible keys
        s = e.get('source') if 'source' in e else e.get('from') if 'from' in e else e.get('src') if 'src' in e else None
        t = e.get('target') if 'target' in e else e.get('to') if 'to' in e else e.get('dst') if 'dst' in e else None

        s_id = resolve_node_ref(s, nodes_by_index, nodes_by_id)
        t_id = resolve_node_ref(t, nodes_by_index, nodes_by_id)
        
        # Get edge tag/id if available
        edge_tag = e.get('id', e.get('tag', f'e{i}'))
        # support new fields: bboxes, action_types
        bboxes = e.get('bboxes') if 'bboxes' in e else e.get('bbox') if 'bbox' in e else None
        action_types = e.get('action_types') if 'action_types' in e else e.get('actions') if 'actions' in e else None

        normalized_edges.append({
            'source': s_id,
            'target': t_id,
            'tag': str(edge_tag),
            'bboxes': bboxes,
            'action_types': action_types,
            'original': e
        })

    # Initialize cluster data structures
    clusters = {}
    for nid, entry in nodes_by_id.items():
        cid = entry['cluster']
        if cid not in clusters:
            clusters[cid] = {
                'nodes': set(), 
                'entry_points': set(), 
                'exit_points': set(), 
                'deg_in': {}, 
                'deg_out': {},
                'edges_inside_cluster': [],
                'edges_from_other_clusters': {},
                'edges_to_other_clusters': {}
            }
        clusters[cid]['nodes'].add(nid)
        clusters[cid]['deg_in'][nid] = 0
        clusters[cid]['deg_out'][nid] = 0

    # Process edges
    for e in normalized_edges:
        s = e['source']
        t = e['target']
        tag = e['tag']
        s_cluster = node_cluster.get(s)
        t_cluster = node_cluster.get(t)

        # If either node unknown, skip
        if s_cluster is None or t_cluster is None:
            continue

        if s_cluster != t_cluster:
            # inter-cluster: t is entry of its cluster, s is exit of its cluster
            clusters[t_cluster]['entry_points'].add(t)
            clusters[s_cluster]['exit_points'].add(s)
            
            # Track edges from other clusters
            if s_cluster not in clusters[t_cluster]['edges_from_other_clusters']:
                clusters[t_cluster]['edges_from_other_clusters'][s_cluster] = []
            edge_entry = {'from': s, 'to': t, 'tag': tag}
            if e.get('bboxes'):
                edge_entry['bboxes'] = e.get('bboxes')
            if e.get('action_types'):
                edge_entry['action_types'] = e.get('action_types')
            clusters[t_cluster]['edges_from_other_clusters'][s_cluster].append(edge_entry)
            
            # Track edges to other clusters  
            if t_cluster not in clusters[s_cluster]['edges_to_other_clusters']:
                clusters[s_cluster]['edges_to_other_clusters'][t_cluster] = []
            edge_entry2 = {'from': s, 'to': t, 'tag': tag}
            if e.get('bboxes'):
                edge_entry2['bboxes'] = e.get('bboxes')
            if e.get('action_types'):
                edge_entry2['action_types'] = e.get('action_types')
            clusters[s_cluster]['edges_to_other_clusters'][t_cluster].append(edge_entry2)
        else:
            # internal edge: count degrees and store edge
            clusters[s_cluster]['deg_out'][s] = clusters[s_cluster]['deg_out'].get(s, 0) + 1
            clusters[s_cluster]['deg_in'][t] = clusters[s_cluster]['deg_in'].get(t, 0) + 1
            edge_inside = {'from': s, 'to': t, 'tag': tag}
            if e.get('bboxes'):
                edge_inside['bboxes'] = e.get('bboxes')
            if e.get('action_types'):
                edge_inside['action_types'] = e.get('action_types')
            clusters[s_cluster]['edges_inside_cluster'].append(edge_inside)

    # Build final result
    result = {}
    for cid, data in clusters.items():
        center = None
        max_deg = -1
        for nid in data['nodes']:
            deg_in = data['deg_in'].get(nid, 0)
            deg_out = data['deg_out'].get(nid, 0)
            deg = deg_in + deg_out
            if deg > max_deg:
                max_deg = deg
                center = nid

        # Format edges_from_other_clusters
        edges_from_other = []
        for from_cluster_id, edge_list in data['edges_from_other_clusters'].items():
            edges_from_other.append({
                'from_cluster_id': str(from_cluster_id),
                'edges': edge_list
            })
            
        # Format edges_to_other_clusters
        edges_to_other = []
        for to_cluster_id, edge_list in data['edges_to_other_clusters'].items():
            edges_to_other.append({
                'to_cluster_id': str(to_cluster_id),
                'edges': edge_list
            })

        result[str(cid)] = {
            'size': len(data['nodes']),
            'nodes': sorted(list(data['nodes'])),
            'edges_inside_cluster': data['edges_inside_cluster'],
            'edges_from_other_clusters': edges_from_other,
            'edges_to_other_clusters': edges_to_other,
            'entry_points': sorted(list(data['entry_points'])),
            'exit_points': sorted(list(data['exit_points'])),
            'center_point': [center] if center is not None else []
        }

    print("=== 分析结果检查 ===")

    return {'clusters': result}


def main():
    if len(sys.argv) > 1:
        input_path = Path(sys.argv[1])
    else:
        input_path = Path('utg_clustered.js')

    if not input_path.exists():
        print(f"Input file not found: {input_path}")
        sys.exit(2)

    text = read_file_text(input_path)

    nodes_text = extract_js_array(text, 'nodes')
    edges_text = extract_js_array(text, 'edges')

    if nodes_text is None or edges_text is None:
        print("Could not find `nodes` or `edges` arrays in the JS file.")
        sys.exit(2)

    nodes = parse_js_array_to_list(nodes_text)
    print("Nodes parsed:", len(nodes))
    edges = parse_js_array_to_list(edges_text)
    print("Edges parsed:", len(edges))


    info = analyze_clusters(nodes, edges)

    out_path = input_path.parent / 'cluster_info.json'
    out_path.write_text(json.dumps(info, indent=2, ensure_ascii=False), encoding='utf-8')
    print(f"Wrote cluster info to: {out_path}")


if __name__ == '__main__':
	main()

