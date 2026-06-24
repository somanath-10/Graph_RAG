from backend.app.shared_retrieval.bm25_retriever import tokenize


class SproutBeamSearch:
    def __init__(self, nodes: list[dict]):
        self.nodes = nodes
        self.by_id = {node['node_id']: node for node in nodes}

    def search(self, question: str, beam_width: int = 6, limit: int = 18) -> list[dict]:
        query_terms = set(tokenize(question))
        if not query_terms:
            return []
        roots = [node for node in self.nodes if node.get('parent_id') is None]
        frontier = roots or self.nodes[:1]
        visited = set()
        selected = []

        while frontier and len(selected) < limit:
            ranked = sorted(frontier, key=lambda node: self._score(node, query_terms), reverse=True)
            next_frontier = []
            for node in ranked[:beam_width]:
                node_id = node['node_id']
                if node_id in visited:
                    continue
                visited.add(node_id)
                scored = dict(node)
                scored['score'] = self._score(node, query_terms)
                if scored['score'] > 0:
                    selected.append(scored)
                for child_id in node.get('child_ids') or []:
                    child = self.by_id.get(child_id)
                    if child:
                        next_frontier.append(child)
            frontier = next_frontier

        selected.sort(key=lambda node: node.get('score', 0), reverse=True)
        return selected[:limit]

    def _score(self, node: dict, query_terms: set[str]) -> float:
        terms = set(tokenize(node.get('text') or ''))
        if not terms:
            return 0.0
        overlap = len(query_terms & terms)
        level_bonus = {'section': 0.2, 'paragraph': 0.6, 'claim': 0.8, 'example': 0.8, 'sentence': 0.5}.get(node.get('level'), 0.0)
        return overlap + level_bonus
