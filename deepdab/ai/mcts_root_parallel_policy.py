from .mcts_game import MCTSGame
from deepdab import *
from math import *
import math
import concurrent.futures


class MCTSRootParallelPolicy:
    """
    Parallelizes MCTS using Root Parallelization.
    """
    def __init__(self, board_size, num_playouts, num_workers, c=sqrt(2), default_policy=None):
        self._board_size = board_size
        self._num_playouts = num_playouts
        self._c = c
        self._default_policy = default_policy
        self._num_workers = num_workers

    def set_num_playouts(self, num_playouts):
        self._num_playouts = num_playouts

    def select_edge(self, board_state, root_player_score):
        root_nodes = []

        with concurrent.futures.ProcessPoolExecutor(max_workers=self._num_workers) as executor:
            for r in executor.map(self._playout, [board_state]*self._num_workers, [root_player_score]*self._num_workers):
                root_nodes.append(r)

        # return the move that was most visited
        merged_root_node = self._merge_root_nodes(root_nodes, board_state)
        most_visited_node = sorted(merged_root_node.children, key = lambda c: c.visits)[-1]
        return self._get_selected_index(most_visited_node.state, board_state)

    def _merge_root_nodes(self, root_nodes, board_state):
        merged_root_node = _Node(board_state, self._c)
        merged_children_map = {}
        for root_node in root_nodes:
            merged_root_node.visits += root_node.visits
            merged_root_node.wins += root_node.wins
            for child_node in root_node.children:
                child_state = as_string(child_node.state)
                if child_state not in merged_children_map:
                    merged_child_node = merged_root_node.add_child(child_node.state, self._c)
                    merged_child_node.visits += child_node.visits
                    merged_child_node.wins += child_node.wins
                    merged_children_map[child_state] = merged_child_node
                else:
                    merged_child_node = merged_children_map[child_state]
                    merged_child_node.visits += child_node.visits
                    merged_child_node.wins += child_node.wins
        return merged_root_node

    def _playout(self, board_state, root_player_score):
        root_node = _Node(board_state, self._c)

        # Perform playouts
        for i in range(self._num_playouts):
            game = MCTSGame(self._board_size, players=['root', 'opponent'], board_state=board_state,
                            root_player_score=root_player_score)
            current_player = game.get_current_player()
            node = root_node

            root_player_states = []
            opponent_states = []

            # Select
            while not node.has_untried_moves() and node.has_children():
                prev_state = node.state
                node = node.select_child()
                if current_player == 'root':
                    root_player_states.append(node.state)
                else:
                    opponent_states.append(node.state)
                selected_index = self._get_selected_index(node.state, prev_state)
                current_player = game.select_edge(selected_index, current_player)

            # Expand
            if node.has_untried_moves():
                move_state = node.select_untried_move()
                if current_player == 'root':
                    root_player_states.append(move_state)
                else:
                    opponent_states.append(move_state)
                selected_index = self._get_selected_index(move_state, node.state)
                current_player = game.select_edge(selected_index, current_player)
                node = node.add_child(move_state, self._c)

            # Rollout
            current_board_state = game.get_board_state()
            while not game.is_finished():
                if self._default_policy is None:
                    next_index = self._select_next_move_randomly(current_board_state)
                else:
                    next_index = self._default_policy.select_edge(current_board_state)
                current_player = game.select_edge(next_index, current_player)
                current_board_state = game.get_board_state()

            # Backpropagate
            #   backpropagate from the expanded node and work back to the root node
            while node is not None:
                root_score = game.get_score('root')
                opponent_score = game.get_score('opponent')
                node.visits += 1
                if node.state in root_player_states:
                    node.wins += (1 if root_score > opponent_score else 0)
                if node.state in opponent_states:
                    node.wins += (1 if opponent_score > root_score else 0)
                node = node.parent

        return root_node

    def _get_selected_index(self, child_state, parent_state):
        diff = [x1 - x2 for (x1, x2) in zip(child_state, parent_state)]
        argmax = max(enumerate(diff), key=lambda x: x[1])[0]
        return argmax

    def _select_next_move_randomly(self, current_state):
        zero_indices = []
        for i in range(len(current_state)):
            if current_state[i] == 0:
                zero_indices.append(i)
        return random.choice(zero_indices)


class _Node:
    def __init__(self, state, c, parent=None):
        self.state = state
        self._c = c
        self.wins = 0
        self.visits = 0
        self.parent = parent
        self.children = []
        self.untried_moves = self._get_child_states()

    def _get_zero_indices(self):
        zero_indices = []
        for i in range(len(self.state)):
            if self.state[i] == 0:
                zero_indices.append(i)
        return zero_indices

    def _get_new_state(self, existing_state, selected_index):
        new_state = [x for x in existing_state]
        new_state[selected_index] = 1
        return new_state

    def _get_child_states(self):
        child_states = []
        zero_indices = self._get_zero_indices()
        for zero_index in zero_indices:
            child_states.append(self._get_new_state(self.state, zero_index))
        return child_states

    def has_untried_moves(self):
        return self.untried_moves != []

    def select_untried_move(self):
        return random.choice(self.untried_moves)

    def add_child(self, child_state, c):
        child = _Node(child_state, c, parent=self)
        self.children.append(child)
        self.untried_moves.remove(child_state)
        return child

    def has_children(self):
        return self.children != []

    def select_child(self):
        highest_ucb1 = None
        selected_child_node = None
        for child_node in self.children:
            ucb1 = child_node.ucb1()
            if highest_ucb1 is None or highest_ucb1 < ucb1:
                highest_ucb1 = ucb1
                selected_child_node = child_node
        return selected_child_node

    def ucb1(self):
        if self.visits == 0:
            return math.inf
        return self.wins/self.visits + self._c*sqrt(log(self.parent.visits)/self.visits)
