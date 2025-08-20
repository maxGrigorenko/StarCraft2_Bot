import sys
from sc2.main import run_game
from sc2 import maps
from sc2.data import Race, Difficulty
from sc2.player import Bot, Computer
from bot_main import SmallBly
from __init__ import run_ladder_game


def refresh_statistics(result, opponent_id):

    with open("data/statistics.txt") as f:

        """
        id_1: 1 2 0 1 2 0
        id_2: 3 0 0 3 0 0
        ...
        id_n: wins1 loses1 ties1 wins2 loses2 ties2
        """

        statistics_text = f.read()
        
    with open("data/chosen_strategy.txt") as f:
        strategy = int(f.read())

    massive = statistics_text.strip().split('\n')
    index = None
    string = f"{opponent_id}: 0 0 0 0 0 0"
    if opponent_id in statistics_text:
        for i in range(len(massive)):
            string = massive[i]
            index = i
            if opponent_id in string:
                break

    split_str = string.split(':')
    split_results = list(map(int, split_str[1].strip().split(' ')))

    while len(split_results) < 6:
        split_results.append(0)
        
    if strategy == 1:
        increment = 0
    elif strategy == 2:
        increment = 3
    else:
        print("Unable to read strategy")
        return

    if "Victory" in result:
        result_index = 0
    elif "Defeat" in result:
        result_index = 1
    elif "Tie" in result:
        result_index = 2
    else:
        result_index = -1

    if result_index != -1:
        split_results[result_index + increment] += 1
    new_string = split_str[0] + f": {' '.join(list(map(str, split_results)))}"

    if index is not None:
        massive[index] = new_string
    else:
        massive.append(new_string)

    write_file(massive)


def write_file(massive):
    with open("data/statistics.txt", mode='w') as f:
        for string in massive:
            print(string)
            f.write(string + '\n')


bot = Bot(Race.Zerg, SmallBly())

# Start game
if __name__ == "__main__":
    if "--LadderServer" in sys.argv:
        # Ladder game started by LadderManager
        print("Starting ladder game...")
        result, opponent_id = run_ladder_game(bot)

        refresh_statistics(str(result), str(opponent_id))

        print(result, " against opponent ", opponent_id)
    else:
        # Local game
        print("Starting local game...")
        run_game(maps.get("AbyssalReefLE"), [bot, Computer(Race.Terran, Difficulty.VeryHard)], realtime=False)
