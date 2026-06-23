from backend.app.llm.openai_client import OpenAIClient


class Embedder:
    def __init__(self):
        self.client = OpenAIClient()

    def embed_chunks(self, chunks: list[dict], batch_size: int = 64) -> list[dict]:
        out = []
        for i in range(0, len(chunks), batch_size):
            batch = chunks[i:i + batch_size]
            vectors = self.client.embed([c['text'] for c in batch])
            for chunk, vector in zip(batch, vectors):
                item = dict(chunk)
                item['embedding'] = vector
                out.append(item)
        return out

    def embed_query(self, question: str) -> list[float]:
        return self.client.embed([question])[0]
