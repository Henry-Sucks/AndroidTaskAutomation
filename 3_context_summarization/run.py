from cluster_summary.pipeline import ClusterSummaryPipeline

pipeline = ClusterSummaryPipeline(
    cluster_info_path="cluster_info.json",
    utg_clustered_path="utg_clustered.js",
    image_root="screens/"
)

pipeline.run()
