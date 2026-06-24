from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8', extra='ignore')

    app_name: str = 'Patent Accuracy RAG'
    environment: str = 'dev'
    api_key: str | None = None
    api_key_header: str = 'X-API-Key'
    require_api_key: bool = False

    openai_api_key: str | None = None
    openai_small_model: str = 'gpt-5.4-mini'
    openai_embedding_model: str = 'text-embedding-3-small'
    embedding_dimensions: int = 1536

    qdrant_url: str = 'http://localhost:6333'
    qdrant_collection: str = 'patent_chunks'
    qdrant_distance: str = 'COSINE'

    neo4j_uri: str = 'bolt://localhost:7687'
    neo4j_user: str = 'neo4j'
    neo4j_password: str = 'password'

    cors_origins: str = 'http://localhost:5173,http://localhost:5177,http://localhost:3000,http://127.0.0.1:5173,http://127.0.0.1:5177'

    data_dir: str = 'data'
    raw_dir: str = 'data/raw'
    processed_dir: str = 'data/processed'
    index_dir: str = 'data/indexes'
    document_registry_path: str = 'data/processed/documents.json'
    sample_pdf_filename: str | None = None
    max_upload_bytes: int = 50 * 1024 * 1024

    section_patterns_path: str = 'config/section_patterns.json'
    normalizer_replacements_path: str = 'config/normalizer_replacements.json'
    retrieval_terms_path: str = 'config/retrieval_terms.json'
    graph_schema_path: str = 'config/graph_schema.json'

    chunk_max_words: int = 420
    chunk_overlap_words: int = 60
    min_chunk_words: int = 5
    min_claim_words: int = 8
    min_paragraph_words: int = 8
    sentence_split_min_chars: int = 24
    claim_section_name: str = 'Claims'
    body_section_name: str = 'Body'
    chunk_id_width: int = 4

    reset_vector_store_on_ingest: bool = True
    reset_graph_store_on_ingest: bool = True

    default_query_top_k: int = 12
    max_query_top_k: int = 50
    default_graph_limit: int = 150
    max_graph_limit: int = 500
    vector_source_unit_types: str = 'claim,example,paragraph'
    bm25_top_k_multiplier: int = 3
    exact_match_limit: int = 12
    sprout_beam_width: int = 6
    sprout_tree_candidate_limit: int = 18
    sprout_store_filename: str = 'sprout_nodes.json'
    max_graph_chunks: int = 25
    max_answer_contexts: int = 8
    min_answer_contexts: int = 2
    fallback_to_top_contexts_when_empty: bool = True
    graph_fact_limit: int = 40
    retrieval_term_limit: int = 12
    graph_priority_sections: str = 'Claims,Examples,Abstract,Summary,Detailed Description'

    context_candidate_chars: int = 900
    context_relevance_threshold: float = 0.25
    context_default_keep_relevance: int = 3
    context_default_drop_relevance: int = 1
    context_eval_max_output_tokens: int = 1200

    graph_chunk_text_chars: int = 8000
    graph_extraction_max_output_tokens: int = 1800

    answer_chunk_text_chars: int = 1800
    answer_fact_limit: int = 30
    answer_max_output_tokens: int = 1400

    default_text_max_output_tokens: int = 1200
    default_json_max_output_tokens: int = 1800
    parse_json_preview_chars: int = 500
    mock_answer_text: str = 'Mock answer. Set USE_MOCK_OPENAI=false and provide OPENAI_API_KEY for real answers.'
    no_evidence_answer: str = 'I do not have enough evidence in the retrieved patent context to answer that exactly.'
    insufficient_citation_answer: str = 'I do not have enough cited evidence in the retrieved patent context to answer that exactly.'

    context_eval_system_prompt_path: str = 'backend/app/prompts/context_eval_system.txt'
    context_eval_user_prompt_path: str = 'backend/app/prompts/context_eval_user.txt'
    graph_extraction_system_prompt_path: str = 'backend/app/prompts/graph_extraction_system.txt'
    graph_extraction_user_prompt_path: str = 'backend/app/prompts/graph_extraction_user.txt'
    answer_system_prompt_path: str = 'backend/app/prompts/answer_system.txt'
    answer_user_prompt_path: str = 'backend/app/prompts/answer_user.txt'

    use_mock_openai: bool = False

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(',') if origin.strip()]

    @property
    def api_key_required(self) -> bool:
        return self.require_api_key or self.environment.lower() in {'prod', 'production'}

    @property
    def section_pattern_list(self) -> list[tuple[str, str]]:
        from backend.app.config_loader import load_json_file

        data = load_json_file(self.section_patterns_path)
        return [
            (str(item['name']), str(item['pattern']))
            for item in data
            if isinstance(item, dict) and item.get('name') and item.get('pattern')
        ]

    @property
    def normalizer_replacements(self) -> dict[str, str]:
        from backend.app.config_loader import load_json_file

        data = load_json_file(self.normalizer_replacements_path)
        return {str(k): str(v) for k, v in data.items()}

    @property
    def retrieval_seed_terms(self) -> list[str]:
        from backend.app.config_loader import load_json_file

        data = load_json_file(self.retrieval_terms_path)
        terms = data.get('seed_terms', data.get('chemical_hints', []))
        return [str(item) for item in terms]

    @property
    def retrieval_keywords(self) -> list[str]:
        from backend.app.config_loader import load_json_file

        data = load_json_file(self.retrieval_terms_path)
        return [str(item) for item in data.get('keywords', [])]

    @property
    def graph_allowed_type_list(self) -> list[str]:
        from backend.app.config_loader import load_json_file

        data = load_json_file(self.graph_schema_path)
        return [str(item) for item in data.get('allowed_entity_types', [])]

    @property
    def graph_allowed_relation_list(self) -> list[str]:
        from backend.app.config_loader import load_json_file

        data = load_json_file(self.graph_schema_path)
        return [str(item) for item in data.get('allowed_relationship_labels', [])]

    @property
    def graph_default_entity_type(self) -> str:
        from backend.app.config_loader import load_json_file

        data = load_json_file(self.graph_schema_path)
        return str(data.get('default_entity_type', 'EvidenceChunk'))

    @property
    def graph_default_relation(self) -> str:
        from backend.app.config_loader import load_json_file

        data = load_json_file(self.graph_schema_path)
        return str(data.get('default_relationship_label', 'SUPPORTS'))

    @property
    def graph_priority_section_list(self) -> list[str]:
        return [section.strip() for section in self.graph_priority_sections.split(',') if section.strip()]

    @property
    def vector_source_unit_type_list(self) -> list[str]:
        return [item.strip() for item in self.vector_source_unit_types.split(',') if item.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
