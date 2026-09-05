# -*- coding: utf-8 -*-
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.abspath('.'))

from backend.extraction.evidence_grounder import EvidenceGrounder
from backend.extraction.mock_provider import MockLLMProvider
from backend.extraction.models import CandidateRequirement, ExtractionStatus, LLMMode
from backend.extraction.requirement_extractor import TenderRequirementExtractor
from backend.extraction.schema_validator import SchemaValidator
from backend.ingestion.models import (
    DocumentMetadata,
    ExtractedPage,
    ExtractionResult,
    TextBlock,
)


class TestExtractionRecallHardening(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.validator = SchemaValidator()
        cls.blocks_p1 = [
            TextBlock(block_id='BLK-001', page_number=1, text='EMD Required: No', raw_text='', bbox=[10.0, 10.0, 20.0, 200.0]),
            TextBlock(block_id='BLK-002', page_number=1, text='ePBG Detail: No', raw_text='', bbox=[25.0, 10.0, 35.0, 200.0]),
            TextBlock(block_id='BLK-003', page_number=1, text='Document required from seller: Compliance of BoQ specification and supporting document *In case any bidder is seeking exemption from Experience / Turnover Criteria, the supporting documents to prove his eligibility for exemption must be uploaded for evaluation by the buyer', raw_text='', bbox=[40.0, 10.0, 70.0, 500.0]),
            TextBlock(block_id='BLK-004', page_number=1, text='Any bidder from a country sharing a land border with India will be eligible to bid only if registered with Competent Authority. The bidder must undertake compliance with Clause 26; false declaration constitutes breach.', raw_text='', bbox=[80.0, 10.0, 110.0, 500.0]),
        ]
        cls.ext_res = ExtractionResult(
            document_id='DOC-TEST-RECALL',
            metadata=DocumentMetadata(
                document_id='DOC-TEST-RECALL',
                filename='test_recall.pdf',
                file_path='test_recall.pdf',
                file_size_bytes=1024,
                sha256='fakehash',
                page_count=1,
                tender_id='TENDER-TEST',
            ),
            pages=[ExtractedPage(page_number=1, width=600.0, height=800.0, text="", raw_text="", blocks=cls.blocks_p1)],
        )

    def test_01_negative_boolean_normalization(self):
        prov = MockLLMProvider()
        extractor = TenderRequirementExtractor(provider=prov)
        
        # Test No / false values
        norm_val, unit = extractor._normalize_expected_value('No', 'emd_required')
        self.assertFalse(norm_val)
        self.assertEqual(unit, 'BOOLEAN')

        norm_val, unit = extractor._normalize_expected_value('Not Required', 'epbg_required')
        self.assertFalse(norm_val)
        self.assertEqual(unit, 'BOOLEAN')

        norm_val, unit = extractor._normalize_expected_value('None', 'mii_preference')
        self.assertFalse(norm_val)
        self.assertEqual(unit, 'BOOLEAN')

        norm_val, unit = extractor._normalize_expected_value(False, 'relaxation_offered')
        self.assertFalse(norm_val)
        self.assertEqual(unit, 'BOOLEAN')

        # Test Yes / true values
        norm_val, unit = extractor._normalize_expected_value('Yes', 'iso_cert_required')
        self.assertTrue(norm_val)
        self.assertEqual(unit, 'BOOLEAN')

    def test_02_footnote_asterisk_decomposition(self):
        prov = MockLLMProvider()
        extractor = TenderRequirementExtractor(provider=prov)

        cand = CandidateRequirement(
            description='Compliance of BoQ specification and supporting document *In case any bidder is seeking exemption from Experience / Turnover Criteria, the supporting documents to prove his eligibility for exemption must be uploaded for evaluation by the buyer',
            category='TECHNICAL_SPECIFICATION',
            field='boq_and_exemption_proof',
            operator='EXISTS',
            expected_value='BoQ compliance and exemption documents',
            mandatory=True,
            evidence_block_ids=['BLK-003'],
        )

        decomposed = extractor._decompose_compound_candidates([cand])
        self.assertEqual(len(decomposed), 2)
        fields = [c.field for c in decomposed]
        self.assertIn('boq_compliance_document', fields)
        self.assertIn('exemption_supporting_documents', fields)
        for d in decomposed:
            self.assertEqual(d.requirement_type, 'BIDDER_COMPLIANCE')
            self.assertTrue(d.mandatory)

    def test_03_land_border_clause_decomposition(self):
        prov = MockLLMProvider()
        extractor = TenderRequirementExtractor(provider=prov)

        cand = CandidateRequirement(
            description='Land border registration and affirmative undertaking requirement under GeM GTC Clause 26 from competent authority',
            category='STATUTORY_ELIGIBILITY',
            field='land_border_mandate',
            operator='EXISTS',
            expected_value='Compliance with land border clause 26',
            mandatory=True,
            evidence_block_ids=['BLK-004'],
        )

        decomposed = extractor._decompose_compound_candidates([cand])
        self.assertEqual(len(decomposed), 2)
        fields = [c.field for c in decomposed]
        self.assertIn('land_border_registration', fields)
        self.assertIn('land_border_compliance_undertaking', fields)

    def test_04_merge_and_deduplicate_candidates(self):
        prov = MockLLMProvider()
        extractor = TenderRequirementExtractor(provider=prov)

        c1 = CandidateRequirement(
            description='Warranty requirement',
            category='COMMERCIAL_TERMS',
            field='warranty_years',
            operator='>=',
            expected_value='3 years',
            mandatory=False,
            evidence_block_ids=['BLK-001'],
            requirement_type='PROCESS_CONDITION',
        )
        c2 = CandidateRequirement(
            description='Detailed minimum comprehensive warranty of 3 years required from seller',
            category='COMMERCIAL_TERMS',
            field='warranty_years',
            operator='>=',
            expected_value='3 years',
            mandatory=True,
            evidence_block_ids=['BLK-001', 'BLK-002'],
            requirement_type='BIDDER_COMPLIANCE',
        )

        merged = extractor._merge_and_deduplicate_candidates([c1, c2])
        self.assertEqual(len(merged), 1)
        res = merged[0]
        self.assertTrue(res.mandatory)
        self.assertEqual(res.requirement_type, 'BIDDER_COMPLIANCE')
        self.assertEqual(res.description, c2.description)
        self.assertEqual(sorted(res.evidence_block_ids), ['BLK-001', 'BLK-002'])

    def test_05_evidence_grounding_firewall_rejection(self):
        prov = MockLLMProvider()
        extractor = TenderRequirementExtractor(provider=prov)

        # Candidate referencing non-existent block ID
        cand_fake = CandidateRequirement(
            description='Fake requirement with phantom block',
            category='FINANCIAL_CAPACITY',
            field='turnover_cr',
            operator='>=',
            expected_value='100 Crores',
            mandatory=True,
            evidence_block_ids=['NON-EXISTENT-BLK-999'],
        )

        grounder = EvidenceGrounder(self.ext_res)
        res = grounder.ground_requirement(
            candidate_block_ids=cand_fake.evidence_block_ids,
            expected_value=cand_fake.expected_value,
            description=cand_fake.description,
        )
        self.assertFalse(res.is_valid)

    def test_06_canned_mock_single_pass_compatibility(self):
        canned = json.dumps({'requirements': [{
            'description': 'Minimum average annual turnover of Rs. 10 Crores',
            'category': 'FINANCIAL_CAPACITY',
            'field': 'turnover_cr',
            'operator': '>=',
            'expected_value': 'Rs. 10 Crores',
            'mandatory': True,
            'evidence_block_ids': ['BLK-001'],
            'source_clause': 'Clause 1.1'
        }]})
        prov = MockLLMProvider(canned_response=canned)
        extractor = TenderRequirementExtractor(provider=prov, mode=LLMMode.MOCK)
        reqs = extractor.extract_requirements(self.ext_res, tender_id='TENDER-MOCK')
        self.assertEqual(len(reqs), 1)
        self.assertEqual(reqs[0].field, 'turnover_cr')
        self.assertEqual(reqs[0].tender_id, 'TENDER-MOCK')

    def test_07_applicability_requirement_type_schema_validity(self):
        canned = json.dumps({'requirements': [{
            'description': 'EMD is not required for this procurement',
            'category': 'COMMERCIAL_TERMS',
            'field': 'emd_required',
            'operator': '==',
            'expected_value': 'No',
            'mandatory': False,
            'evidence_block_ids': ['BLK-001'],
            'requirement_type': 'PROCESS_CONDITION',
        }]})
        prov = MockLLMProvider(canned_response=canned)
        extractor = TenderRequirementExtractor(provider=prov, mode=LLMMode.MOCK)
        reqs = extractor.extract_requirements(self.ext_res)
        self.assertEqual(len(reqs), 1)
        req = reqs[0]
        self.assertEqual(req.normalized_expected_value, False)
        self.assertEqual(req.unit, 'BOOLEAN')
        self.assertIsNotNone(req.applicability)
        self.assertEqual(req.applicability.get('requirement_type'), 'PROCESS_CONDITION')
        is_valid, errs = self.validator.validate_requirement(req.to_dict())
        self.assertTrue(is_valid, f'Schema validation errors: {errs}')


if __name__ == '__main__':
    unittest.main()
