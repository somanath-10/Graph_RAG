import unittest

from backend.app.comparison.answer_scorer import score_answer


class AnswerScorerTests(unittest.TestCase):
    def test_citation_quality_beats_raw_evidence_count(self):
        well_cited = score_answer({
            'citation_validation': {
                'citation_precision': 1.0,
                'unsupported_claim_count': 0,
            },
            'sources': [{'retrieval_channel': 'bm25'}],
            'latency_ms': 100,
        })
        many_uncited_sources = score_answer({
            'citation_validation': {
                'citation_precision': 0.0,
                'unsupported_claim_count': 0,
            },
            'sources': [{'retrieval_channel': 'bm25'} for _ in range(12)],
            'latency_ms': 100,
        })

        self.assertGreater(well_cited['score'], many_uncited_sources['score'])


if __name__ == '__main__':
    unittest.main()
