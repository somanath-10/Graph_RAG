import unittest

from backend.app.shared_retrieval.bm25_retriever import BM25Retriever
from backend.app.shared_retrieval.exact_matcher import ExactMatcher
from backend.app.shared_retrieval.fusion import reciprocal_rank_fusion


SOURCE_UNITS = [
    {
        'source_id': 'doc_p1_claim_1',
        'chunk_id': 'doc_p1_claim_1',
        'document_id': 'doc',
        'unit_type': 'claim',
        'text': '1. A method comprising contacting a Pd catalyst with a reactant.',
        'page_start': 1,
        'page_end': 1,
        'section': 'Claims',
        'claim_number': 1,
        'example_number': None,
    },
    {
        'source_id': 'doc_p2_example_3',
        'chunk_id': 'doc_p2_example_3',
        'document_id': 'doc',
        'unit_type': 'example',
        'text': 'Example 3 shows the Pd catalyst improved conversion to 95%.',
        'page_start': 2,
        'page_end': 2,
        'section': 'Examples',
        'claim_number': None,
        'example_number': 3,
    },
]


class SharedRetrievalTests(unittest.TestCase):
    def test_exact_match_finds_claim_number(self):
        results = ExactMatcher(SOURCE_UNITS).search('What does claim 1 say?')
        self.assertEqual(results[0]['source_id'], 'doc_p1_claim_1')

    def test_bm25_finds_lexical_match(self):
        results = BM25Retriever(SOURCE_UNITS).search('improved conversion', top_k=1)
        self.assertEqual(results[0]['source_id'], 'doc_p2_example_3')

    def test_rrf_merges_duplicate_sources(self):
        fused = reciprocal_rank_fusion([[SOURCE_UNITS[0]], [SOURCE_UNITS[0], SOURCE_UNITS[1]]], limit=3)
        self.assertEqual(len(fused), 2)
        self.assertEqual(fused[0]['source_id'], 'doc_p1_claim_1')


if __name__ == '__main__':
    unittest.main()
