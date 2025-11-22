import json

from loader import ClusterDataLoader
from sampler import ClusterSampler
from summarizer import ImageSummarizer

class ClusterSummaryPipeline:
    def __init__(self, cluster_info_path, utg_clustered_path, image_root):
        self.loader = ClusterDataLoader(cluster_info_path, utg_clustered_path, image_root)
        self.sampler = ClusterSampler(self.loader)
        self.summarizer = ImageSummarizer()

    def run(self, output_path="output/cluster_summaries.json"):
        summaries = {}

        for cid in self.loader.get_cluster_ids():
            cluster = self.loader.get_cluster(cid)

            entry = cluster["entry_points"]
            exit_ = cluster["exit_points"]
            center = cluster["center_point"]

            sample_nodes = self.sampler.get_sample_nodes(cluster)

            points = {
                "entry_points": entry,
                "exit_points": exit_,
                "center_point": center,
                "sample_nodes": sample_nodes
            }

            descriptions = {}

            # 针对每个 point → node → image → VLM
            for key, node_ids in points.items():
                descriptions[key] = []

                for nid in node_ids:
                    node = self.loader.get_node(nid)
                    if not node:
                        continue

                    img = self.mapper.node_to_image_path(node)
                    if not img:
                        continue

                    text = self.summarizer.summarize(img, extra_note=f"Point type: {key}")
                    descriptions[key].append({
                        "node_id": nid,
                        "image": img,
                        "description": text
                    })

            summaries[cid] = descriptions

        # 保存结果
        with open(output_path, "w") as f:
            json.dump(summaries, f, indent=2)

        print(f"Saved cluster summaries → {output_path}")
