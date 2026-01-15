from typing import List, Set
from tig.model import TIGGraph, TIGNode


class TIGQuery:
    """
    Prototype-facing query interface for TIG inspection.

    Design principles:
    - No exposure of raw graph structure
    - Queries describe *functional properties*, not UI details
    - Stable under TIG schema evolution
    """

    def __init__(self, tig: TIGGraph):
        """
        Bind this query interface to a specific TIG instance.
        """
        ...


    def all_intents(self) -> Set[str]:
        """
        Return all intent labels present in the TIG.
        """
        ...

    def all_capabilities(self) -> Set[str]:
        """
        Return the set of all capabilities across all TIG nodes.
        """
        ...

    def nodes_with_intent(self, intent_keyword: str) -> List[TIGNode]:
        """
        Return all nodes whose intent_label semantically matches
        the given keyword.
        """
        ...

    def nodes_with_capability(self, capability_keyword: str) -> List[TIGNode]:
        """
        Return all nodes exposing capabilities that match
        the given keyword.
        """
        ...


    def has_transition(
        self,
        source_capability: str,
        target_capability: str
    ) -> bool:
        """
        Check whether there exists a transition from a node exposing
        source_capability to a node exposing target_capability.

        Example:
            Search → Play
        """
        ...

    def has_intent_sequence(self, intents: List[str]) -> bool:
        """
        Check whether the TIG contains a path that matches
        a sequence of intent labels.

        Example:
            ['Search_Mode', 'Playback_Control']
        """
        ...


    def has_execution_state(self, execution_type: str) -> bool:
        """
        Check whether the TIG contains a state corresponding
        to an execution/runtime condition.

        Example execution types:
            - 'audio_playing'
            - 'media_paused'
            - 'content_exported'
        """
        ...

    def execution_states(self) -> List[TIGNode]:
        """
        Return all nodes that represent execution or runtime
        states (e.g., active playback).
        """
        ...


    def has_modal_states(self) -> bool:
        """
        Check whether the TIG contains modal/dialog-style UI states.
        """
        ...

    def has_navigation_cycles(self) -> bool:
        """
        Check whether the TIG contains cyclic navigation patterns,
        indicating returnable or reversible exploration paths.
        """
        ...

    def dominant_capabilities(self, top_k: int = 5) -> List[str]:
        """
        Return the most frequent capabilities in the TIG,
        useful for coarse functional profiling.
        """
        ...