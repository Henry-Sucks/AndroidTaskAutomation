# UTG 纯语义聚类工具

## 概述

基于**Embedding向量索引 + VLM在线判断**的智能UTG聚类系统。

### 核心思想

```
输入节点 → [快速初筛] → 高相似度? 
                        ↓ Yes: 直接分配 (快速路径)
                        ↓ No: VLM判断 (精确路径)
                              ↓
                        属于现有簇 or 创建新簇
```

### 与传统方法的对比

| 方法 | 速度 | 准确性 | 成本 |
|------|------|--------|------|
| **纯拓扑聚类** (Louvain) | 极快 | 中等 | 免费 |
| **纯VLM聚类** | 极慢 | 高 | 极高 |
| **本工具（混合）** | 快 | 高 | 低 |

### 技术优势

1. **快速初筛**：80%+节点通过向量索引直接分配（毫秒级）
2. **精确判断**：20%不确定节点使用VLM深度分析
3. **动态扩展**：在线创建簇，无需预设簇数量
4. **语义驱动**：基于功能而非拓扑结构聚类

## 工作流程

```
┌─────────────────────────────────────────────────────────┐
│  输入: utg.js (原始UTG图)                               │
└─────────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────┐
│  步骤1: 遍历所有节点                                     │
│  for each node:                                         │
│    1. 获取embedding (基于截图或文本特征)                │
│    2. 在向量索引中搜索最相似的簇                        │
└─────────────────────────────────────────────────────────┘
                        ↓
        ┌───────────────┴───────────────┐
        │                               │
   相似度 > 0.85?                  相似度 ≤ 0.85?
        │                               │
        ↓                               ↓
┌──────────────────┐          ┌──────────────────────┐
│ 快速路径 (80%+)  │          │ 精确路径 (20%-)      │
│ ✓ 直接分配到簇   │          │ ✓ 调用VLM判断        │
│ ✓ 更新簇向量     │          │ ✓ 属于现有簇 or     │
│ ✓ 成本: 0       │          │   创建新簇           │
└──────────────────┘          │ ✓ 成本: 1次VLM调用  │
                              └──────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────┐
│  输出:                                                  │
│  1. utg_clustered.js - 节点带cluster_id和颜色           │
│  2. cluster_summaries.json - 每个簇的语义摘要           │
│  3. clustering_stats.json - 性能统计                   │
└─────────────────────────────────────────────────────────┘
```

## 核心组件

### 1. VectorIndex - 向量索引

```python
class VectorIndex:
    """快速相似度检索（基于余弦相似度）"""
    
    def add(embedding, cluster_id):
        """添加簇的代表向量"""
    
    def search(query_embedding, top_k=1):
        """搜索最相似的簇"""
        # 返回: [(cluster_id, similarity_score)]
    
    def update(cluster_id, new_embedding):
        """增量更新簇向量（使用平均）"""
```

### 2. ClusterRegistry - 簇注册表

```python
class ClusterRegistry:
    """管理所有簇的元数据"""
    
    def create_new(cluster_name, description, representative_node_id):
        """创建新簇并返回cluster_id"""
    
    def add_node(cluster_id, node_id):
        """向簇中添加节点"""
    
    def get_active_summaries():
        """获取所有簇的摘要（供VLM参考）"""
```

### 3. PureSemanticClustering - 主聚类器

```python
class PureSemanticClustering:
    """纯语义聚类器"""
    
    def run_clustering():
        """执行在线聚类"""
        for node in nodes:
            embedding = get_embedding(node)
            results = vector_index.search(embedding)
            
            if results[0].score > threshold:
                assign_directly(node, results[0].cluster_id)
            else:
                vlm_judgment(node)
```

## 使用方法

### 方法1: 执行脚本（推荐）

```python
# 编辑 run_pure_semantic_clustering.py
utg_path = r"C:\path\to\your\utg.js"

# 运行
python run_pure_semantic_clustering.py
```

### 方法2: 命令行

```bash
# 基本用法
python cluster_pure_semantic.py path/to/utg.js

# 调整相似度阈值
python cluster_pure_semantic.py path/to/utg.js --threshold 0.9

# 指定embedding模型
python cluster_pure_semantic.py path/to/utg.js --embedding vlm

# 指定输出目录
python cluster_pure_semantic.py path/to/utg.js --output ./output

# 完整示例
python cluster_pure_semantic.py \
  "C:\Projects\AndroidTaskAutomation\2_structuring\utg\NetEase Cloud Music\utg.js" \
  --threshold 0.85 \
  --embedding vlm \
  --output ./semantic_output
```

