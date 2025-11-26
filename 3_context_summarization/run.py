from cluster_summary.pipeline import ClusterSummaryPipeline

pipeline = ClusterSummaryPipeline(
    package_name = "com.netease.cloudmusic.hm",
    graph_path="C:\\Projects\\AndroidTaskAutomation\\3_context_summarization\\utg\\NetEase Cloud Music"
)

pipeline.run()
