# UTG 簇语义合并工具

## 功能概述

该工具实现了基于语义相似度的UTG簇合并功能，借鉴了 `3_context_summarization/cluster_summary` 中的VLM/LLM分析方法。

### 主要功能

1. **语义摘要生成**：为每个簇生成语义摘要（使用VLM分析节点截图 + LLM综合生成）
2. **相似度计算**：计算簇之间的语义相似度（结合文本相似度和LLM语义判断）
3. **自动合并**：合并语义相似的簇
4. **迭代优化**：递归执行直到收敛或人工停止

## 工作流程

```
输入: utg_clustered.js + cluster_info.json
  ↓
步骤1: 为每个簇生成语义摘要
  ├─ 采样代表性节点
  ├─ VLM分析节点截图 (可选)
  └─ LLM综合生成簇摘要
  ↓
步骤2: 计算簇间语义相似度
  ├─ 文本序列相似度 (SequenceMatcher)
  └─ LLM语义相似度判断
  ↓
步骤3: 合并高相似度簇
  ├─ 使用Union-Find算法
  └─ 避免过度合并(大小限制)
  ↓
步骤4: 更新数据结构
  ├─ 更新节点cluster_id
  └─ 重新生成簇摘要
  ↓
判断: 是否还有需要合并的簇?
  ├─ 是 → 返回步骤1 (下一轮迭代)
  └─ 否 → 输出结果
  ↓
输出: 
  ├─ utg_clustered.js (更新后的聚类)
  ├─ cluster_summaries.json (簇摘要)
  └─ merge_history.json (合并历史)
```

## 使用方法

### 方法1: 使用执行脚本

```python
# 编辑 run_semantic_merge.py 中的配置
utg_folder = r"C:\path\to\your\utg\folder"

# 运行
python run_semantic_merge.py
```

### 方法2: 命令行直接调用

```bash
# 基本用法
python post_process.py /path/to/utg/folder

# 指定相似度阈值
python post_process.py /path/to/utg/folder --threshold 0.8

# 交互模式(每次迭代后询问是否继续)
python post_process.py /path/to/utg/folder --interactive

# 禁用VLM分析(仅使用LLM)
python post_process.py /path/to/utg/folder --no-vlm

# 指定输出目录
python post_process.py /path/to/utg/folder --output /path/to/output

# 完整示例
python post_process.py \
  "C:\Projects\AndroidTaskAutomation\2_structuring\utg\NetEase Cloud Music" \
  --threshold 0.75 \
  --max-iterations 10 \
  --interactive \
  --output ./output_merged
```

### 方法3: 作为模块导入

```python
from post_process import ClusterSemanticMerger

# 创建合并器
merger = ClusterSemanticMerger(
    utg_folder="path/to/utg/folder",
    similarity_threshold=0.75,  # 相似度阈值
    max_iterations=10,          # 最大迭代次数
    use_vlm=True                # 是否使用VLM
)

# 加载数据
merger.load_data()

# 执行合并(非交互)
merger.run_iterative_merging(interactive=False)

# 或者手动控制流程
merger.generate_cluster_summaries()
similarity_matrix = merger.calculate_similarity_matrix()
cluster_mapping = merger.merge_similar_clusters(similarity_matrix)
merger.apply_cluster_mapping(cluster_mapping)

# 保存结果
merger.save_results()
```

## 配置参数

### ClusterSemanticMerger 参数

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `utg_folder` | str | - | UTG文件夹路径(必需) |
| `similarity_threshold` | float | 0.75 | 相似度阈值，超过此值的簇将被合并 |
| `min_cluster_size` | int | 3 | 最小簇大小，避免过度合并 |
| `max_iterations` | int | 10 | 最大迭代次数 |
| `use_vlm` | bool | True | 是否使用VLM进行视觉分析 |

### 相似度阈值建议

- **0.6-0.7**: 较激进的合并，适合初步降低簇数量
- **0.75-0.8**: 平衡的合并策略（推荐）
- **0.85-0.9**: 保守的合并，仅合并极相似的簇

## 输入文件要求

工具需要以下文件（通常由 `cluster_lourin_utg_js.py` 生成）：

