import unittest

import deepdab


class TestBoardStateToString(unittest.TestCase):

    def test_as_string(self):
        self.assertEqual(deepdab.as_string([0, 1, 0, 1]), '0101')
        self.assertEqual(deepdab.as_string([0, 1, 0, 1, 0, 0]), '010100')
