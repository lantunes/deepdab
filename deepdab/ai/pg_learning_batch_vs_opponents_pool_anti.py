from deepdab.ai import *
from deepdab.util.helper_functions import *
from deepdab.util.file_helper import *
from deepdab.util.reward_util import *
from deepdab.util.rate_util import *
from deepdab.util.evaluator import *
from deepdab.util.opponent_pool_util import *

board_size = (3, 3)
num_episodes = 1000000
learning_rate_schedule = {0: 0.005}
epsilon_schedule = {0: 0.1}
batch_size = 32
decay_speed = 1.0
opponent_pool_max_size = 100
num_episodes_per_update = 500
num_episodes_per_opponent_cache = 500
dropout_keep_prob = 1.0
use_symmetries = True
normalize_action_probs_with_softmax = True
base_path = get_base_path_arg()

print("initializing for (%s, %s) game..." % (board_size[0], board_size[1]))

policy = PGPolicy3x3CNN(board_size, batch_size=batch_size, dropout_keep_prob=dropout_keep_prob)
anti_policy = PGPolicy3x3CNN(board_size, batch_size=batch_size, dropout_keep_prob=dropout_keep_prob)
L2 = Level2HeuristicPolicy(board_size)
L1 = Level1HeuristicPolicy(board_size)
L0 = RandomPolicy()
reward_fn = DelayedBinaryReward()
opponent_pool = OpponentPool(max_size=opponent_pool_max_size)

opponent_schedule = {0: L0, 100000: L1, 200000: L2}

print_info(board_size=board_size, num_episodes=num_episodes, policy=policy, mode='vs opponents then self-play pool',
           reward=reward_fn, updates='offline', learning_rate_schedule=learning_rate_schedule, epsilon_schedule=epsilon_schedule,
           architecture=policy.get_architecture(), batch_size=batch_size, use_symmetries=use_symmetries,
           num_episodes_per_policy_update=num_episodes_per_update,
           num_episodes_per_opponent_cache=num_episodes_per_opponent_cache, opponent_pool_max_size=opponent_pool_max_size,
           normalize_action_probs_with_softmax=normalize_action_probs_with_softmax)


def select_edge_with_anti(pol, anti_pol, board_state, epsilon):
    if random.random() < epsilon:
        zero_indices = []  # indices of legal actions
        for i in range(len(board_state)):
            if board_state[i] == 0:
                zero_indices.append(i)
        return random.choice(zero_indices)

    def get_selected_index(child_state, parent_state):
        diff = [x1 - x2 for (x1, x2) in zip(child_state, parent_state)]
        argmax = max(enumerate(diff), key=lambda x: x[1])[0]
        return argmax
    policy_prob_map = pol.get_action_probs(board_state, normalize_action_probs_with_softmax)
    anti_policy_prob_map = anti_pol.get_action_probs(board_state, normalize_action_probs_with_softmax)
    diff_prob_map = {}
    for state in policy_prob_map:
        diff_prob_map[state] = policy_prob_map[state] - anti_policy_prob_map[state]
    highest_prob = None
    selected_state = None
    for state, val in diff_prob_map.items():
        if highest_prob is None or val > highest_prob:
            highest_prob = val
            selected_state = state
    return get_selected_index([int(i) for i in selected_state], board_state)


class CombinedPolicy(Policy):
    def __init__(self, pol, anti_pol, epsilon):
        self._pol = pol
        self._anti_pol = anti_pol
        self._epsilon = epsilon

    def select_edge(self, st):
        return select_edge_with_anti(self._pol, self._anti_pol, st, self._epsilon)

unique_states_visited = set()
all_transitions = []
all_anti_transitions = []

for episode_num in range(1, num_episodes + 1):
    lr = gen_rate_step(episode_num, learning_rate_schedule)
    eps = gen_rate_step(episode_num, epsilon_schedule)
    scheduled_opponent = gen_rate_step(episode_num, opponent_schedule)
    if scheduled_opponent == 'policy':
        opponent = opponent_pool.sample_opponent()
    else:
        opponent = scheduled_opponent
    policy.set_boltzmann_action(False)
    policy.set_epsilon(0.0)
    policy.set_learning_rate(lr)
    anti_policy.set_boltzmann_action(False)
    anti_policy.set_epsilon(0.0)
    anti_policy.set_learning_rate(lr)

    policy_actions = []
    opponent_actions = []
    policy_states = []
    opponent_states = []

    players = ['policy', 'opponent'] if episode_num % 2 == 0 else ['opponent', 'policy']
    game = Game(board_size, players)
    current_player = game.get_current_player()
    while not game.is_finished():
        board_state = game.get_board_state()
        if current_player == 'policy':
            policy_states.append(board_state)
            edge = select_edge_with_anti(policy, anti_policy, board_state, eps)
            policy_actions.append(to_one_hot_action(board_state, edge))
            current_player, _ = game.select_edge(edge, current_player)
            unique_states_visited.add(as_string(game.get_board_state()))
        else:
            opponent_states.append(board_state)
            edge = opponent.select_edge(board_state)
            opponent_actions.append(to_one_hot_action(board_state, edge))
            current_player, _ = game.select_edge(edge, current_player)
            unique_states_visited.add(as_string(game.get_board_state()))
    policy_reward = reward_fn.compute_reward(game, 'policy', 'opponent')
    opponent_reward = reward_fn.compute_reward(game, 'opponent', 'policy')

    if policy_reward == 1:
        policy_outcomes = len(policy_actions)*[policy_reward]
        append_transitions(policy_states, policy_actions, policy_outcomes, all_transitions, use_symmetries, board_size)
        opponent_outcomes = len(opponent_actions)*[policy_reward]
        append_transitions(opponent_states, opponent_actions, opponent_outcomes, all_anti_transitions, use_symmetries, board_size)
    elif opponent_reward == 1:
        opponent_outcomes = len(opponent_actions)*[opponent_reward]
        append_transitions(opponent_states, opponent_actions, opponent_outcomes, all_transitions, use_symmetries, board_size)
        policy_outcomes = len(policy_actions)*[opponent_reward]
        append_transitions(policy_states, policy_actions, policy_outcomes, all_anti_transitions, use_symmetries, board_size)

    if episode_num % num_episodes_per_update == 0:
        policy.update_model(all_transitions)
        anti_policy.update_model(all_anti_transitions)
        all_transitions = []
        all_anti_transitions = []

    if episode_num % num_episodes_per_opponent_cache == 0:
        opponent_pool.add_to_pool(CombinedPolicy(policy.copy(), anti_policy.copy(), eps) if scheduled_opponent == 'policy' else opponent)

    # analyze results
    if episode_num % 1000 == 0:
        # play against opponents
        policy.set_boltzmann_action(False)
        policy.set_epsilon(0.0)
        opponents = [RandomPolicy(), Level1HeuristicPolicy(board_size), Level2HeuristicPolicy(board_size)]
        results = evaluate(policy, board_size, 1000, opponents)
        print("%s, %s, %s, %s, %s, %s, %s, %s" % (episode_num, results[RandomPolicy.__name__]['won'],
                                                  results[Level1HeuristicPolicy.__name__]['won'],
                                                  results[Level2HeuristicPolicy.__name__]['won'],
                                                  results, len(unique_states_visited), eps, lr))
        WeightWriter.print_episode(base_path, episode_num, policy.print_params)
