class Task:
    goal: Dict
    success_criteria: Dict
    preferred_actions: List[str]
    forbidden_states: List[str]



# 音乐App的例子：
# Task(
#     goal={"play_music": True},
#     success_criteria={"audio_playing": True},
#     preferred_actions=["search", "play"],
#     forbidden_states=["login_required"]
# )