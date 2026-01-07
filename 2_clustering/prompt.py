prompt_for_node = """
**Role:**
You are an expert UI/UX Researcher and GUI Agent Planner.

**Task:**
Analyze the provided Android app screenshot and generate a structured functional description. This description will be used to build a "Task Intent Graph," so focus on **logic, intent, and interactivity** rather than purely visual aesthetics.

**Instructions:**
1.  **Macro Analysis (The "Where" & "Why"):** Identify the screen type and the user's primary goal here.
2.  **Micro Analysis (The "What"):** List key interactive components and, crucially, **infer their likely function** (what happens if clicked?).
3.  **Content Context:** Briefly describe the information being presented (e.g., "list of songs," "settings options").

**Output Format (JSON Only):**
```json
{
  "screen_type": "Brief label (e.g., Music Player, Search Results, Settings, Login Page)",
  "primary_intent": "What is the user trying to achieve here? (e.g., 'To control music playback' or 'To find a specific song')",
  "main_content": "Description of the central information (e.g., 'Album art for [Song Name] and lyrics view' or 'List of 10 daily recommended tracks')",
  "interactive_elements": [
    {
      "element_description": "Visual description (e.g., 'Magnifying glass icon in top bar')",
      "inferred_action": "Functionality (e.g., 'Opens search input mode')"
    },
    {
      "element_description": "Visual description (e.g., 'Central circular button with triangle')",
      "inferred_action": "Functionality (e.g., 'Toggles play/pause')"
    },
    // List top 5-7 most important elements
  ],
  "state_summary": "A concise, 1-sentence summary combining the screen type and main capabilities."
}
"""

prompt_for_edge = """
**Role:**
You are an expert GUI Agent Architect. Your goal is to analyze user interactions to build a "Task Intent Graph" (TIG).

**Input Data:**
1.  **Image:** A composite image containing two screenshots:
    * **LEFT (Pre-Action):** The state *before* the interaction. A **RED BOUNDING BOX** highlights the specific UI element the user interacted with.
    * **RIGHT (Post-Action):** The state *after* the interaction, showing the result.
2.  **Interaction Type:** `{interaction_type}` (e.g., click, scroll_down, input_text).

**Task:**
Analyze the semantic meaning of this transition. You must determine **what functionality was triggered** and **what the user's intent was**.

**Reasoning Steps:**
1.  **Identify the Target:** Look at the **RED BOX** in the Left image. Read any text inside or near it. Recognize the icon/widget type.
2.  **Analyze the Change:** Compare the Left and Right images. Did the screen change completely (Navigation)? Did a small part update (State Change)? Did a menu appear?
3.  **Infer the Intent:** Combine the *Target*, the *Interaction Type*, and the *Result* to define the business intent.

**Output Format (JSON Only):**
```json
{
  "target_element": {
    "type": "Widget type (e.g., Button, List Item, Tab, Search Bar)",
    "content": "Text or visual content inside the red box (e.g., 'Play All', 'Song Title', 'Magnifying Glass')"
  },
  "visual_delta": "Brief description of the visual difference between Left and Right (e.g., 'Navigated from playlist view to full-screen player' or 'A toggle switch turned green')",
  "transition_type": "Choose one: [NAVIGATION (New Page) | STATE_MUTATION (Same Page Update) | POPUP (Dialog/Menu) | NO_CHANGE]",
  "semantic_edge": {
    "action_verb": "High-level intent verb (e.g., Open, Play, Search, Toggle, Back, Submit)",
    "action_object": "The logical object being manipulated (e.g., 'Song', 'Settings', 'Search_Mode')",
    "function_signature": "A pseudo-code representation (e.g., Play(item_id), Navigate(Settings), Toggle(Shuffle))"
  },
  "intent_summary": "A concise sentence explaining the user's goal (e.g., 'User selects a specific song to start immediate playback')."
}
"""