from backend.app.llm.openai_client import OpenAIClient
from backend.app.config import get_settings
from backend.app.config_loader import load_text_file


class AnswerGenerator:
    def __init__(self):
        self.settings = get_settings()
        self.client = OpenAIClient()
        self.system_prompt = load_text_file(self.settings.answer_system_prompt_path)
        self.user_template = load_text_file(self.settings.answer_user_prompt_path)

    def generate(self, question: str, chunks: list[dict], facts: list[dict]) -> str:
        if not chunks and not facts:
            return self.settings.no_evidence_answer

        chunk_text = []
        for c in chunks:
            chunk_text.append(
                f"chunk_id={c.get('chunk_id')} page={c.get('page_start')} section={c.get('section')}\n"
                f"{(c.get('text', '') or '')[: self.settings.answer_chunk_text_chars]}"
            )
        fact_text = []
        for f in facts[: self.settings.answer_fact_limit]:
            fact_text.append(
                f"{f.get('source')} -[{f.get('relation')}]-> {f.get('target')} | "
                f"page={f.get('page')} | evidence={f.get('evidence')}"
            )
        prompt = self.user_template.format(
            question=question,
            chunks='\n\n---\n'.join(chunk_text),
            facts='\n'.join(fact_text),
        )
        return self.client.text(prompt, self.system_prompt, max_output_tokens=self.settings.answer_max_output_tokens)
