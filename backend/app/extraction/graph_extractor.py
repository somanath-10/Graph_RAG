from backend.app.llm.openai_client import OpenAIClient
from backend.app.config import get_settings
from backend.app.config_loader import load_text_file


class GraphExtractor:
    def __init__(self):
        self.settings = get_settings()
        self.client = OpenAIClient()
        self.system_prompt = load_text_file(self.settings.graph_extraction_system_prompt_path)
        self.user_template = load_text_file(self.settings.graph_extraction_user_prompt_path)

    def extract_from_chunk(self, chunk: dict) -> dict:
        prompt = self.user_template.format(
            allowed_entity_types=', '.join(self.settings.graph_allowed_type_list),
            allowed_relationship_labels=', '.join(self.settings.graph_allowed_relation_list),
            chunk_id=chunk.get('chunk_id'),
            page=chunk.get('page_start'),
            section=chunk.get('section'),
            text=(chunk.get('text', '') or '')[: self.settings.graph_chunk_text_chars],
        )
        data = self.client.json(prompt, self.system_prompt, max_output_tokens=self.settings.graph_extraction_max_output_tokens)
        if not isinstance(data, dict):
            return {'entities': [], 'relationships': []}
        data.setdefault('entities', [])
        data.setdefault('relationships', [])
        for e in data['entities']:
            e.setdefault('properties', {})
            e['source_chunk_id'] = chunk.get('chunk_id')
            e['source_unit_ids'] = chunk.get('source_unit_ids', [])
            e['document_id'] = chunk.get('document_id')
            e['page'] = chunk.get('page_start')
            e['section'] = chunk.get('section')
        for r in data['relationships']:
            r['source_chunk_id'] = chunk.get('chunk_id')
            r['source_unit_ids'] = chunk.get('source_unit_ids', [])
            r['document_id'] = chunk.get('document_id')
            r['page'] = chunk.get('page_start')
            r['section'] = chunk.get('section')
        return data

    def select_chunks(self, chunks: list[dict], max_chunks: int | None = None) -> list[dict]:
        if max_chunks is None:
            return chunks
        selected = []
        selected_ids = set()
        grouped = {
            section: [chunk for chunk in chunks if chunk.get('section') == section]
            for section in self.settings.graph_priority_section_list
        }
        while len(selected) < max_chunks:
            added = False
            for section in self.settings.graph_priority_section_list:
                bucket = grouped.get(section) or []
                if not bucket:
                    continue
                chunk = bucket.pop(0)
                if chunk.get('chunk_id') in selected_ids:
                    continue
                selected.append(chunk)
                selected_ids.add(chunk.get('chunk_id'))
                added = True
                if len(selected) >= max_chunks:
                    return selected
            if not added:
                break
        for chunk in chunks:
            if chunk.get('chunk_id') in selected_ids:
                continue
            selected.append(chunk)
            selected_ids.add(chunk.get('chunk_id'))
            if len(selected) >= max_chunks:
                return selected
        return selected

    def extract(self, chunks: list[dict], max_chunks: int | None = None) -> dict:
        selected = self.select_chunks(chunks, max_chunks=max_chunks)
        all_entities = []
        all_relationships = []
        for chunk in selected:
            try:
                data = self.extract_from_chunk(chunk)
                all_entities.extend(data.get('entities', []))
                all_relationships.extend(data.get('relationships', []))
            except Exception as exc:
                print(f'Graph extraction failed for {chunk.get("chunk_id")}: {exc}')
        return {'entities': all_entities, 'relationships': all_relationships}
