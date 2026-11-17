import unittest
from src.shop.pricing import total
from src.reports.summary import average

class T(unittest.TestCase):
    def test_total(self):
        self.assertEqual(total(10, 2, 5), 25)
    def test_qty(self):
        with self.assertRaises(ValueError):
            total(10, 0, 5)
    def test_avg(self):
        self.assertEqual(average([1, 2, 3]), 2)

class T2(unittest.TestCase):
    def test_none(self):
        self.assertEqual(average([1, None, 3]), 2)
