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
from sc2.player import Bot, Computer
# from sc2.data import race_townhalls
from sc2.bot_ai import *
from sc2.ids.unit_typeid import UnitTypeId
from sc2.ids.ability_id import AbilityId


class SmallBly(BotAI):

    from _speed_mining import speed_mining, refresh_mining_data, assign_mining_positions, check_reorganization, is_hatchery_for_mining, neighbor_mineral_fields

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
        self.building_workers = []
        self.mining_drones = []
        self.mining_hatchery_data = {}  # {hatchery1: [mineral_field1, mineral_field2, ...], hatchery2: [mineral_field1, mineral_field2, ...], ...}
        self.mining_mineral_data = {}  # {mineral_filed1: [drone1, drone2], mineral_field2: [drone1, drone2], ...}
        self.mining_drone_data = {}  # {drone1: [hatchery_position_mining, mineral_position_mining], drone2: [position1, position2], ...}
        self.mineral_field_distances = {}

        # mineral filed standart distance: 6-8
        # {hatchery: {mineral1: [drone1, drone2], mineral2: [drone1, drone2], ...}, ... }

    def refresh_unit(self, unit):
        for u in self.all_own_units:
            if u == unit:
                return u

    def enemy_dangerous_structures(self):
        if self.enemy_race == Race.Terran:
            return self.enemy_structures(UnitTypeId.BUNKER)
        elif self.enemy_race == Race.Zerg:
            return self.enemy_structures(UnitTypeId.SPINECRAWLER)
        else:
            return self.enemy_structures(UnitTypeId.PHOTONCANNON)

    def d_structures(self):
        return (self.enemy_structures(UnitTypeId.SPINECRAWLER).exists or self.enemy_structures(
            UnitTypeId.PHOTONCANNON).exists or self.enemy_structures(UnitTypeId.BUNKER).exists)

    def select_target(self):
        if self.enemy_structures.exists:
            return random.choice(self.enemy_structures).position

        return self.enemy_start_locations[0]

    def get_locations(self):
        result = []
        dr = list(self.expansion_locations.items())
        for i in range(len(dr)):
            result.append(dr[i][0])

        return result

    async def base_scout(self, unit, loc_n):
        locations = self.get_locations()
        unit.attack(locations[loc_n])

    def is_units_health_max(self):
        for u in self.units(UnitTypeId.DRONE):
            if u.health_max - u.health > 0:
                return False

        return True

    def all_flying_enemies(self):

        if len(self.enemy_units) == 0:
            return False

        if self.enemy_units.exists:
            for enemy in self.enemy_units:
                if not enemy.is_flying:
                    return False
        return True

    def all_known_structures_flying(self):

        if len(self.enemy_structures) == 0:
            return False

        for i in self.enemy_structures:
            if not i.is_flying:
                return False

        return True

    def closest_enemy_unit(self, unit):
        closest_unit = self.all_enemy_units[0]
        minimal_distance = 100
        for enemy in self.enemy_units:
            if enemy in self.known_enemy_u:
                distance_now = get_distance(unit.position, enemy.position)
                if distance_now < minimal_distance:
                    minimal_distance = distance_now
                    closest_unit = enemy

        return closest_unit

    def closest_unit(self, units, obj):
        result = units[0]
        minimal = 300
        for unit in units:
            unit = self.refresh_unit(unit)
            d = get_distance(unit.position, obj.position)
            if d < minimal:
                minimal = d
                result = unit
        return result

    def enemy_locations(self):
        itog_locations = []
        dictionary = {}
        locations = self.get_locations()
        enemy_main = self.enemy_start_locations[0]
        for location in locations:
            dist = get_distance(location, enemy_main)
            dictionary.update({location: dist})

        distances = sorted(list(dictionary.values()))

        for i in distances:
            for j in dictionary.keys():
                if dictionary[j] == i and j not in itog_locations:
                    itog_locations.append(j)

        return itog_locations

    async def overlord_management(self):

        if len(self.busy_overlords) < len(self.get_locations()) - 2:
            for overlord in self.units(UnitTypeId.OVERLORD):
                if overlord not in self.busy_overlords:

                    if self.enemy_race == Race.Terran:
                        overlord.move(self.enemy_locations()[len(self.busy_overlords) + 1])
                    else:
                        overlord.move(self.enemy_locations()[len(self.busy_overlords)])

                    self.busy_overlords.append(overlord)

    async def map_scout(self):

        locations = self.locations

        army = (self.units(UnitTypeId.DRONE) | self.units(UnitTypeId.ZERGLING))
        idle_massiv = []

        for i in army:
            if i not in self.home_dronny:
                idle_massiv.append(i)

        if len(idle_massiv) >= len(locations):
            for i in range(len(locations)):
                if idle_massiv[i] not in self.in_scout:
                    await self.base_scout(idle_massiv[i], i)
                    self.in_scout.append(idle_massiv[i])

        else:
            for a in army:
                if a not in self.home_dronny:
                    dist = get_distance(a.position, locations[self.location_counter])
                    if dist < 5:
                        self.location_counter += 1

                for j in army:
                    if j not in self.home_dronny:
                        await self.base_scout(j, self.location_counter)

    def need_group(self, middle_unit, max_distance, max_middle_group_dist):
        forces = []
        for unit in self.units(UnitTypeId.DRONE) | self.units(UnitTypeId.ZERGLING):

            if unit not in self.home_dronny and unit != middle_unit and unit not in self.wall_breakers:
                forces.append(unit)

        distances = []
        for unit in forces:
            distances.append(get_distance(unit.position, self.enemy_start_locations[0].position))

        amount = sum(distances)
        length = len(distances)
        middle_distance = amount / length

        if middle_distance < 70:
            self.stop_group = True
            return False

        elif middle_distance > 80:
            return False

        amount_dist = 0
        quantity = 0

        for unit in forces:
            d = get_distance(middle_unit.position, unit.position)
            if d < max_distance:
                amount_dist += d
                quantity += 1

        if quantity < 3:
            return False

        middle_dist = amount_dist / quantity
        if middle_dist > max_middle_group_dist:
            result = True
        else:
            result = False

        return result

    async def group_units(self, middle_unit, max_distance):
        forces = []
        for unit in self.units(UnitTypeId.DRONE) | self.units(UnitTypeId.ZERGLING):
            if unit not in self.home_dronny and unit not in self.wall_breakers:
                forces.append(unit)

        print("Do grouping")
        positions = []

        for unit in forces:
            d = get_distance(middle_unit.position, unit.position)
            if d < max_distance:
                positions.append(unit.position)

        x = 0
        y = 0

        for pos in positions:
            x += pos.position[0]
            y += pos.position[1]
        lp = len(positions)

        medium_position = [x / lp, y / lp]
        medium_position = sc2.position.Point2(medium_position)

        for unit in forces:
            unit.move(medium_position)

    async def defending(self):
        piece = True

        if len(self.enemy_units) > 0:
            for enemy in self.enemy_units:
                if get_distance(enemy.position, self.start_location) < 6 and not self.is_units_health_max():
                    print("Defending")
                    piece = False
                    for unit in self.units(UnitTypeId.DRONE) | self.units(UnitTypeId.ZERGLING):
                        unit.attack(self.enemy_start_locations[0])

                    self.defence = True
                break

            if piece and self.defence:
                self.defence = False
                await self.distribute_workers()

        if len(self.enemy_units) == 0 and self.defence:
            await self.distribute_workers()
            self.defence = False

    async def micro_element(self):
        if self.is_units_health_max() or not self.enemy_units.exists:
            return

        drones = []

        for drone in self.units(UnitTypeId.DRONE):
            if drone not in self.home_dronny and drone not in self.wall_breakers:
                drones.append(drone)

        back_distance = 1

        for unit in drones:
            fighter = self.closest_enemy_unit(unit)
            if int(unit.health) in [1, 2, 3, 4, 5, 11, 12, 13, 14, 15, 30, 31, 32, 33, 34]:
                if get_distance(unit.position, fighter.position) <= back_distance:
                    self.in_micro.append(unit)
                    unit.gather(self.mineral_field[10])  # mineral field must be not at the enemy`s base
                    # print("Moving unit out", get_distance(unit.position, fighter.position))
                    self.go_back_points.append(unit)

            if unit in self.go_back_points:
                fighter_pos = fighter.position
                if get_distance(unit.position, fighter_pos) > back_distance - 0.05:
                    self.go_back_points.remove(unit)
                    self.in_micro.remove(unit)
                    # print("Unit back", get_distance(unit.position, fighter_pos))
                    unit.attack(self.enemy_start_locations[0])

    async def queen_management(self):
        for queen in self.units(UnitTypeId.QUEEN):
            dist = get_distance(queen.position, self.start_location)

            if queen.is_idle and dist < 40:
                if queen.energy >= 25 and self.structures(UnitTypeId.HATCHERY).amount > 0:
                    queen(AbilityId.EFFECT_INJECTLARVA, self.townhalls.first)

            '''
            for second_queen in self.units(UnitTypeId.QUEEN): 
                if (10 > get_distance(queen.position, second_queen.position) > 0) and second_queen.health < second_queen.health_max * 0.6:
                    if AbilityId.TRANSFUSION_TRANSFUSION in abilities:
                        queen(AbilityId.TRANSFUSION_TRANSFUSION, second_queen)
                        print("Doing Transfusion")
            '''

    async def macro_element(self):
        first_base = self.townhalls.first
        if self.structures(UnitTypeId.EXTRACTOR).amount + self.already_pending(UnitTypeId.EXTRACTOR) < 2 and len(
                self.mining_drones) > 12:
            if self.can_afford(UnitTypeId.EXTRACTOR):
                for dronny in self.units(UnitTypeId.DRONE):
                    max_distance = 10
                    if not dronny.is_carrying_resource and get_distance(dronny.position,
                                                                        first_base.position) < max_distance:
                        target = self.vespene_geyser.closest_to(
                            dronny.position)  # "When building the gas structure, the target needs to be a unit (the vespene geysir) not the position of the vespene geyser."
                        dronny.build(UnitTypeId.EXTRACTOR, target)
                        if dronny not in self.building_workers:
                            self.building_workers.append(dronny)
                        return

        for extractor in self.structures(UnitTypeId.EXTRACTOR):
            if extractor.assigned_harvesters < extractor.ideal_harvesters:
                w = self.workers.closer_than(6, extractor)
                if w.exists:
                    w.random.gather(extractor)

        if self.structures(UnitTypeId.SPAWNINGPOOL).ready.exists:
            if not self.structures(UnitTypeId.LAIR).exists and not self.structures(
                    UnitTypeId.HIVE).exists and first_base.is_idle:
                if self.can_afford(UnitTypeId.LAIR):
                    first_base.build(UnitTypeId.LAIR)

        if self.structures(UnitTypeId.LAIR).ready.exists:
            if not (self.structures(UnitTypeId.SPIRE).exists or self.already_pending(UnitTypeId.SPIRE)):
                if self.can_afford(UnitTypeId.SPIRE):
                    dronny = self.units(UnitTypeId.DRONE).random
                    await self.build(UnitTypeId.SPIRE, build_worker=dronny, near=first_base)
                    if dronny not in self.building_workers:
                        self.building_workers.append(dronny)

        if self.structures(UnitTypeId.SPIRE).ready.exists:
            if self.units(UnitTypeId.LARVA).exists:
                larva = self.units(UnitTypeId.LARVA).random
                if self.can_afford(UnitTypeId.MUTALISK):
                    larva.train(UnitTypeId.MUTALISK)
                    return

    def no_units_in_opponent_main(self):
        for unit in self.units(UnitTypeId.DRONE) | self.units(UnitTypeId.ZERGLING) | self.units(UnitTypeId.QUEEN):
            if get_distance(unit.position, self.enemy_start_locations[0]) < 30:
                return False

        return True

    def proxy(self):
        for drone in self.units(UnitTypeId.DRONE):
            if get_distance(drone.position, self.start_location) > 100 and self.minerals >= 25:
                print("Building proxy")
                target = self.state.vespene_geyser.closest_to(drone.position)
                drone.build(UnitTypeId.EXTRACTOR, target)
                if drone not in self.building_workers:
                    self.building_workers.append(drone)
                break

    def prominent_structures(self):

        if self.enemy_race == Race.Terran:
            u = 30
        else:
            u = 50
        outcome = 0

        for structure in self.enemy_structures:
            if get_distance(structure.position, self.enemy_start_locations[0].position) < u:
                outcome += 1

        return outcome

    def null_wall_breakers(self):
        if len(self.units(UnitTypeId.ZERGLING)) > 0:
            for z in self.units(UnitTypeId.ZERGLING):
                if get_distance(z.position, self.enemy_start_locations[0]) < 13:
                    return True
        return False

    def check_wall_breakers(self, breakers_quantity):
        if len(self.wall_breakers) < breakers_quantity:
            for unit in self.units(UnitTypeId.DRONE):
                if (len(self.wall_breakers) < breakers_quantity) and (unit not in self.home_dronny) and (
                not unit.is_carrying_resource):
                    self.wall_breakers.append(unit)

    async def zvz_spine_crawler(self):
        self.check_wall_breakers(1)

        if self.canceled_crawl:
            breaker = self.refresh_unit(self.wall_breakers[0])
            if breaker is not None:
                if get_distance(breaker.position, self.enemy_locations()[0]) < 40:
                    breaker.gather(self.mineral_field[10])
                else:
                    breaker(AbilityId.STOP)
                    self.wall_breakers = []
                    self.stop_wall_breaker = True
                return
            else:
                self.wall_breakers = []
                self.stop_wall_breaker = True
                return

        if self.structures(UnitTypeId.SPINECRAWLER).amount + self.already_pending(UnitTypeId.SPINECRAWLER) == 0:

            for breaker in self.units(UnitTypeId.DRONE):
                if breaker in self.wall_breakers:

                    enemy_base_position = self.enemy_start_locations[0]
                    breaker_position = breaker.position

                    if not self.place:
                        self.place = enemy_base_position

                    d = get_distance(breaker_position, enemy_base_position)

                    delta_x = abs(breaker_position[0] - enemy_base_position[0])
                    delta_y = abs(breaker_position[1] - enemy_base_position[1])

                    # k, b = create_straight(breaker_position, enemy_base_position)  # y = kx + b

                    distance = 12

                    if delta_y >= delta_x > 2 and d < 15 and self.game_info.map_size[0] != 184 and \
                            self.game_info.map_size[1] != 168:
                        print("Go to x")

                        if self.start_location[1] >= enemy_base_position[1]:
                            good_point = sc2.position.Point2(
                                [enemy_base_position[0], enemy_base_position[1] + distance])
                        else:
                            good_point = sc2.position.Point2(
                                [enemy_base_position[0], enemy_base_position[1] - distance])

                        if d < distance - 1:
                            self.place = go_from_point(breaker_position, enemy_base_position, 1)
                        else:
                            self.place = good_point

                    elif (delta_x > delta_y > 2 and d < 15) or (
                            self.game_info.map_size[0] == 184 and self.game_info.map_size[1] == 168 and delta_y > 2):
                        print("Go to y")

                        if self.start_location[0] >= enemy_base_position[0]:
                            good_point = sc2.position.Point2(
                                [enemy_base_position[0] + distance, enemy_base_position[1]])
                        else:
                            good_point = sc2.position.Point2(
                                [enemy_base_position[0] - distance, enemy_base_position[1]])

                        if d < distance - 1:
                            self.place = go_from_point(breaker_position, enemy_base_position, 1)
                        else:
                            self.place = good_point

                    else:
                        if 10.55 <= d < distance + 0.3 and (
                                breaker.is_idle or self.place == enemy_base_position) and not self.stop_crawl:
                            # print(f"Distance between enemy base and drone for spine: {d}")

                            self.place = go_from_point(breaker_position, enemy_base_position, -0.1)

                        if self.place != enemy_base_position and self.minerals >= 100 and d < 11.2:
                            print(f"\nTry to build spine with distance: {d}")
                            result = await self.build(UnitTypeId.SPINECRAWLER, near=breaker, build_worker=breaker,
                                                      max_distance=0)
                            if result != ActionResult.CantFindPlacementLocation:
                                print("Spine is building\n")
                                self.stop_crawl = True

                    if not self.stop_crawl:
                        breaker.move(self.place)

        elif self.already_pending(UnitTypeId.SPINECRAWLER) > 0:
            for spine in self.structures(UnitTypeId.SPINECRAWLER):
                if spine.health < 17 and get_distance(spine.position, self.closest_enemy_unit(spine).position) < 3:
                    await self.chat_send("Ouch, my poor spine :(")
                    print("Cancelling spine")
                    spine(AbilityId.CANCEL)
                    self.stop_crawl = True
                    self.canceled_crawl = True

        '''
        else:
            spine = self.units(SPINECRAWLER)[0]
            abilities = await self.get_available_abilities(spine)

            if len(self.known_enemy_units) > 0:
                if get_distance(spine.position, self.closest_enemy_unit(spine).position) > 13:
                    if AbilityId.SPINECRAWLERUPROOT_SPINECRAWLERUPROOT in abilities:
                        await self.do(spine(AbilityId.SPINECRAWLERUPROOT_SPINECRAWLERUPROOT))

                elif get_distance(spine.position, self.closest_enemy_unit(spine).position) < 8:
                    if AbilityId.SPINECRAWLERROOT_SPINECRAWLERROOT in abilities:
                        await self.do(spine(SPINECRAWLERROOT_SPINECRAWLERROOT))

            if AbilityId.SPINECRAWLERROOT_SPINECRAWLERROOT in abilities:
                await self.do(spine.move(self.enemy_start_locations[0]))
        '''

        # SPINECRAWLERROOT_SPINECRAWLERROOT ; CANCEL_SPINECRAWLERROOT ;
        # SPINECRAWLERUPROOT_SPINECRAWLERUPROOT ; SPINECRAWLERUPROOT_CANCEL ;

    async def wall_breaker_do_block(self, breakers_quantity=1):

        if self.null_wall_breakers():
            self.wall_breakers = []
            self.stop_wall_breaker = True
            return

        self.check_wall_breakers(breakers_quantity)

        for breaker in self.units(UnitTypeId.DRONE):
            if breaker in self.wall_breakers and not breaker.is_carrying_resource and breaker.health > 5:

                if not self.have_moved_wall_breaker:
                    breaker.move(self.enemy_locations()[0])
                    self.selected_wall_breaker = breaker
                    self.have_moved_wall_breaker = True

                elif get_distance(breaker.position, self.start_location) < 8:
                    for drone in self.units(UnitTypeId.DRONE):
                        if drone == self.selected_wall_breaker:
                            if 40 < get_distance(drone.position, self.start_location) < 50:
                                breaker.move(self.enemy_locations()[0])
                                self.selected_wall_breaker = breaker

                if self.prominent_structures() >= 2:
                    if not self.begin_position and get_distance(breaker.position, self.enemy_start_locations[0]) < 40:
                        self.begin_position = breaker.position

                    if not self.place:
                        self.place = self.enemy_start_locations[0]

                    if self.begin_position:
                        # print(f"Distance between breaker positions (now and when he firstly saw enemy structures): {get_distance(breaker.position, self.begin_position)}")

                        if get_distance(self.enemy_structures[1].position, self.begin_position) < 6:
                            if self.enemy_race == Race.Terran:
                                itog_dist = 4.1
                            else:
                                itog_dist = 5.2
                        else:
                            itog_dist = 6.3

                        if get_distance(breaker.position, self.begin_position) > itog_dist \
                                and self.place == self.enemy_start_locations[0] \
                                and get_distance(breaker.position, self.enemy_start_locations[0]) < 40:
                            self.place = breaker.position

                        breaker.move(self.place)

            elif breaker.health <= 10 and get_distance(breaker.position, self.closest_enemy_unit(breaker).position) < 3:
                breaker.move(self.enemy_locations()[1])

    async def on_step(self, iteration):  # 168 iterations per minute ~ 3 iterations per second

        bases = self.structures(UnitTypeId.HATCHERY) | self.structures(UnitTypeId.LAIR) | self.structures(
            UnitTypeId.HIVE)
        bases_amount = self.structures(UnitTypeId.HATCHERY).amount + self.structures(
            UnitTypeId.LAIR).amount + self.structures(UnitTypeId.HIVE).amount
        if self.units(UnitTypeId.DRONE).amount > 0 and bases_amount > 0 and self.mineral_field.amount > 0:

            drones = []
            for drone in self.units(UnitTypeId.DRONE):

                if (drone not in self.wall_breakers) and (drone not in self.attack_drones) and (
                        drone not in self.building_workers) and get_distance(drone.position, self.closest_unit(bases,
                                                                                                               drone).position) < 20:
                    drones.append(drone)

            self.mining_drones = drones

            try:
                self.refresh_mining_data(drones)  # (self, drones)
                await self.speed_mining()  # (self), imported functions

            except BaseException:
                print("Mining exception")

        # if self.state.game_loop % (22.4 * 5) == 0:
        #    logger.info(f"{self.time_formatted} Mined a total of {int(self.state.score.collected_minerals)} minerals")

        # if iteration % 30 == 0:
        #   print(f"\n{len(drones)} drones:\n{self.mining_mineral_data}\n{self.mining_hatchery_data}\n")

        if self.enemy_race == Race.Terran:
            len_home_dronny = 3

        elif self.enemy_race == Race.Protoss or self.enemy_race == Race.Random:
            len_home_dronny = 2

        else:
            len_home_dronny = 1  # +1

        if self.units(UnitTypeId.ZERGLING).amount >= 40:
            self.stop_zergling = True
            if self.enemy_race == Race.Terran and not self.need_to_attack_main_base:
                self.need_air_units = True

        elif self.stop_zergling:
            self.stop_zergling = False

        if not self.units(UnitTypeId.DRONE).exists and self.minerals < 50:
            self.need_air_units = False

        if self.home_dronny.amount == 0:
            await self.distribute_workers()

        await self.overlord_management()

        await self.queen_management()

        await self.micro_element()

        if (self.home_dronny.amount == 0) or (
                self.need_air_units and self.home_dronny.amount < self.units(UnitTypeId.DRONE).amount):
            for drone in self.units(UnitTypeId.DRONE):
                if self.home_dronny.amount == len_home_dronny and not self.need_air_units:
                    break
                else:
                    self.home_dronny.append(drone)

        if iteration == 30:
            await self.chat_send("gl hf!")
            print(
                f"\nOpponent_id: {self.opponent_id}\n\nMap size: {self.game_info.map_size[0]} {self.game_info.map_size[1]}\n\nStart location: {self.start_location.position[0]} {self.start_location[1]}")

        if len(self.locations) == 0:
            self.locations = self.get_locations()

        larvae = self.units(UnitTypeId.LARVA)

        forces = self.units(UnitTypeId.DRONE) | self.units(UnitTypeId.ZERGLING) | self.units(UnitTypeId.MUTALISK)

        if self.enemy_units(UnitTypeId.BROODLING).exists:
            for unit in forces:
                if unit not in self.home_dronny:
                    unit.move(self.start_location)
            return

        if not self.townhalls.exists:
            for unit in self.units(UnitTypeId.QUEEN) | forces:
                unit.attack(self.enemy_start_locations[0])
            return
        else:
            first_base = self.townhalls.first
            if first_base.health < 401:
                self.proxy()
                return

        if not self.units(UnitTypeId.ZERGLING).exists:
            await self.defending()

        else:
            self.defence = False

        # BUILDORDER STOPS

        if (not self.stop_drone) and (self.units(UnitTypeId.DRONE).amount == 14 or (not (
                self.structures(UnitTypeId.SPAWNINGPOOL).exists or self.already_pending(
                UnitTypeId.SPAWNINGPOOL)))) and not self.d_structures():
            self.stop_drone = True

        elif self.stop_drone and (
                self.structures(UnitTypeId.SPAWNINGPOOL).exists or self.already_pending(UnitTypeId.SPAWNINGPOOL)) and (
                self.units(UnitTypeId.DRONE).amount != 14 or self.need_air_units):
            self.stop_drone = False

        # BUILDING DRONES

        if len(self.mining_drones) < first_base.ideal_harvesters and (self.need_air_units or not self.stop_drone):
            if self.can_afford(UnitTypeId.DRONE) and larvae.exists:
                self.train(UnitTypeId.DRONE)

        # BUILDING SPAWNING POOL
        if not self.dronny:
            self.dronny = self.closest_unit(
                [unit for unit in self.units(UnitTypeId.DRONE) if not unit.is_carrying_resource],
                self.enemy_start_locations[0])

        if self.structures(UnitTypeId.SPAWNINGPOOL).amount + self.already_pending(UnitTypeId.SPAWNINGPOOL) == 0:
            dronny = self.refresh_unit(self.dronny)
            distance = 8
            if self.time < 70:
                if 200 > self.minerals > 140 and not dronny.is_carrying_resource and get_distance(dronny.position,
                                                                                                  self.start_location) < distance:
                    dronny.move(self.enemy_start_locations[0])
                    if dronny not in self.building_workers:
                        self.building_workers.append(dronny)

                elif self.can_afford(UnitTypeId.SPAWNINGPOOL):
                    await self.build(UnitTypeId.SPAWNINGPOOL, build_worker=dronny, near=dronny)
                    if dronny not in self.building_workers:
                        self.building_workers.append(dronny)

                elif get_distance(dronny.position, self.start_location) >= distance and self.minerals > 160:
                    dronny.move(dronny.position)

            elif self.minerals >= 200 and self.units(UnitTypeId.DRONE).amount > 0:
                dronny = self.units(UnitTypeId.DRONE).random
                await self.build(UnitTypeId.SPAWNINGPOOL, build_worker=dronny, near=first_base)
                if dronny not in self.building_workers:
                    self.building_workers.append(dronny)

        if (self.supply_left < 1 or (self.need_air_units and self.supply_left < 4)) and not self.already_pending(
                UnitTypeId.OVERLORD):
            if self.can_afford(UnitTypeId.OVERLORD) and larvae.exists:
                larvae.random.train(UnitTypeId.OVERLORD)

        # GOING MACRO

        if self.need_air_units:
            if self.units(UnitTypeId.MUTALISK).amount > 4:
                self.need_air_units = False
            else:
                await self.macro_element()
                # return

            if len(self.mining_drones) < self.units(UnitTypeId.DRONE).amount - 5:
                self.home_dronny = Units([], self)

        if self.structures(UnitTypeId.SPAWNINGPOOL).ready.exists and not self.stop_zergling:

            if self.can_afford(UnitTypeId.ZERGLING) and larvae.exists:
                larvae.random.train(UnitTypeId.ZERGLING)

            if first_base.is_idle:  # (self.minerals >= 300 or (self.minerals >= 200 and self.units(UnitTypeId.ZERGLING).amount >= 6))

                larvae_amount = larvae.amount
                if len(self.mining_drones) >= 10:
                    min_minerals = 150 + larvae_amount * 50
                else:
                    min_minerals = 200 + larvae_amount * 50

                if (self.enemy_race == Race.Zerg or self.enemy_race == Race.Random) and (
                        self.structures(UnitTypeId.SPINECRAWLER).amount + self.already_pending(
                        UnitTypeId.SPINECRAWLER) == 0):
                    min_minerals += 150

                if self.minerals >= min_minerals:
                    first_base.train(UnitTypeId.QUEEN)

        # WALL BREAKER

        if self.units(UnitTypeId.OVERLORD).exists and self.need_to_attack_main_base and not self.stop_wall_breaker:

            if self.enemy_race == Race.Terran:
                begin_time = 55

            elif self.enemy_race == Race.Protoss:  # breakers_quantity = 2 better
                begin_time = 45

            elif self.enemy_race == Race.Zerg:
                begin_time = 35

            else:  # Race = Random
                begin_time = 45

            if self.time > begin_time:

                if self.enemy_race != Race.Zerg:
                    await self.wall_breaker_do_block(breakers_quantity=1)
                else:
                    await self.zvz_spine_crawler()

        # CANNON PROBLEM

        if self.d_structures() and (self.no_units_in_opponent_main() or not self.need_to_attack_main_base):
            dist_with_dangerous_structures = get_distance(self.enemy_dangerous_structures()[0].position,
                                                          self.start_location.position)

            if dist_with_dangerous_structures > 100 or (not self.need_to_attack_main_base):

                if self.units(UnitTypeId.ZERGLING).amount < 25:
                    self.stop_drone = False
                    return

        # STOPPING ATTACK WITH DRONES

        if self.time > self.stop_new_drone_attack_time:
            for drone in self.units(UnitTypeId.DRONE):
                if drone not in self.home_dronny and get_distance(drone.position,
                                                                  self.start_location) < 10 and drone not in self.attack_drones:  # not drone.is_idle and get_distance(drone.position, self.start_location) < 20
                    self.home_dronny.append(drone)

        # ATTACK

        if (self.units(UnitTypeId.ZERGLING).amount > 0 or (
                not self.no_units_in_opponent_main() and self.time > 100)) and self.need_to_attack_main_base:
            # group
            if not self.stop_group and self.units(UnitTypeId.ZERGLING).amount <= 25:

                middle_unit = self.closest_unit(self.units(UnitTypeId.ZERGLING), self.enemy_start_locations[0])
                max_distance = 15  # from middle unit
                max_middle_group_dist = 3.2
                if self.need_group(middle_unit, max_distance, max_middle_group_dist):
                    await self.group_units(middle_unit, max_distance)
                    return

            for unit in forces:
                if (unit not in self.in_micro) and (unit not in self.wall_breakers) and (
                        unit not in self.home_dronny) and (not unit.is_carrying_resource):
                    if self.enemy_units.exists:

                        for enemy_unit in self.enemy_units:
                            if (enemy_unit not in self.known_enemy_u) and (
                                    enemy_unit not in self.enemy_structures) and (
                                    enemy_unit not in self.enemy_units(UnitTypeId.LARVA)) and (
                            not enemy_unit.is_flying):
                                self.known_enemy_u.append(enemy_unit)

                        for j in self.known_enemy_u:
                            if j not in self.enemy_units:
                                self.known_enemy_u.remove(j)

                        if len(self.known_enemy_u) > 0 and get_distance(unit.position,
                                                                        self.closest_enemy_unit(unit).position) < 3:
                            unit.attack(self.closest_enemy_unit(unit).position)

                        elif (get_distance(unit.position, self.enemy_start_locations[0]) < 7) or (
                                unit.health_max - unit.health > 0):
                            unit.attack(self.enemy_start_locations[0])

                        else:
                            unit.move(self.enemy_start_locations[0])

                    else:
                        unit.move(self.enemy_start_locations[0])

                for queen in self.units(UnitTypeId.QUEEN):
                    if queen.is_idle:
                        queen.attack(self.enemy_start_locations[0])

        elif not self.need_to_attack_main_base:
            self.wall_breakers = []
            # print("Now, we don`t need to attack enemies main")
            if len(self.enemy_structures) > 0 and not self.all_known_structures_flying():
                for enemy_struct in self.enemy_structures:
                    for unit in forces:
                        if unit not in self.home_dronny and unit.is_idle:
                            unit.attack(enemy_struct.position)
                    self.in_scout = []

            elif len(self.enemy_units) > 0 and not self.all_flying_enemies():
                for unit in forces:
                    if unit not in self.home_dronny:
                        unit.attack(self.enemy_units[0].position)
                self.in_scout = []

            else:
                # print("Map scout")
                await self.map_scout()

                if self.enemy_structures.exists and self.units(UnitTypeId.QUEEN).exists:
                    for queen in self.units(UnitTypeId.QUEEN):
                        if queen.is_idle:
                            queen.attack(self.enemy_structures[0])

                if (not self.need_air_units) and (self.all_known_structures_flying()) and (
                not self.units(UnitTypeId.MUTALISK).exists):
                    await self.chat_send("Do not try to escape from me!")
                    self.need_air_units = True

                if self.units(UnitTypeId.MUTALISK).exists and len(self.enemy_structures) > 0:
                    for muta in self.units(UnitTypeId.MUTALISK):
                        if muta.is_idle:
                            muta.attack(self.enemy_structures[0])

                elif len(self.enemy_structures) == 0 and self.units(UnitTypeId.MUTALISK).exists:
                    for unit in forces:
                        if unit.is_idle:
                            unit.attack(sc2.position.Point2([random.randint(0, int(self.game_info.map_size[0])),
                                                             random.randint(0, int(self.game_info.map_size[1]))]))

        # STARTING ATTACK
        elif self.stop_drone and self.units(UnitTypeId.OVERLORD).amount == 2 and self.units(
                UnitTypeId.EGG).exists and self.time < self.stop_new_drone_attack_time:

            eggs = self.units(UnitTypeId.EGG)
            if eggs.amount == 4:
                for drone in self.units(UnitTypeId.DRONE):
                    if (drone not in self.home_dronny) and (drone not in self.wall_breakers) and (
                    not drone.is_carrying_resource):
                        drone.move(self.enemy_start_locations[0])
                        if drone not in self.attack_drones:
                            self.attack_drones.append(drone)

                self.stop_new_drone_attack_time = self.time + 8

        if self.need_to_attack_main_base:
            for i in forces:
                dist = get_distance(i.position, self.enemy_start_locations[0])

                if dist < 1:
                    if len(self.known_enemy_u) > 0:
                        if get_distance(i.position, self.closest_enemy_unit(i).position) > 4:
                            await self.chat_send("We won opponent`s main!")
                            self.need_to_attack_main_base = False
                            break

                    else:
                        await self.chat_send("We won opponent`s main!")
                        self.need_to_attack_main_base = False
                        break


def main():
    run_game(sc2.maps.get("2000AtmospheresAIE"), [  # 2000AtmospheresAIE ; CatalystLE ; AbyssalReefLE
        # Human(Race.Zerg),                         # JagannathaAIE ; BlackburnAIE ; OxideAIE
        # Bot(Race.Zerg, SmallBly()),
        Bot(Race.Zerg, SmallBly()),
        Computer(Race.Zerg, Difficulty.VeryHard),
    ], realtime=True,
             disable_fog=False,
             random_seed=1
             # save_replay_as="smallBly_vs_smallBly_20-06-2022.SC2Replay",
             )


if __name__ == '__main__':
    main()

