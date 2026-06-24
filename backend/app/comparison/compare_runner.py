from backend.app.comparison.answer_scorer import choose_winner
from backend.app.pipeline import PatentAccuracyRAGPipeline


class CompareRunner:
    def __init__(self):
        self.pipeline = PatentAccuracyRAGPipeline()

    def compare(self, question: str, document_id: str | None = None, top_k: int | None = None) -> dict:
        graph = self.pipeline.answer(question, top_k=top_k, document_id=document_id, method='graph')
        sprout = self.pipeline.answer(question, top_k=top_k, document_id=document_id, method='sprout')
        comparison = choose_winner(graph, sprout)
        return {
            'graph_rag': graph,
            'sprout_rag': sprout,
            **comparison,
        }
