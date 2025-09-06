# import random
# import enum
# import time

import math
from coordinate_functions import *

import sc2
from sc2.data import Difficulty
from sc2.data import ActionResult
from sc2.main import run_game
# from sc2.data import Race, ActionResult, Difficulty
# from sc2.constants import *
from sc2.player import Bot, Computer, Human
# from sc2.data import race_townhalls
from sc2.bot_ai import *
from sc2.ids.unit_typeid import UnitTypeId
from sc2.ids.ability_id import AbilityId
from sc2.ids.upgrade_id import UpgradeId
from sc2.game_info import GameInfo, Ramp


def choose_strategy(game_results: list):
    wins1, losses1, draws1, wins2, losses2, draws2 = game_results

    total1 = wins1 + losses1 + draws1
    total2 = wins2 + losses2 + draws2
    total_games = total1 + total2

    if total_games == 0:
        return 2

    def calculate_score(wins, losses, draws, exploration=2.0):
        n = wins + losses + draws
        if n == 0:
            return float('inf')

        points = 3 * wins + draws
        mean = points / n
        return mean + exploration * math.sqrt(math.log(total_games) / n)

    score1 = calculate_score(wins1, losses1, draws1)
    score2 = calculate_score(wins2, losses2, draws2)

    if score2 > score1:
        return 2
    elif score1 > score2:
        return 1

    if total1 == 0:
        return 1
    if total2 == 0:
        return 2

    if losses1 < losses2:
        return 1
    elif losses2 < losses1:
        return 2

    return 1 if total1 >= total2 else 2


class SmallBly(BotAI):

    from _speed_mining import speed_mining, refresh_mining_data, assign_mining_positions, \
        check_reorganization, is_hatchery_for_mining, neighbor_mineral_fields, \
        check_mineral_fields_near_base

    from _universal_functions import refresh_unit, enemy_dangerous_structures, \
        dangerous_structures_exist, select_target, get_locations, base_scout, \
        is_units_health_max, all_flying_enemies, all_known_structures_flying, \
        closest_enemy_unit, closest_unit, enemy_locations, overlord_management, \
        map_scout, need_group, group_units, defending, micro_element, queen_management, \
        no_units_in_opponent_main, proxy, mining_iteration, find_final_structures, \
        is_opponents_main_won, manage_queen_attack, find_expand, has_expand_ramp, \
        accurate_attack, closest_unit_dist

    from _zergling_drone_rush import prominent_structures, zergling_drone_rush_step, \
        null_wall_breakers, check_wall_breakers, zvz_spine_crawler, \
        wall_breaker_do_block, macro_element

    from _roach_rush import roach_rush_step, burrow_micro

    def __init__(self):
        super().__init__()
        self.need_to_attack_main_base = True
        self.in_scout = []
        self.location_counter = 0
        self.stop_drone = False
        self.defence = False
        self.locations = []
        self.known_enemy_u = []
        self.home_dronny: Units = Units([], self)
        self.stop_group = False
        self.busy_overlords = []
        self.in_micro = []
        self.go_back_points = []
        self.need_air_units = False
        self.stop_zergling = False
        self.dronny = False
        self.selected_wall_breaker = False
        self.wall_breakers = []
        self.have_moved_wall_breaker = False
        self.place = False
        self.begin_position = False
        self.stop_wall_breaker = False
        self.stop_crawl = False
        self.stop_new_drone_attack_time = 100
        self.canceled_crawl = False
        self.muta_tagged = False
        self.attack_drones = []
        self.drones_on_gas = []
        self.building_workers = []
        self.mining_drones = []
        self.mining_hatchery_data = {}  # {hatchery1: [mineral_field1, mineral_field2, ...], hatchery2: [mineral_field1, mineral_field2, ...], ...}
        self.mining_mineral_data = {}  # {mineral_filed1: [drone1, drone2], mineral_field2: [drone1, drone2], ...}
        self.mining_drone_data = {}  # {drone1: [hatchery_position_mining, mineral_position_mining], drone2: [position1, position2], ...}
        self.mineral_field_distances = {}
        self.in_burrow_process = []
        self.two_enemy_ramps = []
        self.expand = False
        self.expand_rump_exist = False
        self.expand_ramp_passed = []
        self.main_ramp_passed = []
        self.strategy = False

        # mineral filed standard distance: 6-8
        # {hatchery: {mineral1: [drone1, drone2], mineral2: [drone1, drone2], ...}, ... }

    def read_and_choose_strategy(self):
        opponent_id = self.opponent_id
        if opponent_id is None:
            self.strategy = 2
            return

        with open("data/statistics.txt") as f:
            statistics_text = f.read()

        massive = statistics_text.strip().split('\n')
        string = f"{opponent_id}: 0 0 0 0 0 0"
        if opponent_id in statistics_text:
            for i in range(len(massive)):
                string = massive[i]
                if opponent_id in string:
                    break

        split_str = string.split(':')
        game_results = list(map(int, split_str[1].strip().split(' ')))

        while len(game_results) < 6:
            game_results.append(0)

        print(f"{game_results=}")
        self.strategy = choose_strategy(game_results)

    async def tag_strategy(self):
        if self.strategy == 1:
            await self.chat_send(message="Tag: zerglings", team_only=True)

        elif self.strategy == 2:
            await self.chat_send(message="Tag: roaches", team_only=True)


    async def on_step(self, iteration):  # 168 iterations per minute ~ 3 iterations per second
        if not self.strategy:
            try:
                self.read_and_choose_strategy()
                print(f"{self.strategy=}")
            except BaseException:
                print("Exception while choosing strategy")

            if self.strategy != 1 and self.strategy != 2:
                self.strategy = 1

            await self.tag_strategy()

            with open("data/chosen_strategy.txt", mode='w') as f:
                f.write(str(self.strategy))

        if len(self.two_enemy_ramps) == 0:
            sorted_ramps = sorted(self.game_info.map_ramps,
                                  key=lambda x: get_distance(x.top_center, self.enemy_start_locations[0].position))
            self.two_enemy_ramps = sorted_ramps[:2]
            self.expand_rump_exist = self.has_expand_ramp()
            print(self.expand_rump_exist)

        if self.strategy == 1:
            await self.zergling_drone_rush_step(iteration=iteration)

        elif self.strategy == 2:
            await self.roach_rush_step(iteration=iteration)


def main():
    run_game(sc2.maps.get("TorchesAIE_v4"), [  # 2000AtmospheresAIE ; CatalystLE ; AbyssalReefLE
        Human(Race.Zerg),                         # JagannathaAIE ; BlackburnAIE ; OxideAIE ; PersephoneAIE_v4
        # Bot(Race.Zerg, SmallBly()),               # TorchesAIE_v4
        Bot(Race.Zerg, SmallBly()),
        # Computer(Race.Protoss, Difficulty.CheatInsane),
    ], realtime=False,
             disable_fog=False,
             random_seed=0,
             # save_replay_as="smallBly_vs_smallBly_21-08-2025.SC2Replay",
             )


if __name__ == '__main__':
    main()

