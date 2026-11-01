import unittest
from student_codes import normalize_student_code
class CodeTests(unittest.TestCase):
    def test_normalization(self):
        self.assertEqual(normalize_student_code(' 123 '),'000123')
        self.assertEqual(normalize_student_code('001268'),'001268')
    def test_reject_invalid(self):
        for value in ['1234567','HS001','1e3','12.0','-1','', '１２３']:
            with self.subTest(value=value), self.assertRaises(ValueError): normalize_student_code(value)
