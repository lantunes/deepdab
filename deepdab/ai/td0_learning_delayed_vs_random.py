from deepdab.ai import *

board_size = (2, 2)
num_episodes = 500000
learning_rate = 1.0
gamma = 0.99
epsilon = 0.18

print("initializing value table for (%s, %s) game..." % (board_size[0], board_size[1]))

p1 = TDZeroPolicy(board_size=board_size, epsilon=epsilon, learning_rate=learning_rate, gamma=gamma,
                  initial_state_value=0.0)
random_policy = RandomPolicy()


def compute_reward(game):
    if game.is_finished() and game.get_score('p1') > game.get_score('random'):
        return 1.0
    return 0.0

total_rewards = []
results = {'won': 0, 'lost': 0, 'tied': 0}

for episode_num in range(1, num_episodes + 1):
    players = ['p1', 'random']
    if episode_num % 2 == 0:
        players = [x for x in reversed(players)]
    game = Game(board_size, players)
    current_player = game.get_current_player()
    backups = []
    while not game.is_finished():
        board_state = game.get_board_state()
        if current_player == 'random':
            random_edge = random_policy.select_edge(board_state)
            current_player, _ = game.select_edge(random_edge, 'random')
        else:
            edge = p1.select_edge(board_state)
            current_player, _ = game.select_edge(edge, 'p1')
            backups.append(game.get_board_state())
            if not game.is_finished() and len(backups) > 1:
                p1.update_value(0.0, backups[-2], backups[-1])
    reward = compute_reward(game)
    p1.update_value(reward, backups[-2], backups[-1])
    # analyze results
    total_rewards.append(reward)
    p1_score = game.get_score('p1')
    random_score = game.get_score('random')
    if p1_score > random_score:
        results['won'] += 1
    elif p1_score < random_score:
        results['lost'] += 1
    else:
        results['tied'] += 1
    if episode_num % 100 == 0:
        vt = p1.get_value_table()
        print("%s, %s, %s, %s" % (episode_num, sum(total_rewards), results, len([x for x in vt if vt[x] > 0.0 ])))
        total_rewards = []
        results = {'won': 0, 'lost': 0, 'tied': 0}


print(p1.get_value_table())
