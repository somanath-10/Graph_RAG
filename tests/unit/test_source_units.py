import unittest

from backend.app.ingest.normalizer import normalize_patent_text
from backend.app.ingest.source_units import build_source_units
from backend.app.sprout_rag.tree_builder import build_sprout_tree


class SourceUnitTests(unittest.TestCase):
    def test_builds_claim_and_sentence_units(self):
        pages = [{
            'page': 1,
            'text': 'Claims\n1. A method comprising heating a catalyst. The method improves yield.\n2. The method of claim 1, wherein the catalyst is Pd.'
        }]
        units = build_source_units(pages, document_id='doc_test', section_patterns=[('Claims', r'\bClaims\b')])
        claim_units = [u for u in units if u['unit_type'] == 'claim']
        sentence_units = [u for u in units if u['unit_type'] == 'sentence']
        self.assertEqual([u['claim_number'] for u in claim_units], [1, 2])
        self.assertTrue(sentence_units)
        self.assertTrue(all(u['source_id'] for u in units))

    def test_sprout_tree_links_to_source_units(self):
        pages = [{'page': 1, 'text': 'Abstract\nA catalyst improves conversion. It reduces energy use.'}]
        units = build_source_units(pages, document_id='doc_tree', section_patterns=[('Abstract', r'\bAbstract\b')])
        nodes = build_sprout_tree(units, document_id='doc_tree')
        self.assertTrue(any(n['level'] == 'document' for n in nodes))
        self.assertTrue(any(n['source_unit_ids'] for n in nodes if n['level'] != 'document'))

    def test_normalizer_preserves_paragraph_boundaries(self):
        text = normalize_patent_text('Abstract\n\nA catalyst.  It works.\n\nClaims\n1. A method.')
        self.assertIn('\n\n', text)
        self.assertIn('Claims\n1.', text)


if __name__ == '__main__':
    unittest.main()
