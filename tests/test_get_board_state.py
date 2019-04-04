import unittest

import deepdab


class TestGetBoardState(unittest.TestCase):

    def test_get_board_state_1x1(self):
        game = deepdab.Game((1, 1), ['player1', 'player2'])
        board_state = game.get_board_state()
        self.assertEqual(board_state, [0, 0, 0, 0])

    def test_get_board_state_1x2(self):
        game = deepdab.Game((1, 2), ['player1', 'player2'])
        board_state = game.get_board_state()
        self.assertEqual(board_state, [0, 0, 0, 0, 0, 0, 0])

    def test_get_board_state_2x1(self):
        game = deepdab.Game((2, 1), ['player1', 'player2'])
        board_state = game.get_board_state()
        self.assertEqual(board_state, [0, 0, 0, 0, 0, 0, 0])

    def test_get_board_state_2x2(self):
        game = deepdab.Game((2, 2), ['player1', 'player2'])
        board_state = game.get_board_state()
        self.assertEqual(board_state, [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0])

    def test_get_board_state_2x3(self):
        game = deepdab.Game((2, 3), ['player1', 'player2'])
        board_state = game.get_board_state()
        self.assertEqual(board_state, [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0])

    def test_get_board_state_3x2(self):
        game = deepdab.Game((3, 2), ['player1', 'player2'])
        board_state = game.get_board_state()
        self.assertEqual(board_state, [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0])

    def test_get_board_state_3x3(self):
        game = deepdab.Game((3, 3), ['player1', 'player2'])
        board_state = game.get_board_state()
        self.assertEqual(board_state, [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0])
