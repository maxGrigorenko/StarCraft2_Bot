from sc2.units import Units
from sc2.ids.unit_typeid import UnitTypeId
from sc2.data import Race, ActionResult
from sc2.ids.ability_id import AbilityId
from src.utils.coordinate_functions import *
from src.managers.action_registry import ActionPriority
from src.strategies.base_strategy import BaseStrategy


class ZerglingDroneStrategy(BaseStrategy):

    def __init__(self, bot):
        super().__init__(bot)

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
        if len(self.bot.wall_breakers_tags) < breakers_quantity:
            for unit in self.bot.units(UnitTypeId.DRONE):
                if len(self.bot.wall_breakers_tags) >= breakers_quantity:
                    break
                if unit.tag not in self.bot.home_dronny_tags and not unit.is_carrying_resource:
                    if unit.tag not in self.bot.wall_breakers_tags:
                        self.bot.wall_breakers_tags.append(unit.tag)

    async def zvz_spine_crawler(self):
        self.check_wall_breakers(1)

        if self.bot.canceled_crawl:
            if len(self.bot.wall_breakers_tags) == 0:
                self.bot.stop_wall_breaker = True
                return

            breaker_tag = self.bot.wall_breakers_tags[0]
            breaker = self.bot.units.find_by_tag(breaker_tag)
            if breaker is None:
                self.bot.wall_breakers_tags.remove(breaker_tag)
                self.bot.stop_wall_breaker = True
                return

            if get_distance(breaker.position, self.bot.scouting_helper.sorted_enemy_locations()[0]) < 40:
                self.bot.action_registry.submit_action(
                    tag=breaker.tag,
                    action=lambda b=breaker, mf=self.bot.mineral_field[10]: b.gather(mf),
                    priority=ActionPriority.NORMAL,
                    source="zvz_spine_crawler_gather"
                )
            else:
                self.bot.action_registry.submit_action(
                    tag=breaker.tag,
                    action=lambda b=breaker: b(AbilityId.STOP),
                    priority=ActionPriority.NORMAL,
                    source="zvz_spine_crawler_stop"
                )
                self.bot.wall_breakers_tags.clear()
                self.bot.stop_wall_breaker = True
            return

        if self.bot.structures(UnitTypeId.SPINECRAWLER).amount + self.bot.already_pending(UnitTypeId.SPINECRAWLER) == 0:

            for unit in self.bot.units(UnitTypeId.DRONE):
                if unit.tag not in self.bot.wall_breakers_tags:
                    continue

                breaker = self.bot.units.find_by_tag(unit.tag)
                if breaker is None:
                    self.bot.wall_breakers_tags.remove(unit.tag)
                    continue

                enemy_base_position = self.bot.enemy_start_locations[0]
                breaker_position = breaker.position

                if not self.bot.place:
                    self.bot.place = enemy_base_position

                d = get_distance(breaker_position, enemy_base_position)

                delta_x = abs(breaker_position[0] - enemy_base_position[0])
                delta_y = abs(breaker_position[1] - enemy_base_position[1])

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
                        self.bot.place = go_from_point(breaker_position, enemy_base_position, -0.1)

                    if self.bot.place != enemy_base_position and self.bot.minerals >= 100 and d < 11.2:
                        print(f"\nTry to build spine with distance: {d}")
                        await self.bot.build(UnitTypeId.SPINECRAWLER, build_worker=breaker, near=breaker, max_distance=1)
                        self.bot.stop_crawl = True

                if not self.bot.stop_crawl:
                    self.bot.action_registry.submit_action(
                        tag=breaker.tag,
                        action=lambda b=breaker, p=self.bot.place: b.move(p),
                        priority=ActionPriority.NORMAL,
                        source="zvz_spine_crawler_move"
                    )

        elif self.bot.already_pending(UnitTypeId.SPINECRAWLER) > 0:
            for spine in self.bot.structures(UnitTypeId.SPINECRAWLER):
                if spine.health < 17 and get_distance(spine.position, self.bot.combat_helper.closest_enemy_unit(spine).position) < 3:
                    await self.bot.chat_send("Ouch, my poor spine :(")
                    print("Cancelling spine")
                    self.bot.action_registry.submit_action(
                        tag=spine.tag,
                        action=lambda s=spine: s(AbilityId.CANCEL),
                        priority=ActionPriority.CRITICAL,
                        source="zvz_spine_crawler_cancel"
                    )
                    self.bot.stop_crawl = True
                    self.bot.canceled_crawl = True

    async def wall_breaker_do_block(self, breakers_quantity=1):
        if self.null_wall_breakers():
            self.bot.wall_breakers_tags.clear()
            self.bot.stop_wall_breaker = True
            return

        self.check_wall_breakers(breakers_quantity)

        for unit in self.bot.units(UnitTypeId.DRONE):
            if unit.tag not in self.bot.wall_breakers_tags:
                continue

            breaker = self.bot.units.find_by_tag(unit.tag)
            if breaker is None:
                self.bot.wall_breakers_tags.remove(unit.tag)
                continue

            if not breaker.is_carrying_resource and breaker.health > 5:

                if not self.bot.have_moved_wall_breaker:
                    self.bot.action_registry.submit_action(
                        tag=breaker.tag,
                        action=lambda b=breaker, t=self.bot.scouting_helper.sorted_enemy_locations()[0]: b.move(t),
                        priority=ActionPriority.NORMAL,
                        source="wall_breaker_move_to_first_loc"
                    )
                    if breaker.tag not in self.bot.wall_breakers_tags:
                        self.bot.wall_breakers_tags.append(breaker.tag)
                    self.bot.have_moved_wall_breaker = True

                elif get_distance(breaker.position, self.bot.start_location) < 8:
                    selected_tag = self.bot.wall_breakers_tags[0] if self.bot.wall_breakers_tags else None
                    if selected_tag is not None:
                        selected_drone = self.bot.units.find_by_tag(selected_tag)
                        if selected_drone is not None:
                            if 40 < get_distance(selected_drone.position, self.bot.start_location) < 50:
                                self.bot.action_registry.submit_action(
                                    tag=breaker.tag,
                                    action=lambda b=breaker, t=self.bot.scouting_helper.sorted_enemy_locations()[0]: b.move(t),
                                    priority=ActionPriority.NORMAL,
                                    source="wall_breaker_move_to_first_loc2"
                                )
                        else:
                            self.bot.wall_breakers_tags.remove(selected_tag)

                if self.prominent_structures() >= 2:
                    if not self.bot.begin_position and get_distance(breaker.position,
                                                                    self.bot.enemy_start_locations[0]) < 40:
                        self.bot.begin_position = breaker.position

                    if not self.bot.place:
                        self.bot.place = self.bot.enemy_start_locations[0]

                    if self.bot.begin_position:
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

                        self.bot.action_registry.submit_action(
                            tag=breaker.tag,
                            action=lambda b=breaker, p=self.bot.place: b.move(p),
                            priority=ActionPriority.NORMAL,
                            source="wall_breaker_move_place"
                        )

            else:
                if len(self.bot.all_enemy_units) > 0:
                    if breaker.health <= 10 and get_distance(breaker.position,
                                                             self.bot.combat_helper.closest_enemy_unit(breaker).position) < 3:
                        self.bot.action_registry.submit_action(
                            tag=breaker.tag,
                            action=lambda b=breaker, t=self.bot.scouting_helper.sorted_enemy_locations()[1]: b.move(t),
                            priority=ActionPriority.HIGH,
                            source="wall_breaker_move_to_second_loc"
                        )

    # ------------------------------------------------------------------
    # Small helper methods for readability
    # ------------------------------------------------------------------

    def _update_drone_production(self):
        stop = False
        resume = False
        drone_amount = self.bot.units(UnitTypeId.DRONE).amount
        pool_exists = self.bot.structures(UnitTypeId.SPAWNINGPOOL).exists or self.bot.already_pending(
            UnitTypeId.SPAWNINGPOOL)
        dangerous_structures = self.bot.unit_helper.dangerous_structures_exist()

        if self.bot.stop_drone:
            if pool_exists and (drone_amount != 14 or self.bot.need_air_units) and not self.bot.defence:
                resume = True
        else:
            if (drone_amount == 14 or not pool_exists) and not dangerous_structures:
                stop = True

        if stop:
            self.bot.stop_drone = True
        elif resume:
            self.bot.stop_drone = False

    def _should_attack_main(self):
        return self.should_attack_main_base(self.bot.units(UnitTypeId.ZERGLING).amount)

    def _should_drone_attack_egg(self):
        return (self.bot.stop_drone and
                self.bot.units(UnitTypeId.OVERLORD).amount == 2 and
                self.bot.units(UnitTypeId.EGG).exists and
                self.bot.time < self.bot.stop_new_drone_attack_time)

    async def _start_drone_attack(self):
        eggs = self.bot.units(UnitTypeId.EGG)
        if eggs.amount == 4:
            for drone in self.bot.units(UnitTypeId.DRONE):
                if (drone.tag not in self.bot.home_dronny_tags and
                        drone.tag not in self.bot.wall_breakers_tags and
                        not drone.is_carrying_resource):
                    self.bot.action_registry.submit_action(
                        tag=drone.tag,
                        action=lambda d=drone, target=self.bot.enemy_start_locations[0]: d.move(target),
                        priority=ActionPriority.NORMAL,
                        source="start_attack_drone_move"
                    )
                    if drone.tag not in self.bot.attack_drones_tags:
                        self.bot.attack_drones_tags.append(drone.tag)
            self.bot.stop_new_drone_attack_time = self.bot.time + 8

    def _wall_breaker_should_run(self):
        return (self.bot.units(UnitTypeId.OVERLORD).exists and
                self.bot.need_to_attack_main_base and
                not self.bot.stop_wall_breaker)

    def _wall_breaker_begin_time(self):
        if self.bot.enemy_race == Race.Terran:
            return 55
        elif self.bot.enemy_race == Race.Protoss:
            return 45
        elif self.bot.enemy_race == Race.Zerg:
            return 35
        else:  # Race.Random
            return 45

    def _zergling_attack_micro(self, unit):
        self.update_known_enemies()

        if self.bot.enemy_units.exists:
            if len(self.bot.known_enemy_u) > 0 and get_distance(
                    unit.position, self.bot.combat_helper.closest_enemy_unit(unit).position) < 3:
                closest_enemy = self.bot.combat_helper.closest_enemy_unit(unit)
                self.bot.action_registry.submit_action(
                    tag=unit.tag,
                    action=lambda u=unit, t=closest_enemy.position: u.attack(t),
                    priority=ActionPriority.NORMAL,
                    source="zergling_attack_closest_enemy"
                )
            elif get_distance(unit.position, self.bot.enemy_start_locations[0]) < 7:
                self.bot.action_registry.submit_action(
                    tag=unit.tag,
                    action=lambda u=unit, target=self.bot.enemy_start_locations[0]: u.attack(target),
                    priority=ActionPriority.NORMAL,
                    source="zergling_attack_enemy_start"
                )
            elif unit.health_max - unit.health > 0:
                self.bot.combat_helper.accurate_attack(unit, attack_on_way=True)
            else:
                self.bot.combat_helper.accurate_attack(unit, attack_on_way=False)
        else:
            self.bot.combat_helper.accurate_attack(unit, attack_on_way=False)

    # ------------------------------------------------------------------
    # Main step
    # ------------------------------------------------------------------
    async def zergling_drone_rush_step(self, iteration):
        await self.bot.economy_helper.mining_iteration()
        await self.bot.overlord_manager.manage(overlords=self.bot.units(UnitTypeId.OVERLORD),
                                               enemies=self.bot.scouting_helper.air_danger_units())
        await self.bot.combat_helper.queen_management()
        await self.bot.combat_helper.micro_element()

        if self.bot.enemy_race == Race.Terran:
            home_dronny_amount = 3
        elif self.bot.enemy_race == Race.Protoss or self.bot.enemy_race == Race.Random:
            home_dronny_amount = 2
        else:
            home_dronny_amount = 1  # +1

        if self.dangerous_air_units():
            self.bot.need_air_units = True

        if self.bot.units(UnitTypeId.ZERGLING).amount >= 40:
            self.bot.stop_zergling = True
            if self.bot.enemy_race == Race.Terran and not self.bot.need_to_attack_main_base:
                self.bot.need_air_units = True

        elif self.bot.stop_zergling:
            self.bot.stop_zergling = False

        if not self.bot.units(UnitTypeId.DRONE).exists and self.bot.minerals < 50:
            self.bot.need_air_units = False

        self.bot.home_dronny_tags = [
            tag for tag in self.bot.home_dronny_tags
            if self.bot.units.find_by_tag(tag) is not None
        ]

        if len(self.bot.home_dronny_tags) == 0:
            await self.bot.distribute_workers()

        if (len(self.bot.home_dronny_tags) == 0) or (
                self.bot.need_air_units and len(self.bot.home_dronny_tags) < self.bot.units(UnitTypeId.DRONE).amount):
            for drone in self.bot.units(UnitTypeId.DRONE):
                if len(self.bot.home_dronny_tags) == home_dronny_amount and not self.bot.need_air_units:
                    break
                else:
                    if drone.tag not in self.bot.home_dronny_tags:
                        self.bot.home_dronny_tags.append(drone.tag)

        if iteration == 30:
            await self.bot.chat_send("gl hf!")
            print(
                f"\nOpponent_id: {self.bot.opponent_id}\n\nMap size: {self.bot.game_info.map_size[0]} {self.bot.game_info.map_size[1]}\n\nStart location: {self.bot.start_location.position[0]} {self.bot.start_location[1]}")

        if len(self.bot.locations) == 0:
            self.bot.locations = self.bot.scouting_helper.get_locations()

        larvae = self.bot.units(UnitTypeId.LARVA)
        forces = (self.bot.units(UnitTypeId.DRONE) | self.bot.units(UnitTypeId.ZERGLING) |
                  self.bot.units(UnitTypeId.ROACH) | self.bot.units(UnitTypeId.MUTALISK))

        if self.bot.enemy_units(UnitTypeId.BROODLING).exists:
            for unit in forces:
                if unit.tag not in self.bot.home_dronny_tags:
                    self.bot.action_registry.submit_action(
                        tag=unit.tag,
                        action=lambda u=unit, loc=self.bot.start_location: u.move(loc),
                        priority=ActionPriority.NORMAL,
                        source="broodling_retreat"
                    )
            return

        if self.emergency_attack_no_townhalls(forces):
            return

        first_base = self.bot.townhalls.first
        if self.check_main_base_health():
            return

        if not self.bot.units(UnitTypeId.ZERGLING).exists:
            await self.bot.combat_helper.defending()
        else:
            self.bot.defence = False

        # BUILDORDER STOPS

        self._update_drone_production()

        # BUILDING DRONES

        if len(self.bot.mining_drones_tags) < first_base.ideal_harvesters and (
                self.bot.need_air_units or not self.bot.stop_drone) and not self.bot.defence:
            if self.bot.can_afford(UnitTypeId.DRONE) and larvae.exists:
                larva = larvae.random
                self.bot.action_registry.submit_action(
                    tag=larva.tag,
                    action=lambda u=larva, tid=UnitTypeId.DRONE: u.train(tid),
                    priority=ActionPriority.HIGH,
                    source="train_drone"
                )

        # BUILDING SPAWNING POOL

        dronny = self.find_dronny()

        self.build_spawning_pool(dronny, first_base)

        overlord_extra_condition = self.bot.need_air_units and self.bot.supply_left < 4
        self.train_overlord_if_needed(larvae, supply_threshold=0, extra_condition=True)

        # GOING MACRO

        if self.bot.need_air_units:
            if self.bot.units(UnitTypeId.MUTALISK).amount > 4:
                self.bot.need_air_units = False
            else:
                await self.bot.economy_helper.macro_element()

            if len(self.bot.mining_drones_tags) < self.bot.units(UnitTypeId.DRONE).amount - 5:
                self.bot.home_dronny_tags.clear()

        if self.bot.structures(UnitTypeId.SPAWNINGPOOL).ready.exists and not self.bot.stop_zergling:

            if self.bot.can_afford(UnitTypeId.ZERGLING) and larvae.exists:
                larva = larvae.random
                self.bot.action_registry.submit_action(
                    tag=larva.tag,
                    action=lambda u=larva, tid=UnitTypeId.ZERGLING: u.train(tid),
                    priority=ActionPriority.HIGH,
                    source="train_zergling"
                )

            if first_base.is_idle:

                larvae_amount = larvae.amount
                if len(self.bot.mining_drones_tags) >= 10:
                    min_minerals = 150 + larvae_amount * 50
                else:
                    min_minerals = 200 + larvae_amount * 50

                if (self.bot.enemy_race == Race.Zerg or self.bot.enemy_race == Race.Random) and (
                        self.bot.structures(UnitTypeId.SPINECRAWLER).amount + self.bot.already_pending(
                    UnitTypeId.SPINECRAWLER) == 0):
                    min_minerals += 150

                if self.bot.minerals >= min_minerals:
                    self.bot.action_registry.submit_action(
                        tag=first_base.tag,
                        action=lambda hatchery=first_base: hatchery.train(UnitTypeId.QUEEN),
                        priority=ActionPriority.HIGH,
                        source="train_queen"
                    )

        # WALL BREAKER

        if self._wall_breaker_should_run():
            if self.bot.time > self._wall_breaker_begin_time():
                if self.bot.enemy_race != Race.Zerg:
                    await self.wall_breaker_do_block(breakers_quantity=1)
                else:
                    await self.zvz_spine_crawler()

        # CANNON PROBLEM

        if self.bot.unit_helper.dangerous_structures_exist() and (
                self.bot.unit_helper.no_units_in_opponent_main() or not self.bot.need_to_attack_main_base):
            dist_with_dangerous_structures = get_distance(self.bot.unit_helper.enemy_dangerous_structures()[0].position,
                                                          self.bot.start_location.position)

            if dist_with_dangerous_structures > 100 or (not self.bot.need_to_attack_main_base):

                if self.bot.units(UnitTypeId.ZERGLING).amount < 25 and self.bot.time > 200:
                    self.bot.stop_drone = False
                    return

        # STOPPING ATTACK WITH DRONES

        self.bot.attack_drones_tags = [
            tag for tag in self.bot.attack_drones_tags
            if self.bot.units.find_by_tag(tag) is not None
        ]

        if self.bot.time > self.bot.stop_new_drone_attack_time:
            for drone in self.bot.units(UnitTypeId.DRONE):
                if drone.tag not in self.bot.home_dronny_tags and \
                        get_distance(drone.position, self.bot.start_location) < 10 and \
                        drone.tag not in self.bot.attack_drones_tags:
                    self.bot.home_dronny_tags.append(drone.tag)

        # ATTACK

        if self._should_attack_main():
            # group
            if not self.bot.stop_group and self.bot.units(UnitTypeId.ZERGLING).amount <= 25:
                middle_unit = self.bot.unit_helper.closest_unit(self.bot.units(UnitTypeId.ZERGLING),
                                                    self.bot.enemy_start_locations[0])
                max_distance = 15  # from middle unit
                max_middle_group_dist = 3.2
                if self.bot.combat_helper.need_group(middle_unit, max_distance, max_middle_group_dist):
                    await self.bot.combat_helper.group_units(middle_unit, max_distance)
                    return

            self.bot.in_micro_tags = [
                tag for tag in self.bot.in_micro_tags
                if self.bot.units.find_by_tag(tag) is not None
            ]

            for unit in forces:
                if unit.tag in self.bot.in_micro_tags:
                    continue
                if unit.tag in self.bot.wall_breakers_tags:
                    continue
                if unit.tag in self.bot.home_dronny_tags:
                    continue
                if unit.is_carrying_resource:
                    continue

                self._zergling_attack_micro(unit)

            self.bot.combat_helper.manage_queen_attack()

        elif not self.bot.need_to_attack_main_base:
            await self.bot.combat_helper.find_final_structures(
                forces=forces,
                army=(self.bot.units(UnitTypeId.DRONE) | self.bot.units(UnitTypeId.ZERGLING))
            )

        # STARTING ATTACK
        elif self._should_drone_attack_egg():
            await self._start_drone_attack()

        if self.bot.need_to_attack_main_base:
            await self.bot.combat_helper.is_opponents_main_won()
