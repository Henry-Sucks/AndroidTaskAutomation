from clients.llm_client import LLMClient
import json

PROMPT_TEMPLATE = """
            You are an expert in Android UI state analysis.You will be given VLM-generated summaries of UI nodes inside a cluster 
            (entry points, exit points, center node, and sampled nodes). 
            Your task is to infer the overall function and purpose of this cluster.\n\n
            Please produce the following structured output:\n
            1. **Cluster Overall Function (one concise sentence)**\n
            2. **Key Functional Capabilities** (3–8 bullet points)\n
            3. **Representative Page Types** (what UI pages appear in this cluster)\n
            4. **Likely User Tasks** (what a user is trying to accomplish inside this cluster)\n
            5. **Reasoning Evidence** (cite clues extracted from entry/exit/center/sample nodes)\n\n
            Below is the JSON containing node summaries:\n
            """

class LLMSummarizer:
    def __init__(self, model="deepseek-chat"):
        self.client = LLMClient(model)


    def _build_cluster_prompt_en(self, results):
        """
        Build the English prompt for cluster summarization.
        The model will reason over entry_points, exit_points,
        center_point, and sample_nodes from VLM summaries.
        """

        prompt_parts = []

        prompt_parts.append(
            PROMPT_TEMPLATE
        )

        prompt_parts.append(json.dumps(results, ensure_ascii=False, indent=2))

        return "\n".join(prompt_parts)


    def summarize_cluster(self, results):
        """
        Summarize cluster functionality using the LLMClient defined in llm_client.py.
        """

        prompt = self._build_cluster_prompt_en(results)

        system_prompt = (
            "You are a highly skilled Android UI/UX workflow analysis assistant. "
            "You understand user flows, UI navigation, and app-level functionality."
        )

        # use the LLM client to run inference
        response = self.client.run(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=0.2
        )

        return response