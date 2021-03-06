from deepdab.ai import *
from deepdab.util.evaluator import *
from deepdab.util.file_helper import *
from deepdab.util.helper_functions import *
from deepdab.util.rate_util import *
from deepdab.util.reward_util import *

board_size = (2, 2)
num_episodes = 300000
learning_rate = 0.0005
min_learning_rate = 0.000001
temperature = 1.0
min_temperature = 1.0
decay_speed = 1.0
use_symmetries = True
base_path = get_base_path_arg()

print("initializing for (%s, %s) game..." % (board_size[0], board_size[1]))

policy = PGPolicyCNN(board_size, batch_size=1)
reward_fn = DelayedBinaryReward()

print_info(board_size=board_size, num_episodes=num_episodes, policy=policy, mode='self-play', reward=reward_fn,
           updates='offline', learning_rate=learning_rate, min_learning_rate=min_learning_rate, temperature=temperature,
           min_temperature=min_temperature, architecture=policy.get_architecture(), decay_speed=decay_speed)

unique_states_visited = set()
for episode_num in range(1, num_episodes + 1):
    tmp = gen_rate_exponential(episode_num, temperature, min_temperature, num_episodes, decay_speed)
    lr = gen_rate_exponential(episode_num, learning_rate, min_learning_rate, num_episodes, decay_speed)
    policy.set_boltzmann_action(True)
    policy.set_temperature(tmp)
    policy.set_learning_rate(lr)
    players = [0, 1]
    game = Game(board_size, players)
    current_player = game.get_current_player()

    p0_actions = []
    p1_actions = []
    p0_states = []
    p1_states = []

    while not game.is_finished():
        board_state = game.get_board_state()
        if current_player == 0:
            p0_states.append(board_state)
            edge = policy.select_edge(board_state)
            p0_actions.append(to_one_hot_action(board_state, edge))
            current_player, _ = game.select_edge(edge, 0)
            unique_states_visited.add(as_string(game.get_board_state()))
        else:
            p1_states.append(board_state)
            edge = policy.select_edge(board_state)
            p1_actions.append(to_one_hot_action(board_state, edge))
            current_player, _ = game.select_edge(edge, 1)
            unique_states_visited.add(as_string(game.get_board_state()))

    p0_reward = reward_fn.compute_reward(game, 0, 1)
    p1_reward = reward_fn.compute_reward(game, 1, 0)
    p0_outcomes = len(p0_actions)*[p0_reward]
    p1_outcomes = len(p1_actions)*[p1_reward]

    all_transitions = []
    append_transitions(p0_states, p0_actions, p0_outcomes, all_transitions, use_symmetries, board_size)
    append_transitions(p1_states, p1_actions, p1_outcomes, all_transitions, use_symmetries, board_size)

    policy.update_model(all_transitions)

    # analyze results
    if episode_num % 500 == 0:
        # play against opponents
        policy.set_boltzmann_action(False)
        opponents = [RandomPolicy(), Level1HeuristicPolicy(board_size), Level2HeuristicPolicy(board_size)]
        results = evaluate(policy, board_size, 1000, opponents)
        print("%s, %s, %s, %s, %s, %s, %s, %s" % (episode_num, results[RandomPolicy.__name__]['won'],
                                                  results[Level1HeuristicPolicy.__name__]['won'],
                                                  results[Level2HeuristicPolicy.__name__]['won'],
                                                  results, len(unique_states_visited), tmp, lr))
        WeightWriter.print_episode(base_path, episode_num, policy.print_params)