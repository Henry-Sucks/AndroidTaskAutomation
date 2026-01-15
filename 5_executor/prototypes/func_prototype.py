# prototypes/base.py
from typing import List, Dict

class FunctionalPrototype:
    name: str
    intent: str  # 人类可读功能描述
    ui_signature: Dict
    action_pattern: List[str]
    success_signal: Dict

    def match(self, tig_subgraph) -> float:
        """返回 [0,1] 匹配分数"""
        raise NotImplementedError


class SearchAndPlay(FunctionalPrototype):
    name = "search_and_play"
    intent = "Search content and start playback"

    ui_signature = {
        "has_search_entry": True,
        "has_result_list": True,
        "has_play_button": True
    }

    action_pattern = [
        "click(search)",
        "input(text)",
        "click(result)",
        "click(play)"
    ]

    success_signal = {
        "audio_playing": True
    }

    def match(self, tig):
        score = 0
        if tig.has_widget_role("search"):
            score += 0.4
        if tig.has_list_like_transition():
            score += 0.3
        if tig.has_state_with_audio():
            score += 0.3
        return score
