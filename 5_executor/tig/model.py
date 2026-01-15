# tig/model.py
from typing import List, Dict


class TIGNode:
    """
    Represents a functional UI state in the TIG.

    Attributes:
        id:
            Unique TIG node identifier (e.g., 'TIG_SEARCH_MODE')

        intent_label:
            High-level functional intent of this UI state
            (e.g., 'Search_Mode', 'Playback_Control')

        ui_description:
            Natural language description of the UI and its purpose

        capabilities:
            List of abstracted user-performable actions or functions
            exposed by this UI state
            (e.g., 'Search_Music', 'Play_Song', 'Navigate_Settings')
    """
    ...


class TIGEdge:
    """
    Represents a directed transition between two TIG nodes.

    Attributes:
        source:
            Source TIG node id

        target:
            Target TIG node id

        action:
            Abstracted action triggering the transition
            (e.g., 'Play(song)', 'Navigate(Settings)')

        description:
            Natural language explanation of the user's intent
            behind this transition
    """
    ...


class TIGGraph:
    """
    Graph-level container for all TIG nodes and edges.

    Responsibilities:
    - Store nodes and edges
    - Provide basic structural access (neighbors, node lookup)
    - Remain *policy-agnostic*
    """

    nodes: Dict[str, TIGNode]
    edges: List[TIGEdge]

    def get_node(self, node_id: str) -> TIGNode:
        """
        Retrieve a TIG node by id.
        """
        ...

    def outgoing_edges(self, node_id: str) -> List[TIGEdge]:
        """
        Get all outgoing edges from a given TIG node.
        """
        ...

    def incoming_edges(self, node_id: str) -> List[TIGEdge]:
        """
        Get all incoming edges to a given TIG node.
        """
        ...
