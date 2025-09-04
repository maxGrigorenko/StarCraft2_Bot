from sc2.units import Units
from sc2.ids.unit_typeid import UnitTypeId
from coordinate_functions import *
from sc2.data import Race, ActionResult
from sc2.ids.ability_id import AbilityId
from _universal_functions import *
from _speed_mining import *


def prominent_structures(self):
    if self.enemy_race == Race.Terran:
        min_dist = 30
    else:
        min_dist = 50

    outcome = 0
    for structure in self.enemy_structures:
        if get_distance(structure.position, self.enemy_start_locations[0].position) < min_dist:
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

        else:
            if len(self.all_enemy_units) > 0:
                if breaker.health <= 10 and get_distance(breaker.position, self.closest_enemy_unit(breaker).position) < 3:
                    breaker.move(self.enemy_locations()[1])


async def zergling_drone_rush_step(self, iteration):
    await self.mining_iteration()
    await self.overlord_management()
    await self.queen_management()
    await self.micro_element()

    if self.enemy_race == Race.Terran:
        home_dronny_amount = 3
    elif self.enemy_race == Race.Protoss or self.enemy_race == Race.Random:
        home_dronny_amount = 2
    else:
        home_dronny_amount = 1  # +1

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

    if (self.home_dronny.amount == 0) or (
            self.need_air_units and self.home_dronny.amount < self.units(UnitTypeId.DRONE).amount):
        for drone in self.units(UnitTypeId.DRONE):
            if self.home_dronny.amount == home_dronny_amount and not self.need_air_units:
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
    forces = self.units(UnitTypeId.DRONE) | self.units(UnitTypeId.ZERGLING) | self.units(UnitTypeId.ROACH) | self.units(
        UnitTypeId.MUTALISK)

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
        UnitTypeId.SPAWNINGPOOL)))) and not self.dangerous_structures_exist():
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

    if self.dangerous_structures_exist() and (self.no_units_in_opponent_main() or not self.need_to_attack_main_base):
        dist_with_dangerous_structures = get_distance(self.enemy_dangerous_structures()[0].position,
                                                      self.start_location.position)

        if dist_with_dangerous_structures > 100 or (not self.need_to_attack_main_base):

            if self.units(UnitTypeId.ZERGLING).amount < 25 and self.time > 200:
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

                for unit_in_known in self.known_enemy_u:
                    if unit_in_known not in self.enemy_units:
                        self.known_enemy_u.remove(unit_in_known)

                if self.enemy_units.exists:
                    for enemy_unit in self.enemy_units:
                        if (enemy_unit not in self.known_enemy_u) and (
                                enemy_unit not in self.enemy_structures) and (
                                enemy_unit not in self.enemy_units(UnitTypeId.LARVA)) and (
                                not enemy_unit.is_flying):
                            self.known_enemy_u.append(enemy_unit)

                    if len(self.known_enemy_u) > 0 and get_distance(unit.position,
                                                                    self.closest_enemy_unit(unit).position) < 3:
                        unit.attack(self.closest_enemy_unit(unit).position)

                    elif get_distance(unit.position, self.enemy_start_locations[0]) < 7:
                        unit.attack(self.enemy_start_locations[0])

                    elif unit.health_max - unit.health > 0:
                        self.accurate_attack(unit, attack_on_way=True)

                    else:
                        # unit.move(self.enemy_start_locations[0])
                        self.accurate_attack(unit, attack_on_way=False)

                else:
                    # unit.move(self.enemy_start_locations[0])
                    self.accurate_attack(unit, attack_on_way=False)

        self.manage_queen_attack()

    elif not self.need_to_attack_main_base:
        await self.find_final_structures(forces=forces, army=(self.units(UnitTypeId.DRONE) | self.units(UnitTypeId.ZERGLING)))

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
        await self.is_opponents_main_won()

