import re
from typing import Any
from neo4j import GraphDatabase

from backend.app.config import get_settings


def clean_type(entity_type: str, allowed_types: set[str], default_type: str) -> str:
    entity_type = re.sub(r'[^A-Za-z0-9]', '', entity_type or '')
    return entity_type if entity_type in allowed_types else default_type


def clean_relation(rel: str, allowed_relations: set[str], default_relation: str) -> str:
    rel = re.sub(r'[^A-Za-z0-9_]', '_', (rel or '').upper())
    return rel if rel in allowed_relations else default_relation


class Neo4jStore:
    def __init__(self):
        self.settings = get_settings()
        self.allowed_types = set(self.settings.graph_allowed_type_list)
        self.allowed_relations = set(self.settings.graph_allowed_relation_list)
        self.driver = GraphDatabase.driver(
            self.settings.neo4j_uri,
            auth=(self.settings.neo4j_user, self.settings.neo4j_password),
        )

    def close(self):
        self.driver.close()

    def reset(self):
        with self.driver.session() as session:
            session.run('MATCH (n) DETACH DELETE n')

    def upsert_graph(self, graph: dict[str, Any]):
        entities = graph.get('entities', []) or []
        relationships = graph.get('relationships', []) or []
        with self.driver.session() as session:
            for e in entities:
                name = str(e.get('name', '')).strip()
                if not name:
                    continue
                entity_type = clean_type(
                    str(e.get('type', self.settings.graph_default_entity_type)),
                    self.allowed_types,
                    self.settings.graph_default_entity_type,
                )
                props = e.get('properties') if isinstance(e.get('properties'), dict) else {}
                props.update({
                    'name': name,
                    'entity_type': entity_type,
                    'source_chunk_id': e.get('source_chunk_id'),
                    'page': e.get('page'),
                    'section': e.get('section'),
                })
                session.run('MERGE (n:GraphNode {name: $name}) SET n += $props', name=name, props=props)

            for r in relationships:
                source = str(r.get('source', '')).strip()
                target = str(r.get('target', '')).strip()
                if not source or not target:
                    continue
                rel = clean_relation(
                    str(r.get('relation', self.settings.graph_default_relation)),
                    self.allowed_relations,
                    self.settings.graph_default_relation,
                )
                props = {
                    'evidence': r.get('evidence', ''),
                    'source_chunk_id': r.get('source_chunk_id'),
                    'page': r.get('page'),
                    'section': r.get('section'),
                }
                cypher = f'''
                MERGE (a:GraphNode {{name: $source}})
                MERGE (b:GraphNode {{name: $target}})
                MERGE (a)-[rel:{rel}]->(b)
                SET rel += $props
                '''
                session.run(cypher, source=source, target=target, props=props)

    def search_facts(self, terms: list[str], limit: int | None = None) -> list[dict]:
        limit = limit or self.settings.graph_fact_limit
        if not terms:
            return []
        with self.driver.session() as session:
            result = session.run(
                '''
                MATCH (a:GraphNode)-[r]->(b:GraphNode)
                WHERE any(t IN $terms WHERE toLower(a.name) CONTAINS toLower(t)
                   OR toLower(b.name) CONTAINS toLower(t)
                   OR toLower(coalesce(r.evidence, '')) CONTAINS toLower(t))
                RETURN a.entity_type AS source_type, a.name AS source,
                       type(r) AS relation, b.entity_type AS target_type, b.name AS target,
                       r.evidence AS evidence, r.page AS page, r.source_chunk_id AS chunk_id
                LIMIT $limit
                ''',
                terms=terms,
                limit=limit,
            )
            return [dict(record) for record in result]

    def graph_snapshot(self, limit: int | None = None) -> dict:
        limit = limit or self.settings.default_graph_limit
        with self.driver.session() as session:
            result = session.run(
                '''
                MATCH (a:GraphNode)-[r]->(b:GraphNode)
                RETURN id(a) AS source_id, a.name AS source, a.entity_type AS source_type,
                       id(b) AS target_id, b.name AS target, b.entity_type AS target_type,
                       type(r) AS relation, r.evidence AS evidence
                LIMIT $limit
                ''',
                limit=limit,
            )
            nodes = {}
            edges = []
            for rec in result:
                sid = str(rec['source_id'])
                tid = str(rec['target_id'])
                nodes[sid] = {'id': sid, 'name': rec['source'], 'type': rec['source_type'] or 'GraphNode'}
                nodes[tid] = {'id': tid, 'name': rec['target'], 'type': rec['target_type'] or 'GraphNode'}
                edges.append({
                    'source': sid,
                    'target': tid,
                    'relation': rec['relation'],
                    'evidence': rec['evidence'],
                })
            return {'nodes': list(nodes.values()), 'edges': edges}
