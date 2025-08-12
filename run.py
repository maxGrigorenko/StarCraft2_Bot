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
        id_1: 1 2 0
        id_2: 3 0 0
        ...
        id_n: wins loses ties
        """

        statistics_text = f.read()
        print(f"{statistics_text=}")
        massive = statistics_text.strip().split('\n')

        index = None

        if opponent_id in statistics_text:

            for i in range(len(massive)):
                string = massive[i]
                index = i

                if opponent_id in string:
                    break

        else:
            string = f"{opponent_id}: 0 0 0"

        split_str = string.split(':')
        split_str_1 = split_str[1].strip().split(' ')

        if "Victory" in result:
            new_string = split_str[0] + f": {str(int(split_str_1[0])+1)} {split_str_1[1]} {split_str_1[2]}"
        elif "Defeat" in result:
            new_string = split_str[0] + f": {split_str_1[0]} {str(int(split_str_1[1])+1)} {split_str_1[2]}"
        else:
            new_string = split_str[0] + f": {split_str_1[0]} {split_str_1[1]} {str(int(split_str_1[2])+1)}"

        if index is not None:
            massive[index] = new_string
        else:
            massive.append(new_string)

        write_file(massive)
        f.close()


def write_file(massive):
    with open("data/statistics.txt", mode='w') as f:
        for string in massive:
            print(string + '\n')
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
