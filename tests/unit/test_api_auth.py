import unittest

from fastapi.testclient import TestClient

from backend.app import main


class ApiAuthTests(unittest.TestCase):
    def test_health_public_but_graph_requires_key_when_enabled(self):
        old_required = main.settings.require_api_key
        old_key = main.settings.api_key
        try:
            main.settings.require_api_key = True
            main.settings.api_key = 'test-secret'
            client = TestClient(main.app)

            self.assertEqual(client.get('/api/health').status_code, 200)
            self.assertEqual(client.get('/api/graph').status_code, 401)
            self.assertNotEqual(
                client.get('/api/graph', headers={'X-API-Key': 'test-secret'}).status_code,
                401,
            )
        finally:
            main.settings.require_api_key = old_required
            main.settings.api_key = old_key


class GraphFallbackTests(unittest.TestCase):
    def test_json_snapshot_dedupes_entities_across_source_and_target_roles(self):
        old_store = main.DocumentStore

        class FakeDocumentStore:
            def latest_document(self):
                return {'document_id': 'doc_test'}

            def graph_path(self, document_id):
                return f'{document_id}_graph.json'

            def read_json(self, path, default=None):
                return {
                    'relationships': [
                        {'source': 'Alpha', 'target': 'Beta', 'relation': 'SUPPORTS', 'evidence': 'Alpha supports Beta.'},
                        {'source': 'Beta', 'target': 'Gamma', 'relation': 'SUPPORTS', 'evidence': 'Beta supports Gamma.'},
                    ]
                }

        try:
            main.DocumentStore = FakeDocumentStore
            snapshot = main.graph_snapshot_from_json(document_id=None, limit=10)
        finally:
            main.DocumentStore = old_store

        self.assertEqual(sorted(node['name'] for node in snapshot['nodes']), ['Alpha', 'Beta', 'Gamma'])
        self.assertEqual(len(snapshot['edges']), 2)
        self.assertEqual(
            snapshot['edges'][0]['target'],
            snapshot['edges'][1]['source'],
        )


if __name__ == '__main__':
    unittest.main()
