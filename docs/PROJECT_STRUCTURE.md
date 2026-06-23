# Project structure

```text
patent-graphrag-openai-react/
|-- config/
|   |-- graph_schema.json
|   |-- normalizer_replacements.json
|   |-- retrieval_terms.json
|   `-- section_patterns.json
|-- backend/
|   |-- Dockerfile
|   `-- app/
|       |-- main.py
|       |-- pipeline.py
|       |-- config.py
|       |-- schemas.py
|       |-- ingest/
|       |-- embedding/
|       |-- extraction/
|       |-- storage/
|       |-- retrieval/
|       |-- generation/
|       |-- prompts/
|       `-- llm/
|-- frontend/
|   |-- Dockerfile
|   |-- package.json
|   |-- vite.config.js
|   |-- index.html
|   `-- src/
|       |-- main.jsx
|       `-- styles.css
|-- data/
|   |-- raw/
|   |   `-- *.pdf
|   `-- processed/
|-- docs/
|   |-- PROJECT_STRUCTURE.md
|   `-- WORKFLOWS.md
|-- scripts/
|   |-- run_ingest.py
|   `-- smoke_test.py
|-- docker-compose.yml
|-- requirements.txt
|-- .env.example
|-- Makefile
`-- README.md
```
