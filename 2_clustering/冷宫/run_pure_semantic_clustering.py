"""
纯语义聚类执行脚本

使用方法：
    python run_pure_semantic_clustering.py
"""

from cluster_pure_semantic import PureSemanticClustering


def main():
    """执行纯语义聚类"""
    
    # 配置UTG文件路径
    utg_path = r"C:\Projects\AndroidTaskAutomation\2_clustering\utg\NetEase Cloud Music\utg.js"
    
    print("=" * 80)
    print("UTG 纯语义聚类工具")
    print("基于 Embedding向量索引 + VLM在线判断")
    print("=" * 80)
    
    # 创建聚类器
    clusterer = PureSemanticClustering(
        utg_path=utg_path,
        high_similarity_threshold=0.85,  # 高相似度阈值：超过此值直接分配
        embedding_model='clip'            # 使用CLIP模型（需安装sentence-transformers）
    )
    
    # 1. 加载UTG数据
    print("\n步骤 1/3: 加载数据...")
    clusterer.load_utg_data()
    
    # 2. 执行聚类
    print("\n步骤 2/3: 执行在线语义聚类...")
    print("提示：")
    print("  - 使用CLIP模型获取高质量embedding")
    print("  - 高相似度节点会直接分配到现有簇（快速）")
    print("  - 不确定的节点会调用VLM判断（精确但耗时）")
    print("  - VLM只会收到Top-5最相似的候选簇（减少token消耗）")
    print("  - 会动态创建新簇以容纳不同功能的UI")
    print()
    
    # 可选：使用并行处理（注意：VLM API可能有并发限制）
    use_parallel = False  # 设为True启用并行
    max_workers = 3       # 并行线程数
    
    clusterer.run_clustering(max_workers=max_workers, use_parallel=use_parallel)
    
    # 3. 保存结果
    print("\n步骤 3/3: 保存结果...")
    output_folder = None  # None表示保存到默认位置
    clusterer.save_results(output_folder=output_folder)
    
    # 4. 结果总结
    print("\n" + "=" * 80)
    print("处理完成！")
    print("=" * 80)
    
    print(f"\n输出目录: {clusterer.utg_folder / 'semantic_clustered'}")
    print("\n生成的文件:")
    print("  1. utg_clustered.js - 更新后的聚类图")
    print("  2. cluster_summaries.json - 簇的语义摘要")
    print("  3. clustering_stats.json - 聚类统计信息")
    
    print("\n性能分析:")
    vlm_rate = clusterer.stats['vlm_judgments'] / clusterer.stats['total_nodes'] * 100
    direct_rate = clusterer.stats['direct_assignments'] / clusterer.stats['total_nodes'] * 100
    
    print(f"  - 直接分配率: {direct_rate:.1f}% (通过向量索引快速匹配)")
    print(f"  - VLM调用率: {vlm_rate:.1f}% (精确判断)")
    print(f"  - 创建的簇数: {clusterer.stats['new_clusters_created']}")
    
    if vlm_rate < 30:
        print("\n✓ 向量索引效果良好，大部分节点通过快速匹配完成分簇")
    elif vlm_rate > 70:
        print("\n⚠ VLM调用较多，考虑调整相似度阈值或优化embedding质量")
    
    print("=" * 80)


if __name__ == "__main__":
    main()
