import unittest
from backend.ocr_text import assemble

def block(x,y,w,h,text,score=.99):
    return ([[x,y],[x+w,y],[x+w,y+h],[x,y+h]],text,score)

class OCRTextTests(unittest.TestCase):
    def test_stacked_prefix_before_tall_suffix(self):
        parts=[block(20,32,20,18,'MA'),block(80,10,60,45,'2662'),block(15,5,45,22,'KA-09',.84)]
        result=assemble(parts)
        self.assertEqual(result['normalized_text'],'KA09MA2662')
        self.assertEqual(result['confidence'],.84)
    def test_regular_two_line_plate(self):
        result=assemble([block(55,30,40,20,'1234'),block(10,0,80,20,'AB-09'),block(10,30,30,20,'XY')])
        self.assertEqual(result['normalized_text'],'AB09XY1234')
    def test_weak_fragment_cannot_hide_in_average(self):
        result=assemble([block(0,0,30,20,'AB',.2),block(40,0,50,20,'1234',1)])
        self.assertEqual(result['confidence'],.2)
        self.assertTrue(result['needs_manual_review'])
    def test_empty(self):
        self.assertEqual(assemble([])['normalized_text'],'')
        self.assertTrue(assemble([])['needs_manual_review'])
