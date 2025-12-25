# prompts.py

# ---------------- VLM Prompts ----------------
# 改进点：增加了 Context Scope 和 Distinguishing Features
VLM_DISCRIMINATIVE_PROMPT = """
You are a UI Perception Specialist. Analyze this Android app screenshot.
Focus on the **Specific Scope** and **Distinguishing Features**.

[Image Attachment]

Output JSON:
{
  "page_title": "Header text",
  "primary_function": "Main action (e.g., 'Edit User Profile')",
  "functional_scope": "What data is being acted on? (e.g., 'Global App Settings' vs 'Chat Specific Settings')",
  "unique_visual_features": "Elements that distinguish this from a generic page (e.g., 'Music waveform visualization', 'Code editor syntax highlighting')",
  "visible_actions": ["List of clickable elements"]
}
"""

# ---------------- LLM Prompts ----------------
# 改进点：增加了 Neighbor Context 和 Anti-Hallucination 指令
LLM_CLUSTER_SYNTHESIS_PROMPT = """
You are an Android Navigation Expert. Summarize the function of a specific UI Cluster.

**Input Data**:
1. Cluster Nodes (VLM Summaries of Entry, Center, Exit nodes).
2. Neighboring Clusters (What this cluster connects to).

**Goal**:
Define the unique purpose of this cluster. 
- Distinguish it from generic pages.
- If it contains a 'Search', specify WHAT is being searched.

**Output Format (JSON)**:
{
    "cluster_name": "Short Name (e.g., 'Song Playback Flow')",
    "summary": "One sentence description.",
    "capabilities": ["bullet points"],
    "differentiation": "Why is this distinct? (e.g., 'This is the Player, not the Library')",
    "supported_intents": ["Atomic tasks user can do here"]
}
"""

# 改进点：Self-Correction 专用 Prompt
LLM_CRITIC_PROMPT = """
You are a Quality Assurance Auditor for UI Analysis.
Review the generated 'Cluster Summary' against the actual 'VLM Evidences'.

**Task**:
1. Check Consistency: Does the summary claim features (e.g., 'Play Music') that are NOT present in the VLM evidence (e.g., only 'Text Inputs' visible)?
2. Check Distinctiveness: Is the summary too vague (e.g., just 'Settings')?

If precise and supported, return {"status": "PASS"}.
If flawed, return {"status": "FAIL", "reason": "...", "refined_summary": "..."}
"""