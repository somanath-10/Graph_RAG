import os

import requests


API = os.getenv('API_BASE', 'http://localhost:8000/api')
API_KEY = os.getenv('API_KEY')
API_KEY_HEADER = os.getenv('API_KEY_HEADER', 'X-API-Key')
HEADERS = {API_KEY_HEADER: API_KEY} if API_KEY else {}

print('health:', requests.get(f'{API}/health', timeout=10).json())
print('graph:', requests.get(f'{API}/graph', headers=HEADERS, timeout=10).status_code)
print('Run ingestion from the UI or with: python scripts/run_ingest.py')
