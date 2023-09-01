import unittest
from src.helpers import detect_nonzero_segments
import numpy as np


class TestHelpers(unittest.TestCase):
    def test_detect_nonzero_segments(self):
        data = np.zeros(50)
        data[10:20] = 1.0
        data[30:40] = 1.0
        segments = detect_nonzero_segments(data)
        self.assertEqual(segments, [(10, 20), (30, 40)])
