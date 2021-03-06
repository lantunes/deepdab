from deepdab.ai import *
from deepdab.util.helper_functions import *
from deepdab.util.file_helper import *
from deepdab.util.reward_util import *
from deepdab.util.rate_util import *
from deepdab.util.evaluator import *

board_size = (2, 2)
num_episodes = 1000000
learning_rate_schedule = {0: 0.005, 500000: 0.0005}
epsilon = 1.0
min_epsilon = 0.1
batch_size = 32
decay_speed = 1.0
use_symmetries = True
activation = tf.nn.tanh
base_path = get_base_path_arg()

print("initializing for (%s, %s) game..." % (board_size[0], board_size[1]))

policy = PGPolicyCNN2(board_size, batch_size=batch_size, activation=activation)
reward_fn = DelayedBinaryReward()

print_info(board_size=board_size, num_episodes=num_episodes, policy=policy, mode='self-play', reward=reward_fn,
           updates='offline', learning_rate_schedule=learning_rate_schedule, epsilon=epsilon,
           min_epsilon=min_epsilon, architecture=policy.get_architecture(), batch_size=batch_size,
           decay_speed=decay_speed, activation=activation)

unique_states_visited = set()
all_transitions = []
for episode_num in range(1, num_episodes + 1):
    eps = gen_rate_exponential(episode_num, epsilon, min_epsilon, num_episodes, decay_speed)
    lr = gen_rate_step(episode_num, learning_rate_schedule)
    policy.set_boltzmann_action(False)
    policy.set_epsilon(eps)
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

    # don't add transitions that have 0 reward as the gradient will be zero anyways
    if p0_reward == 1:
        p0_outcomes = len(p0_actions)*[p0_reward]
        append_transitions(p0_states, p0_actions, p0_outcomes, all_transitions, use_symmetries, board_size)
    elif p1_reward == 1:
        p1_outcomes = len(p1_actions)*[p1_reward]
        append_transitions(p1_states, p1_actions, p1_outcomes, all_transitions, use_symmetries, board_size)

    if episode_num % 100 == 0:
        policy.update_model(all_transitions)
        all_transitions = []

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