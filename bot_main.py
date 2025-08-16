# import random
# import enum
# import time

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
        is_opponents_main_won

    from _zergling_drone_rush import prominent_structures, zergling_drone_rush_step, \
        null_wall_breakers, check_wall_breakers, zvz_spine_crawler, \
        wall_breaker_do_block, macro_element

    from _roach_rush import roach_rush_step

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
        self.attack_drones = []
        self.drones_on_gas = []
        self.building_workers = []
        self.mining_drones = []
        self.mining_hatchery_data = {}  # {hatchery1: [mineral_field1, mineral_field2, ...], hatchery2: [mineral_field1, mineral_field2, ...], ...}
        self.mining_mineral_data = {}  # {mineral_filed1: [drone1, drone2], mineral_field2: [drone1, drone2], ...}
        self.mining_drone_data = {}  # {drone1: [hatchery_position_mining, mineral_position_mining], drone2: [position1, position2], ...}
        self.mineral_field_distances = {}

        # mineral filed standard distance: 6-8
        # {hatchery: {mineral1: [drone1, drone2], mineral2: [drone1, drone2], ...}, ... }

    async def on_step(self, iteration):  # 168 iterations per minute ~ 3 iterations per second
        # await self.zergling_drone_rush_step(iteration=iteration)
        await self.roach_rush_step(iteration=iteration)


def main():
    run_game(sc2.maps.get("2000AtmospheresAIE"), [  # 2000AtmospheresAIE ; CatalystLE ; AbyssalReefLE
        Human(Race.Terran),                         # JagannathaAIE ; BlackburnAIE ; OxideAIE
        # Bot(Race.Zerg, SmallBly()),
        Bot(Race.Zerg, SmallBly()),
        # Computer(Race.Terran, Difficulty.VeryHard),
    ], realtime=False,
             disable_fog=False,
             random_seed=1
             # save_replay_as="smallBly_vs_smallBly_20-06-2022.SC2Replay",
             )


if __name__ == '__main__':
    main()

