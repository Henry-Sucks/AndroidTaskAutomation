# tig/loader.py

def load_tig(path: str) -> "TIGGraph":
    """
    Load a TIG from a tig.json file.

    Responsibilities:
    - Parse nodes and edges from JSON
    - Construct a TIGGraph instance
    - Perform basic schema validation (optional)

    Args:
        path: Path to tig.json

    Returns:
        TIGGraph: in-memory representation of the TIG
    """
    ...