import unittest
from types import SimpleNamespace
from backend.ocr_engine import agree_fallback, rapid_parts

class EngineTests(unittest.TestCase):
    def reading(self,text,score):
        return {'normalized_text':text,'raw_text':text,'confidence':score,'needs_manual_review':score<.8}
    def test_disagreement_never_uses_highest_score(self):
        result=agree_fallback(self.reading('AB0123',.99),self.reading('ABO123',.98))
        self.assertEqual(result['confidence'],0)
        self.assertTrue(result['needs_manual_review'])
    def test_agreement_uses_lower_score(self):
        result=agree_fallback(self.reading('AB0123',.99),self.reading('AB0123',.85))
        self.assertEqual(result['confidence'],.85)
        self.assertFalse(result['needs_manual_review'])
    def test_empty_and_weak_agreement_rejected(self):
        for text,score in [('',1),('AB123',.4)]:
            self.assertTrue(agree_fallback(self.reading(text,score),self.reading(text,score))['needs_manual_review'])
    def test_recognition_only_output_adapter(self):
        result=SimpleNamespace(txts=('AB123',),scores=(.9,))
        self.assertEqual(rapid_parts(result,(400,100))[0][0],[[0,0],[400,0],[400,100],[0,100]])
        self.assertEqual(rapid_parts(SimpleNamespace(txts=None),(400,100)),[])
