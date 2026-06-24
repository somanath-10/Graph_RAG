from backend.app.llm.openai_client import OpenAIClient
from backend.app.config import get_settings
from backend.app.config_loader import load_text_file
from backend.app.generation.citation_validator import CitationValidator


class AnswerGenerator:
    def __init__(self):
        self.settings = get_settings()
        self.client = OpenAIClient()
        self.system_prompt = load_text_file(self.settings.answer_system_prompt_path)
        self.user_template = load_text_file(self.settings.answer_user_prompt_path)
        self.validator = CitationValidator()

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

    def generate_grounded(
        self,
        question: str,
        evidence: list[dict],
        method: str,
        facts: list[dict] | None = None,
    ) -> dict:
        if not evidence and not facts:
            return self._insufficient(method, evidence, self.settings.no_evidence_answer)

        chunks = []
        for item in evidence:
            source_id = item.get('source_id') or item.get('chunk_id')
            chunks.append({
                'chunk_id': source_id,
                'source_id': source_id,
                'page_start': item.get('page_start'),
                'section': item.get('section'),
                'text': item.get('text'),
            })
        answer = self.generate(question, chunks, facts or [])
        validation = self.validator.validate(answer, evidence)

        if not validation['valid'] and not self.settings.use_mock_openai:
            retry_chunks = []
            for item in chunks:
                retry_chunks.append({
                    **item,
                    'text': (
                        f"Use citation [{item.get('source_id')}] for any fact from this evidence. "
                        f"{item.get('text') or ''}"
                    ),
                })
            answer = self.generate(question, retry_chunks, facts or [])
            validation = self.validator.validate(answer, evidence)

        if not validation['valid']:
            answer = self._extractive_answer(question, evidence, method)
            validation = self.validator.validate(answer, evidence)

        return {
            'method': method,
            'answer': answer,
            'claims': self._claims_from_answer(answer, validation),
            'sources': evidence,
            'insufficient_evidence': not bool(evidence),
            'citation_validation': validation,
        }

    def _extractive_answer(self, question: str, evidence: list[dict], method: str) -> str:
        if not evidence:
            return self.settings.insufficient_citation_answer
        import re

        lines = []
        for item in evidence[:3]:
            source_id = item.get('source_id')
            text = (item.get('text') or '').strip().replace('\n', ' ')
            text = re.sub(r'(?<=[.!?])\s+', '; ', text)
            if len(text) > 420:
                text = f'{text[:417]}...'
            page = item.get('page_start') or '?'
            section = item.get('section') or 'section'
            lines.append(f'{text} [{source_id}] (page {page}, {section})')
        return '\n'.join(lines)

    def _claims_from_answer(self, answer: str, validation: dict) -> list[dict]:
        claims = []
        cited = validation.get('cited_source_ids') or []
        for sentence in [s.strip() for s in answer.split('\n') if s.strip()]:
            source_ids = [source_id for source_id in cited if f'[{source_id}]' in sentence]
            if source_ids:
                claims.append({'claim': sentence, 'source_ids': source_ids, 'confidence': validation.get('citation_precision', 0.0)})
        return claims

    def _insufficient(self, method: str, evidence: list[dict], answer: str) -> dict:
        validation = self.validator.validate(answer, evidence)
        return {
            'method': method,
            'answer': answer,
            'claims': [],
            'sources': evidence,
            'insufficient_evidence': True,
            'citation_validation': validation,
        }