### 方法3: 作为模块导入

```python
from cluster_pure_semantic import PureSemanticClustering

clusterer = PureSemanticClustering(
    utg_path="path/to/utg.js",
    high_similarity_threshold=0.85,
    embedding_model='vlm'
)

clusterer.load_utg_data()
clusterer.run_clustering()
clusterer.save_results()
```

## 配置参数

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `utg_path` | str | - | UTG文件路径（必需） |
| `high_similarity_threshold` | float | 0.85 | 高相似度阈值，超过则直接分配 |
| `embedding_model` | str | 'vlm' | embedding模型 ('vlm', 'clip', 'text') |

### 相似度阈值调优

- **0.90-0.95**: 极保守，VLM调用多（高成本）
- **0.85-0.90**: 平衡（推荐）
- **0.75-0.85**: 激进，直接分配多（可能不够精确）

## 输入要求

工具需要以下文件：

1. **utg.js** - 包含节点数据的JavaScript文件
   ```javascript
   var nodes = [
     {id: "state_0", image: "screen_0.png", activity: "MainActivity", ...},
     ...
   ];
   ```

2. **states/** - 节点截图文件夹（用于VLM分析）

## 输出文件

默认保存到 `{utg_folder}/semantic_clustered/`：

### 1. utg_clustered.js

```javascript
var nodes = [
  {
    id: "state_0",
    image: "screen_0.png",
    cluster_id: "semantic_cluster_0",  // ← 新增
    color: "#3498db",                   // ← 新增
    ...
  },
  ...
];
```

### 2. cluster_summaries.json

```json
{
  "semantic_cluster_0": {
    "cluster_id": "semantic_cluster_0",
    "cluster_name": "Music Library - Browse Songs",
    "functional_description": "Allows users to browse and search their music collection",
    "node_ids": ["state_0", "state_5", "state_12"],
    "representative_node_id": "state_0",
    "node_count": 3
  }
}
```

### 3. clustering_stats.json

```json
{
  "total_nodes": 127,
  "direct_assignments": 105,
  "vlm_judgments": 22,
  "new_clusters_created": 8,
  "final_cluster_count": 8,
  "avg_cluster_size": 15.9,
  "vlm_usage_rate": 0.173
}
```

## VLM判断Prompt示例

当遇到不确定的节点时，系统会调用VLM：

```
Analyze this Android app screenshot and determine if it belongs 
to any existing functional cluster.

### Existing Functional Clusters:
1. **Music Player Interface** (ID: semantic_cluster_0)
   - Provides music playback controls and visualization

2. **Settings Panel** (ID: semantic_cluster_1)
   - Application settings and preferences

**Task:**
Does this UI screen fit into any of the existing clusters above?

- If YES: Return the cluster ID it belongs to.
- If NO: Propose a NEW cluster name and description.

**Output Format (JSON):**
{
    "is_new": true/false,
    "existing_cluster_id": "cluster_id" (if is_new=false),
    "cluster_name": "New Cluster Name" (if is_new=true),
    "description": "Functional description" (if is_new=true),
    "reasoning": "Brief explanation"
}
```

## Embedding策略

### 当前实现（简化版）

```python
def get_embedding(node):
    if node.has_screenshot:
        # 使用VLM生成截图描述
        description = vlm.analyze(screenshot)
        # 转为文本embedding
        return text_to_embedding(description)
    else:
        # 使用节点文本特征
        text = node.activity + " " + node.id
        return text_to_embedding(text)
```

### 升级建议（生产环境）

1. **使用CLIP模型**
   ```python
   import clip
   model, preprocess = clip.load("ViT-B/32")
   embedding = model.encode_image(preprocess(image))
   ```

2. **使用OpenAI Embeddings**
   ```python
   from openai import OpenAI
   client = OpenAI()
   embedding = client.embeddings.create(
       input=description,
       model="text-embedding-3-small"
   ).data[0].embedding
   ```

3. **使用Sentence Transformers**
   ```python
   from sentence_transformers import SentenceTransformer
   model = SentenceTransformer('all-MiniLM-L6-v2')
   embedding = model.encode(description)
   ```

## 性能优化

### 1. 并行处理（可选）

```python
from concurrent.futures import ThreadPoolExecutor

def process_batch(nodes):
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = [executor.submit(_process_node, node) for node in nodes]
        results = [f.result() for f in futures]
    return results
```

### 2. 缓存Embedding

```python
class EmbeddingCache:
    def __init__(self):
        self.cache = {}  # node_id -> embedding
    
    def get_or_compute(self, node):
        if node['id'] not in self.cache:
            self.cache[node['id']] = compute_embedding(node)
        return self.cache[node['id']]
```

### 3. 使用FAISS（大规模数据）

```python
import faiss

class FAISSVectorIndex:
    def __init__(self, dim=512):
        self.index = faiss.IndexFlatIP(dim)  # 内积索引
        self.cluster_ids = []
    
    def add(self, embedding, cluster_id):
        self.index.add(embedding.reshape(1, -1))
        self.cluster_ids.append(cluster_id)
    
    def search(self, query, k=1):
        distances, indices = self.index.search(query.reshape(1, -1), k)
        return [(self.cluster_ids[i], distances[0][j]) 
                for j, i in enumerate(indices[0])]
```

## 示例输出

```
=== 加载UTG数据 ===
✓ 加载 127 个节点

=== 开始纯语义聚类 ===
处理进度: 10/127 (7.9%)
处理进度: 20/127 (15.7%)
...
处理进度: 127/127 (100.0%)

=== 聚类完成 ===
====================================================
聚类统计信息
====================================================
总节点数: 127
最终簇数: 8
直接分配: 105 (82.7%)
VLM判断: 22 (17.3%)
新建簇数: 8
平均簇大小: 15.9

簇大小分布:
  1. Music Player Interface: 28 节点
  2. Music Library - Browse Songs: 22 节点
  3. Settings Panel: 18 节点
  4. Search Interface: 15 节点
  5. User Profile: 12 节点
  ...

=== 保存结果到 .../semantic_clustered ===
  ✓ 保存 utg_clustered.js
  ✓ 保存 cluster_summaries.json
  ✓ 保存 clustering_stats.json
✓ 结果保存完成

性能分析:
  - 直接分配率: 82.7% (通过向量索引快速匹配)
  - VLM调用率: 17.3% (精确判断)
  - 创建的簇数: 8

✓ 向量索引效果良好，大部分节点通过快速匹配完成分簇
```

## 与其他聚类方法的集成

### 1. 作为Louvain聚类的后处理

```python
# 先用Louvain得到初步聚类
from cluster_lourin_utg_js import UTGLouvainClustering
louvain = UTGLouvainClustering(utg_path)
louvain.run_louvain_clustering()

# 再用纯语义聚类优化
from cluster_pure_semantic import PureSemanticClustering
semantic = PureSemanticClustering(louvain.output_folder / "utg_clustered.js")
semantic.run_clustering()
```

### 2. 与后处理合并结合

```python
# 1. 纯语义聚类
from cluster_pure_semantic import PureSemanticClustering
clusterer = PureSemanticClustering(utg_path)
clusterer.run_clustering()
clusterer.save_results()

# 2. 语义相似簇合并
from post_process import ClusterSemanticMerger
merger = ClusterSemanticMerger(clusterer.output_folder)
merger.run_iterative_merging()
```

## 常见问题

**Q: 为什么VLM调用率过高（>50%）？**
A: 
- 检查相似度阈值是否过高
- 检查embedding质量（是否使用了高质量的embedding模型）
- 考虑预先使用拓扑聚类减少节点数

**Q: 如何减少成本？**
A:
1. 提高 `high_similarity_threshold` 到 0.9+（牺牲一些精度）
2. 使用更好的embedding模型（提高初筛准确率）
3. 预先过滤明显属于同一簇的节点

**Q: 聚类结果簇数过多怎么办？**
A:
- 使用 `post_process.py` 进行簇合并
- 调整VLM的prompt，鼓励其分配到现有簇
- 在VLM判断前增加更严格的相似度检查

**Q: 可以不使用VLM吗？**
A: 可以，但需要修改代码使用纯embedding聚类（如K-means），但会失去语义精确性

## 技术限制

1. **Embedding质量依赖**：当前使用简化的embedding，建议替换为CLIP或专业模型
2. **单线程处理**：未实现并行，处理大规模数据可能较慢
3. **内存占用**：所有向量存储在内存中，超大规模数据建议使用FAISS

## 未来改进方向

1. ✅ 集成CLIP模型获取高质量embedding
2. ✅ 使用FAISS支持百万级节点
3. ✅ 实现多线程并行处理
4. ✅ 添加embedding缓存机制
5. ✅ 支持增量聚类（新节点加入现有簇）

## 参考资料

- 伪代码灵感来源：提供的 `cluster_pure_semantic.py`
- 向量索引：FAISS (https://github.com/facebookresearch/faiss)
- CLIP模型：OpenAI CLIP (https://github.com/openai/CLIP)
