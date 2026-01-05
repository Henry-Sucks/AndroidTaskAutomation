You are a system architect designing a Task Intent Graph (TIG) for a GUI Agent.
Input 1: A list of Functional Clusters from a raw User Transition Graph (UTG).
Input 2: Connections between these clusters observed in the UTG.

**Goal:**
Construct a high-level TIG that represents the *business logic* flow, independent of specific UI widgets.

**Rules:**
1. **Merge Redundancy:** If multiple clusters serve the same core intent (e.g., "Home Page" and "Genre List" both serve "Discovery"), merge them into one TIG Node (e.g., "Discovery_State").
2. **Abstract Actions:** Label the edges with the user's intent (e.g., "Confirm", "Select_Item", "Search"), not "Click".
3. **Ignore Noise:** Ignore back-buttons, ads, or login interruptions unless they are critical flows.

**Input Data:**
Clusters:
- Cluster_01: Music Player Interface (Play, Pause, Seek)
- Cluster_02: Search Results List
- Cluster_03: Home Page Recommendations
- Cluster_04: Artist Profile (similar to Home Page, just list of songs)

Connections:
- Cluster_03 -> Cluster_02 (via Search Bar)
- Cluster_02 -> Cluster_01 (via Song Click)
- Cluster_03 -> Cluster_04 (via Artist Icon)
- Cluster_04 -> Cluster_01 (via Song Click)

**Output Format (JSON):**
Produce the TIG nodes and edges.