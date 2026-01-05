"""
簇语义合并执行脚本

使用示例：
    python run_semantic_merge.py
"""

from post_process import ClusterSemanticMerger


def main():
    """执行簇语义合并"""
    
    # 配置UTG文件夹路径
    utg_folder = r"C:\\Projects\\AndroidTaskAutomation\\2_clustering\\utg\\NetEase Cloud Music"
    
    # 创建语义合并器
    merger = ClusterSemanticMerger(
        utg_folder=utg_folder,
        similarity_threshold=0.75,      # 相似度阈值: 超过此值的簇将被合并
        min_cluster_size=3,             # 最小簇大小
        max_iterations=10,              # 最大迭代次数
        use_vlm=True                    # 是否使用VLM进行视觉分析
    )
    
    print("=" * 80)
    print("UTG 簇语义合并工具")
    print("=" * 80)
    
    # 1. 加载聚类数据
    merger.load_data()
    
    # 2. 执行迭代合并 (interactive=True 表示每次迭代后询问是否继续)
    iterations = merger.run_iterative_merging(interactive=True)
    
    # 3. 保存结果
    output_folder = None  # None表示保存到默认位置: utg_folder/semantic_merged
    merger.save_results(output_folder=output_folder)
    
    # 4. 打印统计信息
    print("\n" + "=" * 80)
    print("处理完成！统计信息：")
    print("=" * 80)
    print(f"总迭代次数: {iterations}")
    print(f"最终簇数: {len(merger.clusters)}")
    print(f"\n簇大小分布:")
    
    from collections import Counter
    cluster_sizes = Counter(len(nodes) for nodes in merger.clusters.values())
    for size, count in sorted(cluster_sizes.items(), reverse=True):
        print(f"  大小 {size:3d}: {count:2d} 个簇")
    
    print(f"\n输出目录: {merger.utg_folder / 'semantic_merged'}")
    print("=" * 80)


if __name__ == "__main__":
    main()
