import os

import requests


API = os.getenv('API_BASE', 'http://localhost:8000/api')
print('health:', requests.get(f'{API}/health', timeout=10).json())
print('Run ingestion from the UI or with: python scripts/run_ingest.py')
