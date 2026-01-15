# prototypes/base.py

class FunctionalPrototype:
    """
    Cross-application functional abstraction.

    A prototype describes:
    - What function the app likely supports
    - How confident we are that this function exists
    - What task-level guidance it can generate
    """

    name: str

    def match(self, tig: "TIGQuery") -> float:
        """
        Estimate how well this prototype matches the given TIG.

        Returns:
            A score in [0, 1], representing confidence.
        """
        ...

    def required_signals(self) -> list[str]:
        """
        Declare which TIG-level signals are essential
        for this prototype to be valid.
        """
        ...

    def to_task_spec(self) -> dict:
        """
        Convert this prototype into a task specification
        consumable by the Task Generator.
        """
        ...


