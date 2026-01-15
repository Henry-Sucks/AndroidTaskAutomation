class TaskGenerator:
    def generate(self, tig, prototypes):
        matched = []
        for p in prototypes:
            score = p.match(tig)
            if score > 0.6:
                matched.append((p, score))

        return [self._instantiate(p, tig) for p, _ in matched]
    

    def _instantiate(self, prototype, tig):
        return Task(
            goal=prototype.success_signal,
            success_criteria=prototype.success_signal,
            preferred_actions=prototype.action_pattern
        )
