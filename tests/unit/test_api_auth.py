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


if __name__ == '__main__':
    unittest.main()