1. **utg_clustered.js** - 包含聚类后的节点数据
2. **cluster_info.json** (可选) - 包含簇的元数据
3. **states/** - 节点截图文件夹（VLM分析时需要）
4. **layout/** - XML布局文件夹（可选）

## 输出文件

默认输出到 `{utg_folder}/semantic_merged/`：

1. **utg_clustered.js** - 更新后的聚类图
2. **cluster_summaries.json** - 所有簇的语义摘要
   ```json
   {
     "cluster_0": {
       "cluster_id": "cluster_0",
       "node_count": 15,
       "summary": {
         "cluster_name": "Music Player Interface",
         "summary": "Provides music playback controls and visualization",
         "primary_capabilities": ["Play/Pause", "Skip Track", "Volume Control"],
         "functional_scope": "Active playback session management",
         "key_distinguishing_features": "Waveform visualization and lyrics display"
       }
     }
   }
   ```

3. **merge_history.json** - 每轮迭代的合并记录
   ```json
   [
     {
       "merge_count": 3,
       "merged_groups": [
         ["cluster_1", "cluster_3", 0.82],
         ["cluster_2", "cluster_5", 0.78]
       ],
       "cluster_mapping": {
         "cluster_1": "cluster_1",
         "cluster_2": "cluster_2",
         "cluster_3": "cluster_1",
         "cluster_5": "cluster_2"
       }
     }
   ]
   ```

## 技术细节

### VLM分析流程

1. 从每个簇中采样代表性节点（优先选择有截图的节点）
2. 使用VLMClient分析截图，提取：
   - 页面标题
   - 主要功能
   - 功能范围
   - 独特特征
   - 可见操作

### LLM摘要生成

输入：
- VLM分析结果
- 节点Activity信息
- 簇的拓扑结构信息

输出JSON格式：
```json
{
  "cluster_name": "短且具体的名称",
  "summary": "一句话描述主要功能",
  "primary_capabilities": ["核心操作列表"],
  "functional_scope": "操作的具体领域/数据",
  "key_distinguishing_features": "区别于其他簇的独特特征"
}
```

### 相似度计算

采用**混合策略**：

1. **快速筛选** (SequenceMatcher)
   - 计算摘要文本的序列相似度
   - 时间复杂度: O(1)

2. **精确判断** (LLM Semantic Similarity)
   - 仅对初筛相似度 > 0.5 的簇对使用
   - LLM返回0-1的相似度分数
   - 综合两种方法取平均

### 簇合并算法

使用 **Union-Find (并查集)** 算法：

- 优点：高效处理传递性合并（A合B，B合C → A合C）
- 路径压缩优化：查询复杂度接近O(1)
- 避免过大簇：检查合并后大小是否超过阈值

## 示例输出

```
=== 加载聚类数据 ===
✓ 加载完成: 127 个节点, 8 个簇

=== 迭代 1/10 ===

=== 生成簇语义摘要 ===
处理簇 cluster_0 (18 个节点)...
✓ 簇 cluster_0 摘要: Music Library - Browse Songs

处理簇 cluster_1 (22 个节点)...
✓ 簇 cluster_1 摘要: Music Library - Album View

=== 计算簇间语义相似度 ===
  高相似度: cluster_0 <-> cluster_1 = 0.812

=== 合并相似簇 ===
  ✓ 合并 cluster_0 <- cluster_1 (相似度: 0.812)
✓ 完成: 合并了 1 对簇

继续下一轮合并? (y/n): y

=== 迭代 2/10 ===
...

✓ 收敛: 没有发现相似度超过阈值 (0.75) 的簇对

处理完成！统计信息：
总迭代次数: 2
最终簇数: 6

簇大小分布:
  大小  40:  1 个簇
  大小  25:  2 个簇
  大小  18:  2 个簇
  大小  12:  1 个簇
```

## 注意事项

1. **VLM调用成本**：使用VLM会产生API调用费用，可通过 `--no-vlm` 禁用
2. **迭代次数**：通常2-3轮即可收敛，可通过 `--max-iterations` 调整
3. **交互模式**：建议首次使用时启用 `--interactive` 以观察合并效果
4. **阈值调优**：建议从0.75开始，根据实际效果调整

## 与cluster_lourin_utg_js.py的集成

可以在原有聚类脚本中调用语义合并：

```python
# 在 cluster_lourin_utg_js.py 的 main() 函数末尾添加

from post_process import ClusterSemanticMerger

# 原有聚类完成后
clusterer.save_clustering_results()

# 执行语义合并
print("\n" + "="*60)
print("开始语义合并...")
print("="*60)

merger = ClusterSemanticMerger(
    utg_folder=str(clusterer.utg_folder),
    similarity_threshold=0.75,
    use_vlm=True
)

merger.load_data()
merger.run_iterative_merging(interactive=True)
merger.save_results()
```

## 常见问题

**Q: 为什么合并后簇数量没有减少？**
A: 可能是相似度阈值设置过高，尝试降低到0.65-0.7

**Q: 如何跳过VLM分析加快速度？**
A: 使用 `--no-vlm` 参数，仅基于Activity等元数据生成摘要

**Q: 可以手动停止迭代吗？**
A: 使用 `--interactive` 模式，每轮迭代后会询问是否继续

**Q: 合并结果不满意如何回退？**
A: 查看 `merge_history.json` 了解合并过程，或重新运行调整阈值

## 贡献者

基于 `3_context_summarization/cluster_summary` 实现
