from sc2.units import Units
from sc2.ids.unit_typeid import UnitTypeId
from sc2.data import Race, ActionResult
from sc2.ids.ability_id import AbilityId
from src.utils.coordinate_functions import *
from src.utils.universal_functions import *
from src.utils.speed_mining import *


class ZerglingDroneStrategy:
    
    def __init__(self, bot):
        self.bot = bot
    
    def prominent_structures(self):
        if self.bot.enemy_race == Race.Terran:
            min_dist = 30
        else:
            min_dist = 50
    
        outcome = 0
        for structure in self.bot.enemy_structures:
            if get_distance(structure.position, self.bot.enemy_start_locations[0].position) < min_dist:
                outcome += 1
    
        return outcome

    def null_wall_breakers(self):
        if len(self.bot.units(UnitTypeId.ZERGLING)) > 0:
            for z in self.bot.units(UnitTypeId.ZERGLING):
                if get_distance(z.position, self.bot.enemy_start_locations[0]) < 13:
                    return True
        return False

    def check_wall_breakers(self, breakers_quantity):
        if len(self.bot.wall_breakers) < breakers_quantity:
            for unit in self.bot.units(UnitTypeId.DRONE):
                if (len(self.bot.wall_breakers) < breakers_quantity) and (unit not in self.bot.home_dronny) and (
                        not unit.is_carrying_resource):
                    self.bot.wall_breakers.append(unit)

    async def zvz_spine_crawler(self):
        self.check_wall_breakers(1)
    
        if self.bot.canceled_crawl:
            breaker = self.bot.refresh_unit(self.bot.wall_breakers[0])
            if breaker is not None:
                if get_distance(breaker.position, self.bot.sorted_enemy_locations()[0]) < 40:
                    breaker.gather(self.bot.mineral_field[10])
                else:
                    breaker(AbilityId.STOP)
                    self.bot.wall_breakers = []
                    self.bot.stop_wall_breaker = True
                return
            else:
                self.bot.wall_breakers = []
                self.bot.stop_wall_breaker = True
                return
    
        if self.bot.structures(UnitTypeId.SPINECRAWLER).amount + self.bot.already_pending(UnitTypeId.SPINECRAWLER) == 0:
    
            for breaker in self.bot.units(UnitTypeId.DRONE):
                if breaker in self.bot.wall_breakers:
    
                    enemy_base_position = self.bot.enemy_start_locations[0]
                    breaker_position = breaker.position
    
                    if not self.bot.place:
                        self.bot.place = enemy_base_position
    
                    d = get_distance(breaker_position, enemy_base_position)
    
                    delta_x = abs(breaker_position[0] - enemy_base_position[0])
                    delta_y = abs(breaker_position[1] - enemy_base_position[1])
    
                    # k, b = create_straight(breaker_position, enemy_base_position)  # y = kx + b
    
                    distance = 12
    
                    if delta_y >= delta_x > 2 and d < 15 and self.bot.game_info.map_size[0] != 184 and \
                            self.bot.game_info.map_size[1] != 168:
                        print("Go to x")
    
                        if self.bot.start_location[1] >= enemy_base_position[1]:
                            good_point = sc2.position.Point2(
                                [enemy_base_position[0], enemy_base_position[1] + distance])
                        else:
                            good_point = sc2.position.Point2(
                                [enemy_base_position[0], enemy_base_position[1] - distance])
    
                        if d < distance - 1:
                            self.bot.place = go_from_point(breaker_position, enemy_base_position, 1)
                        else:
                            self.bot.place = good_point
    
                    elif (delta_x > delta_y > 2 and d < 15) or (
                            self.bot.game_info.map_size[0] == 184 and self.bot.game_info.map_size[1] == 168 and delta_y > 2):
                        print("Go to y")
    
                        if self.bot.start_location[0] >= enemy_base_position[0]:
                            good_point = sc2.position.Point2(
                                [enemy_base_position[0] + distance, enemy_base_position[1]])
                        else:
                            good_point = sc2.position.Point2(
                                [enemy_base_position[0] - distance, enemy_base_position[1]])
    
                        if d < distance - 1:
                            self.bot.place = go_from_point(breaker_position, enemy_base_position, 1)
                        else:
                            self.bot.place = good_point
    
                    else:
                        if 10.55 <= d < distance + 0.3 and (
                                breaker.is_idle or self.bot.place == enemy_base_position) and not self.bot.stop_crawl:
                            # print(f"Distance between enemy base and drone for spine: {d}")
    
                            self.bot.place = go_from_point(breaker_position, enemy_base_position, -0.1)
    
                        if self.bot.place != enemy_base_position and self.bot.minerals >= 100 and d < 11.2:
                            print(f"\nTry to build spine with distance: {d}")
                            result = await self.bot.build(UnitTypeId.SPINECRAWLER, near=breaker, build_worker=breaker,
                                                      max_distance=0)
                            if result != ActionResult.CantFindPlacementLocation:
                                print("Spine is building\n")
                                self.bot.stop_crawl = True
    
                    if not self.bot.stop_crawl:
                        breaker.move(self.bot.place)
    
        elif self.bot.already_pending(UnitTypeId.SPINECRAWLER) > 0:
            for spine in self.bot.structures(UnitTypeId.SPINECRAWLER):
                if spine.health < 17 and get_distance(spine.position, self.bot.closest_enemy_unit(spine).position) < 3:
                    await self.bot.chat_send("Ouch, my poor spine :(")
                    print("Cancelling spine")
                    spine(AbilityId.CANCEL)
                    self.bot.stop_crawl = True
                    self.bot.canceled_crawl = True
    
        '''
        else:
            spine = self.bot.units(SPINECRAWLER)[0]
            abilities = await self.bot.get_available_abilities(spine)
    
            if len(self.bot.known_enemy_units) > 0:
                if get_distance(spine.position, self.bot.closest_enemy_unit(spine).position) > 13:
                    if AbilityId.SPINECRAWLERUPROOT_SPINECRAWLERUPROOT in abilities:
                        await self.bot.do(spine(AbilityId.SPINECRAWLERUPROOT_SPINECRAWLERUPROOT))
    
                elif get_distance(spine.position, self.bot.closest_enemy_unit(spine).position) < 8:
                    if AbilityId.SPINECRAWLERROOT_SPINECRAWLERROOT in abilities:
                        await self.bot.do(spine(SPINECRAWLERROOT_SPINECRAWLERROOT))
    
            if AbilityId.SPINECRAWLERROOT_SPINECRAWLERROOT in abilities:
                await self.bot.do(spine.move(self.bot.enemy_start_locations[0]))
        '''
    
        # SPINECRAWLERROOT_SPINECRAWLERROOT ; CANCEL_SPINECRAWLERROOT ;
        # SPINECRAWLERUPROOT_SPINECRAWLERUPROOT ; SPINECRAWLERUPROOT_CANCEL ;

    async def wall_breaker_do_block(self, breakers_quantity=1):
        if self.null_wall_breakers():
            self.bot.wall_breakers = []
            self.bot.stop_wall_breaker = True
            return
    
        self.check_wall_breakers(breakers_quantity)
    
        for breaker in self.bot.units(UnitTypeId.DRONE):
            if breaker in self.bot.wall_breakers and not breaker.is_carrying_resource and breaker.health > 5:
    
                if not self.bot.have_moved_wall_breaker:
                    breaker.move(self.bot.sorted_enemy_locations()[0])
                    self.bot.selected_wall_breaker = breaker
                    self.bot.have_moved_wall_breaker = True
    
                elif get_distance(breaker.position, self.bot.start_location) < 8:
                    for drone in self.bot.units(UnitTypeId.DRONE):
                        if drone == self.bot.selected_wall_breaker:
                            if 40 < get_distance(drone.position, self.bot.start_location) < 50:
                                breaker.move(self.bot.sorted_enemy_locations()[0])
                                self.bot.selected_wall_breaker = breaker
    
                if self.prominent_structures() >= 2:
                    if not self.bot.begin_position and get_distance(breaker.position, self.bot.enemy_start_locations[0]) < 40:
                        self.bot.begin_position = breaker.position
    
                    if not self.bot.place:
                        self.bot.place = self.bot.enemy_start_locations[0]
    
                    if self.bot.begin_position:
                        # print(f"Distance between breaker positions (now and when he firstly saw enemy structures): {get_distance(breaker.position, self.bot.begin_position)}")
    
                        if get_distance(self.bot.enemy_structures[1].position, self.bot.begin_position) < 6:
                            if self.bot.enemy_race == Race.Terran:
                                itog_dist = 4.1
                            else:
                                itog_dist = 5.2
                        else:
                            itog_dist = 6.3
    
                        if get_distance(breaker.position, self.bot.begin_position) > itog_dist \
                                and self.bot.place == self.bot.enemy_start_locations[0] \
                                and get_distance(breaker.position, self.bot.enemy_start_locations[0]) < 40:
                            self.bot.place = breaker.position
    
                        breaker.move(self.bot.place)
    
            else:
                if len(self.bot.all_enemy_units) > 0:
                    if breaker.health <= 10 and get_distance(breaker.position, self.bot.closest_enemy_unit(breaker).position) < 3:
                        breaker.move(self.bot.sorted_enemy_locations()[1])

    async def zergling_drone_rush_step(self, iteration):
        await self.bot.mining_iteration()
        await self.bot.overlord_manager.manage(overlords=self.bot.units(UnitTypeId.OVERLORD),
                                           enemies=self.bot.air_danger_units())
        await self.bot.queen_management()
        await self.bot.micro_element()
    
        if self.bot.enemy_race == Race.Terran:
            home_dronny_amount = 3
        elif self.bot.enemy_race == Race.Protoss or self.bot.enemy_race == Race.Random:
            home_dronny_amount = 2
        else:
            home_dronny_amount = 1  # +1
    
        if self.bot.units(UnitTypeId.ZERGLING).amount >= 40:
            self.bot.stop_zergling = True
            if self.bot.enemy_race == Race.Terran and not self.bot.need_to_attack_main_base:
                self.bot.need_air_units = True
        elif self.bot.stop_zergling:
            self.bot.stop_zergling = False
    
        if not self.bot.units(UnitTypeId.DRONE).exists and self.bot.minerals < 50:
            self.bot.need_air_units = False
    
        if self.bot.home_dronny.amount == 0:
            await self.bot.distribute_workers()
    
        if (self.bot.home_dronny.amount == 0) or (
                self.bot.need_air_units and self.bot.home_dronny.amount < self.bot.units(UnitTypeId.DRONE).amount):
            for drone in self.bot.units(UnitTypeId.DRONE):
                if self.bot.home_dronny.amount == home_dronny_amount and not self.bot.need_air_units:
                    break
                else:
                    self.bot.home_dronny.append(drone)
    
        if iteration == 30:
            await self.bot.chat_send("gl hf!")
            print(
                f"\nOpponent_id: {self.bot.opponent_id}\n\nMap size: {self.bot.game_info.map_size[0]} {self.bot.game_info.map_size[1]}\n\nStart location: {self.bot.start_location.position[0]} {self.bot.start_location[1]}")
    
        if len(self.bot.locations) == 0:
            self.bot.locations = self.bot.get_locations()
    
        larvae = self.bot.units(UnitTypeId.LARVA)
        forces = self.bot.units(UnitTypeId.DRONE) | self.bot.units(UnitTypeId.ZERGLING) | self.bot.units(UnitTypeId.ROACH) | self.bot.units(
            UnitTypeId.MUTALISK)
    
        if self.bot.enemy_units(UnitTypeId.BROODLING).exists:
            for unit in forces:
                if unit not in self.bot.home_dronny:
                    unit.move(self.bot.start_location)
            return
    
        if not self.bot.townhalls.exists:
            for unit in self.bot.units(UnitTypeId.QUEEN) | forces:
                unit.attack(self.bot.enemy_start_locations[0])
            return
        else:
            first_base = self.bot.townhalls.first
            if first_base.health < 401:
                self.bot.proxy()
                return
    
        if not self.bot.units(UnitTypeId.ZERGLING).exists:
            await self.bot.defending()
        else:
            self.bot.defence = False
    
        # BUILDORDER STOPS
    
        if (not self.bot.stop_drone) and (self.bot.units(UnitTypeId.DRONE).amount == 14 or (not (
                self.bot.structures(UnitTypeId.SPAWNINGPOOL).exists or self.bot.already_pending(
            UnitTypeId.SPAWNINGPOOL)))) and not self.bot.dangerous_structures_exist():
            self.bot.stop_drone = True
    
        elif self.bot.stop_drone and (
                self.bot.structures(UnitTypeId.SPAWNINGPOOL).exists or self.bot.already_pending(UnitTypeId.SPAWNINGPOOL)) and (
                self.bot.units(UnitTypeId.DRONE).amount != 14 or self.bot.need_air_units) and not self.bot.defence:
            self.bot.stop_drone = False
    
        # BUILDING DRONES
    
        if len(self.bot.mining_drones) < first_base.ideal_harvesters and (self.bot.need_air_units or not self.bot.stop_drone) and not self.bot.defence:
            if self.bot.can_afford(UnitTypeId.DRONE) and larvae.exists:
                self.bot.train(UnitTypeId.DRONE)
    
        # BUILDING SPAWNING POOL
    
        if not self.bot.dronny:
            self.bot.dronny = self.bot.closest_unit(
                [unit for unit in self.bot.units(UnitTypeId.DRONE) if not unit.is_carrying_resource],
                self.bot.enemy_start_locations[0])
    
        if self.bot.structures(UnitTypeId.SPAWNINGPOOL).amount + self.bot.already_pending(UnitTypeId.SPAWNINGPOOL) == 0:
            dronny = self.bot.refresh_unit(self.bot.dronny)
            distance = 8
            if self.bot.time < 70:
                if 200 > self.bot.minerals > 140 and not dronny.is_carrying_resource and get_distance(dronny.position,
                                                                                                  self.bot.start_location) < distance:
                    dronny.move(self.bot.enemy_start_locations[0])
                    if dronny not in self.bot.building_workers:
                        self.bot.building_workers.append(dronny)
    
                elif self.bot.can_afford(UnitTypeId.SPAWNINGPOOL):
                    await self.bot.build(UnitTypeId.SPAWNINGPOOL, build_worker=dronny, near=dronny)
                    if dronny not in self.bot.building_workers:
                        self.bot.building_workers.append(dronny)
    
                elif get_distance(dronny.position, self.bot.start_location) >= distance and self.bot.minerals > 160:
                    dronny.move(dronny.position)
    
            elif self.bot.minerals >= 200 and self.bot.units(UnitTypeId.DRONE).amount > 0:
                dronny = self.bot.units(UnitTypeId.DRONE).random
                await self.bot.build(UnitTypeId.SPAWNINGPOOL, build_worker=dronny, near=first_base)
                if dronny not in self.bot.building_workers:
                    self.bot.building_workers.append(dronny)
    
        if (self.bot.supply_left < 1 or (self.bot.need_air_units and self.bot.supply_left < 4)) and not self.bot.already_pending(
                UnitTypeId.OVERLORD):
            if self.bot.can_afford(UnitTypeId.OVERLORD) and larvae.exists:
                larvae.random.train(UnitTypeId.OVERLORD)
    
        # GOING MACRO
    
        if self.bot.need_air_units:
            if self.bot.units(UnitTypeId.MUTALISK).amount > 4:
                self.bot.need_air_units = False
            else:
                await self.bot.macro_element()
                # return
    
            if len(self.bot.mining_drones) < self.bot.units(UnitTypeId.DRONE).amount - 5:
                self.bot.home_dronny = Units([], self.bot)
    
        if self.bot.structures(UnitTypeId.SPAWNINGPOOL).ready.exists and not self.bot.stop_zergling:
    
            if self.bot.can_afford(UnitTypeId.ZERGLING) and larvae.exists:
                larvae.random.train(UnitTypeId.ZERGLING)
    
            if first_base.is_idle:  # (self.bot.minerals >= 300 or (self.bot.minerals >= 200 and self.bot.units(UnitTypeId.ZERGLING).amount >= 6))
    
                larvae_amount = larvae.amount
                if len(self.bot.mining_drones) >= 10:
                    min_minerals = 150 + larvae_amount * 50
                else:
                    min_minerals = 200 + larvae_amount * 50
    
                if (self.bot.enemy_race == Race.Zerg or self.bot.enemy_race == Race.Random) and (
                        self.bot.structures(UnitTypeId.SPINECRAWLER).amount + self.bot.already_pending(
                    UnitTypeId.SPINECRAWLER) == 0):
                    min_minerals += 150
    
                if self.bot.minerals >= min_minerals:
                    first_base.train(UnitTypeId.QUEEN)
    
        # WALL BREAKER
    
        if self.bot.units(UnitTypeId.OVERLORD).exists and self.bot.need_to_attack_main_base and not self.bot.stop_wall_breaker:
    
            if self.bot.enemy_race == Race.Terran:
                begin_time = 55
    
            elif self.bot.enemy_race == Race.Protoss:  # breakers_quantity = 2 better
                begin_time = 45
    
            elif self.bot.enemy_race == Race.Zerg:
                begin_time = 35
    
            else:  # Race = Random
                begin_time = 45
    
            if self.bot.time > begin_time:
    
                if self.bot.enemy_race != Race.Zerg:
                    await self.wall_breaker_do_block(breakers_quantity=1)
                else:
                    await self.zvz_spine_crawler()
    
        # CANNON PROBLEM
    
        if self.bot.dangerous_structures_exist() and (self.bot.no_units_in_opponent_main() or not self.bot.need_to_attack_main_base):
            dist_with_dangerous_structures = get_distance(self.bot.enemy_dangerous_structures()[0].position,
                                                          self.bot.start_location.position)
    
            if dist_with_dangerous_structures > 100 or (not self.bot.need_to_attack_main_base):
    
                if self.bot.units(UnitTypeId.ZERGLING).amount < 25 and self.bot.time > 200:
                    self.bot.stop_drone = False
                    return
    
        # STOPPING ATTACK WITH DRONES
    
        if self.bot.time > self.bot.stop_new_drone_attack_time:
            for drone in self.bot.units(UnitTypeId.DRONE):
                if drone not in self.bot.home_dronny and get_distance(drone.position,
                                                                  self.bot.start_location) < 10 and drone not in self.bot.attack_drones:  # not drone.is_idle and get_distance(drone.position, self.bot.start_location) < 20
                    self.bot.home_dronny.append(drone)
    
        # ATTACK
    
        if (self.bot.units(UnitTypeId.ZERGLING).amount > 0 or (
                not self.bot.no_units_in_opponent_main() and self.bot.time > 100)) and self.bot.need_to_attack_main_base:
            # group
            if not self.bot.stop_group and self.bot.units(UnitTypeId.ZERGLING).amount <= 25:
                middle_unit = self.bot.closest_unit(self.bot.units(UnitTypeId.ZERGLING), self.bot.enemy_start_locations[0])
                max_distance = 15  # from middle unit
                max_middle_group_dist = 3.2
                if self.bot.need_group(middle_unit, max_distance, max_middle_group_dist):
                    await self.bot.group_units(middle_unit, max_distance)
                    return
    
            for unit in forces:
                if (unit not in self.bot.in_micro) and (unit not in self.bot.wall_breakers) and (
                        unit not in self.bot.home_dronny) and (not unit.is_carrying_resource):
    
                    for unit_in_known in self.bot.known_enemy_u:
                        if unit_in_known not in self.bot.enemy_units:
                            self.bot.known_enemy_u.remove(unit_in_known)
    
                    if self.bot.enemy_units.exists:
                        for enemy_unit in self.bot.enemy_units:
                            if (enemy_unit not in self.bot.known_enemy_u) and (
                                    enemy_unit not in self.bot.enemy_structures) and (
                                    enemy_unit not in self.bot.enemy_units(UnitTypeId.LARVA)) and (
                                    not enemy_unit.is_flying):
                                self.bot.known_enemy_u.append(enemy_unit)
    
                        if len(self.bot.known_enemy_u) > 0 and get_distance(unit.position,
                                                                        self.bot.closest_enemy_unit(unit).position) < 3:
                            unit.attack(self.bot.closest_enemy_unit(unit).position)
    
                        elif get_distance(unit.position, self.bot.enemy_start_locations[0]) < 7:
                            unit.attack(self.bot.enemy_start_locations[0])
    
                        elif unit.health_max - unit.health > 0:
                            self.bot.accurate_attack(unit, attack_on_way=True)
    
                        else:
                            # unit.move(self.bot.enemy_start_locations[0])
                            self.bot.accurate_attack(unit, attack_on_way=False)
    
                    else:
                        # unit.move(self.bot.enemy_start_locations[0])
                        self.bot.accurate_attack(unit, attack_on_way=False)
    
            self.bot.manage_queen_attack()
    
        elif not self.bot.need_to_attack_main_base:
            await self.bot.find_final_structures(forces=forces, army=(self.bot.units(UnitTypeId.DRONE) | self.bot.units(UnitTypeId.ZERGLING)))
    
        # STARTING ATTACK
        elif self.bot.stop_drone and self.bot.units(UnitTypeId.OVERLORD).amount == 2 and self.bot.units(
                UnitTypeId.EGG).exists and self.bot.time < self.bot.stop_new_drone_attack_time:
    
            eggs = self.bot.units(UnitTypeId.EGG)
            if eggs.amount == 4:
                for drone in self.bot.units(UnitTypeId.DRONE):
                    if (drone not in self.bot.home_dronny) and (drone not in self.bot.wall_breakers) and (
                            not drone.is_carrying_resource):
                        drone.move(self.bot.enemy_start_locations[0])
                        if drone not in self.bot.attack_drones:
                            self.bot.attack_drones.append(drone)
    
                self.bot.stop_new_drone_attack_time = self.bot.time + 8
    
        if self.bot.need_to_attack_main_base:
            await self.bot.is_opponents_main_won()
    
