from sc2.ids.upgrade_id import UpgradeId
from src.utils.universal_functions import *
from src.utils.speed_mining import *
from src.managers.ravager_manager import find_closest_enemy, calculate_retreat_position
from src.utils.coordinate_functions import get_distance


class RoachStrategy:
    def __init__(self, bot):
        self.bot = bot

    def burrow_micro(self):
        if UpgradeId.BURROW not in self.bot.state.upgrades:
            return

        self.bot.in_burrow_process = [roach for roach in self.bot.units(UnitTypeId.ROACH) if roach.health <= 54]

        detectors = [unit for unit in self.bot.enemy_units if unit.is_detector]
        for struct in self.bot.enemy_structures:
            if struct.is_detector:
                detectors.append(struct)

        for roach in self.bot.units(UnitTypeId.ROACH):
            if roach.health <= 54 and not roach.is_burrowed and self.bot.closest_unit_dist(unit=roach,
                                                                                           units=detectors) > 10:
                self.bot.action_registry.submit_action(
                    tag=roach.tag,
                    action=lambda u=roach: u(AbilityId.BURROWDOWN_ROACH),
                    priority=50,
                    source="burrow_micro"
                )

        for burrowed_roach in self.bot.units(UnitTypeId.ROACHBURROWED):
            health_up_border = 130
            if self.bot.units(UnitTypeId.ROACH).amount > 0:
                closest_roach = self.bot.closest_unit([unit for unit in self.bot.units(UnitTypeId.ROACH)],
                                                      burrowed_roach)
                if get_distance(burrowed_roach.position, closest_roach.position) < 3:
                    health_up_border = 85
            if (burrowed_roach.health >= health_up_border and burrowed_roach.is_burrowed) or self.bot.closest_unit_dist(
                    unit=burrowed_roach, units=detectors) < 10:
                self.bot.action_registry.submit_action(
                    tag=burrowed_roach.tag,
                    action=lambda u=burrowed_roach: u(AbilityId.BURROWUP_ROACH),
                    priority=50,
                    source="burrow_micro"
                )

        for queen in self.bot.units(UnitTypeId.QUEEN):
            if queen.health <= 50 and not queen.is_burrowed and self.bot.closest_unit_dist(unit=queen,
                                                                                           units=detectors) > 10:
                self.bot.action_registry.submit_action(
                    tag=queen.tag,
                    action=lambda u=queen: u(AbilityId.BURROWDOWN_QUEEN),
                    priority=50,
                    source="burrow_micro"
                )

        for burrowed_queen in self.bot.units(UnitTypeId.QUEENBURROWED):
            if (burrowed_queen.health >= 100 and burrowed_queen.is_burrowed) or self.bot.closest_unit_dist(
                    unit=burrowed_queen, units=detectors) < 10:
                self.bot.action_registry.submit_action(
                    tag=burrowed_queen.tag,
                    action=lambda u=burrowed_queen: u(AbilityId.BURROWUP_QUEEN),
                    priority=50,
                    source="burrow_micro"
                )

        '''
        NEED TO REFACTOR SPEEDMINING
        if self.bot.enemy_units.exists:
            for drone in self.bot.units(UnitTypeId.DRONE):
                if drone.health < drone.health_max - 5 and \
                        get_distance(self.bot.closest_enemy_unit(drone).position, drone.position) <= 10 and \
                        drone not in self.bot.drones_on_gas:
                    drone(AbilityId.BURROWDOWN_DRONE)
    
        for burrowed_drone in self.bot.units(UnitTypeId.DRONEBURROWED):
            if burrowed_drone.health == burrowed_drone.health_max or not self.bot.enemy_units.exists:
                burrowed_drone(AbilityId.BURROWUP_DRONE)
            elif get_distance(self.bot.closest_enemy_unit(burrowed_drone).position, burrowed_drone.position) > 10:
                burrowed_drone(AbilityId.BURROWUP_DRONE)
        '''

    async def roach_micro_management(self):
        roaches = self.bot.units(UnitTypeId.ROACH)
        ground_enemies = [u for u in self.bot.enemy_units if not u.is_flying and not u.is_hallucination]
        dangerous_structures = (self.bot.enemy_structures(UnitTypeId.PHOTONCANNON) |
                                self.bot.enemy_structures(UnitTypeId.BUNKER) |
                                self.bot.enemy_structures(UnitTypeId.SPINECRAWLER))

        for roach in roaches:
            closest_enemy = find_closest_enemy(roach, ground_enemies)
            if closest_enemy is None:
                continue

            dist_to_enemy = get_distance(roach.position, closest_enemy.position)
            if dist_to_enemy < 7:
                if roach.weapon_ready:
                    self.bot.action_registry.submit_action(
                        tag=roach.tag,
                        action=lambda u=roach, p=closest_enemy.position: u.attack(p),
                        priority=40,
                        source="roach_micro"
                    )
                else:
                    retreat_pos = calculate_retreat_position(
                        roach.position, closest_enemy.position, retreat_dist=1.5
                    )
                    self.bot.action_registry.submit_action(
                        tag=roach.tag,
                        action=lambda u=roach, p=retreat_pos: u.move(p),
                        priority=60,
                        source="roach_micro"
                    )
                continue

    async def roach_rush_step(self, iteration):
        await self.bot.mining_iteration()
        await self.bot.overlord_manager.manage(overlords=self.bot.units(UnitTypeId.OVERLORD),
                                               enemies=self.bot.air_danger_units())
        await self.bot.queen_management()
        await self.roach_micro_management()
        self.burrow_micro()

        if self.bot.units(UnitTypeId.ROACH).amount >= 16:
            if self.bot.enemy_race == Race.Terran and not self.bot.need_to_attack_main_base:
                self.bot.need_air_units = True

        forces = self.bot.units(UnitTypeId.ZERGLING) | self.bot.units(UnitTypeId.ROACH) | self.bot.units(UnitTypeId.MUTALISK)
        with_drone_forces = self.bot.units(UnitTypeId.DRONE) | self.bot.units(UnitTypeId.ZERGLING) | self.bot.units(UnitTypeId.ROACH) | self.bot.units(
            UnitTypeId.MUTALISK)
        larvae = self.bot.units(UnitTypeId.LARVA)
        dangerous_structures = (self.bot.enemy_structures(UnitTypeId.PHOTONCANNON) |
                                self.bot.enemy_structures(UnitTypeId.BUNKER) |
                                self.bot.enemy_structures(UnitTypeId.SPINECRAWLER))

        if not self.bot.townhalls.exists:
            for unit in self.bot.units(UnitTypeId.QUEEN) | with_drone_forces:
                self.bot.action_registry.submit_action(
                    tag=unit.tag,
                    action=lambda u=unit, p=self.bot.enemy_start_locations[0].position: u.attack(p),
                    priority=40,
                    source="roach_rush_step"
                )
            return
        else:
            first_base = self.bot.townhalls.first
            if first_base.health < 401:
                self.bot.proxy()
                return

        if not self.bot.units(UnitTypeId.ROACH).exists:
            await self.bot.defending()
        else:
            self.bot.defence = False

        if (not self.bot.stop_drone) and (
                self.bot.supply_workers >= 14 or
                (not (self.bot.structures(UnitTypeId.SPAWNINGPOOL).exists or self.bot.already_pending(UnitTypeId.SPAWNINGPOOL)))) \
                and not self.bot.dangerous_structures_exist():
            self.bot.stop_drone = True

        elif self.bot.stop_drone and (
                self.bot.structures(UnitTypeId.SPAWNINGPOOL).exists or self.bot.already_pending(
            UnitTypeId.SPAWNINGPOOL)) and (
                self.bot.structures(UnitTypeId.EXTRACTOR).exists or self.bot.already_pending(
            UnitTypeId.EXTRACTOR)) and (
                self.bot.supply_workers < 14 or self.bot.need_air_units):
            self.bot.stop_drone = False

        if iteration == 30:
            await self.bot.chat_send("gl hf!")
            print(
                f"\nOpponent_id: {self.bot.opponent_id}\n\nMap size: {self.bot.game_info.map_size[0]} {self.bot.game_info.map_size[1]}\n\nStart location: {self.bot.start_location.position[0]} {self.bot.start_location[1]}")

        if len(self.bot.locations) == 0:
            self.bot.locations = self.bot.get_locations()

        # BUILDING DRONES

        if len(self.bot.mining_drones) < first_base.ideal_harvesters and (self.bot.need_air_units or not self.bot.stop_drone):
            if self.bot.can_afford(UnitTypeId.DRONE) and larvae.exists and (
                    (self.bot.time < 70 and self.bot.supply_used < 14) or self.bot.structures(UnitTypeId.ROACHWARREN).ready.exists):
                self.bot.train(UnitTypeId.DRONE)

        if not self.bot.dronny or self.bot.dronny is None:
            drones_without_minerals = [unit for unit in self.bot.units(UnitTypeId.DRONE) if not unit.is_carrying_resource]
            if len(drones_without_minerals) >= 1:
                self.bot.dronny = self.bot.closest_unit(drones_without_minerals, self.bot.enemy_start_locations[0])

        # BUILDING SPAWNING POOL

        if self.bot.structures(UnitTypeId.SPAWNINGPOOL).amount + self.bot.already_pending(UnitTypeId.SPAWNINGPOOL) == 0:
            self.bot.dronny = self.bot.refresh_unit(self.bot.dronny)
            dronny = self.bot.dronny
            distance = 8
            if self.bot.time < 70 and dronny is not None:
                if 200 > self.bot.minerals > 140 and not dronny.is_carrying_resource and get_distance(dronny.position,
                                                                                                      self.bot.start_location) < distance:
                    self.bot.action_registry.submit_action(
                        tag=dronny.tag,
                        action=lambda u=dronny, p=self.bot.enemy_start_locations[0].position: u.move(p),
                        priority=20,
                        source="roach_rush_step"
                    )
                    if dronny not in self.bot.building_workers:
                        self.bot.building_workers.append(dronny)

                elif self.bot.can_afford(UnitTypeId.SPAWNINGPOOL):
                    self.bot.action_registry.submit_action(
                        tag=dronny.tag,
                        action=lambda u=dronny, tid=UnitTypeId.SPAWNINGPOOL, near_pos=dronny.position: u.build(tid, near_pos),
                        priority=80,
                        source="roach_rush_step"
                    )
                    if dronny not in self.bot.building_workers:
                        self.bot.building_workers.append(dronny)

                elif get_distance(dronny.position, self.bot.start_location) >= distance and self.bot.minerals > 160:
                    self.bot.action_registry.submit_action(
                        tag=dronny.tag,
                        action=lambda u=dronny, p=dronny.position: u.move(p),
                        priority=20,
                        source="roach_rush_step"
                    )

            elif self.bot.minerals >= 200 and self.bot.units(UnitTypeId.DRONE).amount > 0 and dronny is not None:
                self.bot.action_registry.submit_action(
                    tag=dronny.tag,
                    action=lambda u=dronny, tid=UnitTypeId.SPAWNINGPOOL, near_pos=first_base.position: u.build(tid, near_pos),
                    priority=80,
                    source="roach_rush_step"
                )
                if dronny not in self.bot.building_workers:
                    self.bot.building_workers.append(dronny)

        # BUILDING EXTRACTOR

        if self.bot.structures(UnitTypeId.SPAWNINGPOOL).amount >= 1 and\
                (self.bot.structures(UnitTypeId.EXTRACTOR).amount + self.bot.already_pending(UnitTypeId.EXTRACTOR) == 0):
            self.bot.dronny = self.bot.refresh_unit(self.bot.dronny)
            dronny = self.bot.dronny
            if self.bot.can_afford(UnitTypeId.EXTRACTOR) and dronny is not None:
                target = self.bot.vespene_geyser.closest_to(
                    dronny.position)  # "When building the gas structure, the target needs to be a unit (the vespene geyser) not the position of the vespene geyser."
                self.bot.action_registry.submit_action(
                    tag=dronny.tag,
                    action=lambda u=dronny, tgt=target, tid=UnitTypeId.EXTRACTOR: u.build(tid, tgt),
                    priority=80,
                    source="roach_rush_step"
                )
                if dronny not in self.bot.building_workers:
                    self.bot.building_workers.append(dronny)

        for extractor in self.bot.structures(UnitTypeId.EXTRACTOR):
            if extractor.assigned_harvesters < extractor.ideal_harvesters and \
                    self.bot.structures(UnitTypeId.EXTRACTOR).ready.exists and not self.bot.defence:
                w = self.bot.workers.closer_than(6, extractor)
                if w.exists:
                    drone = w.random
                    if drone != self.bot.dronny:
                        self.bot.action_registry.submit_action(
                            tag=drone.tag,
                            action=lambda u=drone, extr=extractor: u.gather(extr),
                            priority=30,
                            source="roach_rush_step"
                        )
                        self.bot.drones_on_gas.append(drone)

        # BUILDING ROACH WARREN

        if self.bot.structures(UnitTypeId.SPAWNINGPOOL).amount >= 1 and \
                (self.bot.structures(UnitTypeId.ROACHWARREN).amount + self.bot.already_pending(UnitTypeId.ROACHWARREN) == 0):
            self.bot.dronny = self.bot.refresh_unit(self.bot.dronny)
            dronny = self.bot.dronny
            if not dronny or dronny is None:
                drones_without_minerals = [unit for unit in self.bot.units(UnitTypeId.DRONE) if not unit.is_carrying_resource]
                if len(drones_without_minerals) >= 1:
                    self.bot.dronny = self.bot.closest_unit(drones_without_minerals, self.bot.enemy_start_locations[0])
                    dronny = self.bot.dronny

            distance = 8
            if dronny is not None:
                if self.bot.time > 55 and not dronny.is_carrying_resource and \
                        get_distance(dronny.position, self.bot.start_location) < distance:
                    self.bot.action_registry.submit_action(
                        tag=dronny.tag,
                        action=lambda u=dronny, p=self.bot.enemy_start_locations[0].position: u.move(p),
                        priority=20,
                        source="roach_rush_step"
                    )
                    if dronny not in self.bot.building_workers:
                        self.bot.building_workers.append(dronny)

                elif self.bot.structures(UnitTypeId.SPAWNINGPOOL).ready.exists and self.bot.can_afford(
                        UnitTypeId.ROACHWARREN):
                    self.bot.action_registry.submit_action(
                        tag=dronny.tag,
                        action=lambda u=dronny, tid=UnitTypeId.ROACHWARREN, near_pos=dronny.position: u.build(tid, near_pos),
                        priority=80,
                        source="roach_rush_step"
                    )
                    if dronny not in self.bot.building_workers:
                        self.bot.building_workers.append(dronny)

                elif get_distance(dronny.position, self.bot.start_location) >= distance:
                    self.bot.action_registry.submit_action(
                        tag=dronny.tag,
                        action=lambda u=dronny, p=dronny.position: u.move(p),
                        priority=20,
                        source="roach_rush_step"
                    )

        # GOING MACRO

        if self.bot.need_air_units:
            if self.bot.units(UnitTypeId.MUTALISK).amount > 4:
                self.bot.need_air_units = False
            else:
                await self.bot.macro_element()

        if first_base.is_idle:
            min_minerals = 225 + larvae.amount * 75
            if self.bot.minerals >= min_minerals and self.bot.already_pending_upgrade(UpgradeId.BURROW) == 1 and \
                    (not self.bot.need_air_units or self.bot.structures(
                        UnitTypeId.LAIR).amount >= 1) and self.bot.supply_left >= 2:
                self.bot.action_registry.submit_action(
                    tag=first_base.tag,
                    action=lambda u=first_base, tid=UnitTypeId.QUEEN: u.train(tid),
                    priority=90,
                    source="roach_rush_step"
                )

        if (self.bot.supply_left <= 0 or (
                self.bot.units(UnitTypeId.DRONE).amount >= 14 and self.bot.supply_left <= 1)) and \
                not self.bot.already_pending(UnitTypeId.OVERLORD):
            if self.bot.can_afford(UnitTypeId.OVERLORD) and larvae.exists:
                larva = larvae.random
                self.bot.action_registry.submit_action(
                    tag=larva.tag,
                    action=lambda u=larva, tid=UnitTypeId.OVERLORD: u.train(tid),
                    priority=90,
                    source="roach_rush_step"
                )

        if self.bot.already_pending_upgrade(UpgradeId.BURROW) == 0 and self.bot.can_afford(
                UpgradeId.BURROW
        ):
            hatchery = self.bot.townhalls.first
            if hatchery:
                self.bot.action_registry.submit_action(
                    tag=hatchery.tag,
                    action=lambda u=hatchery, upg=UpgradeId.BURROW: u.research(upg),
                    priority=80,
                    source="roach_rush_step"
                )

        if self.bot.structures(UnitTypeId.ROACHWARREN).ready.exists and \
                self.bot.can_afford(UnitTypeId.ROACH) and \
                larvae.exists and not self.bot.need_air_units:
            larva = larvae.random
            self.bot.action_registry.submit_action(
                tag=larva.tag,
                action=lambda u=larva, tid=UnitTypeId.ROACH: u.train(tid),
                priority=90,
                source="roach_rush_step"
            )

        # ATTACK

        if (self.bot.units(UnitTypeId.ROACH).amount > 0 or (
                not self.bot.no_units_in_opponent_main() and self.bot.time > 100)) and self.bot.need_to_attack_main_base:

            for unit in forces:
                if unit not in self.bot.in_burrow_process:
                    for unit_in_known in self.bot.known_enemy_u:
                        if unit_in_known not in self.bot.enemy_units:
                            self.bot.known_enemy_u.remove(unit_in_known)

                    if self.bot.enemy_units.exists:
                        closest_enemy_to_unit = self.bot.closest_enemy_unit(unit)
                        closest_enemy_to_base = self.bot.closest_enemy_unit(self.bot.townhalls.first)
                        enemy_near_home_and_unit = (get_distance(closest_enemy_to_base.position, self.bot.townhalls.first.position) < 12 and
                                 get_distance(closest_enemy_to_base.position, unit.position) < 13)
                        enemy_is_close = get_distance(unit.position, closest_enemy_to_unit.position) < 5

                        for enemy_unit in self.bot.enemy_units:
                            if (enemy_unit not in self.bot.known_enemy_u) and (
                                    enemy_unit not in self.bot.enemy_structures) and (
                                    enemy_unit not in self.bot.enemy_units(UnitTypeId.LARVA)) and (
                                    not enemy_unit.is_flying):
                                self.bot.known_enemy_u.append(enemy_unit)

                        need_to_run_deep = ((self.bot.time < 210) and
                                            (self.bot.closest_unit_dist(unit=unit, units=dangerous_structures) < 15) and
                                            (get_distance(unit.position, self.bot.enemy_start_locations[0].position) > 8))

                        if self.bot.units(UnitTypeId.ROACHBURROWED).amount >= 1 and \
                                get_distance(self.bot.closest_unit(self.bot.units(UnitTypeId.ROACHBURROWED), unit).position, unit.position) < 1.25 and \
                                self.bot.units(UnitTypeId.ROACH).amount < 15 and self.bot.units(UnitTypeId.QUEEN).amount < 3 and \
                                not need_to_run_deep:
                            self.bot.action_registry.submit_action(
                                tag=unit.tag,
                                action=lambda u=unit, p=self.bot.townhalls.first.position: u.move(p),
                                priority=20,
                                source="roach_rush_step"
                            )

                        elif (len(self.bot.known_enemy_u) > 0 and
                              (enemy_is_close or enemy_near_home_and_unit) and
                              (not closest_enemy_to_base.is_flying) and
                              (self.bot.time > 150 or self.bot.closest_unit_dist(unit=unit, units=dangerous_structures) > 10) and
                              (not need_to_run_deep)):
                            self.bot.action_registry.submit_action(
                                tag=unit.tag,
                                action=lambda u=unit, p=closest_enemy_to_base.position: u.attack(p),
                                priority=40,
                                source="roach_rush_step"
                            )

                        elif get_distance(unit.position, self.bot.enemy_start_locations[0]) < 7:
                            self.bot.action_registry.submit_action(
                                tag=unit.tag,
                                action=lambda u=unit, p=self.bot.enemy_start_locations[0].position: u.attack(p),
                                priority=40,
                                source="roach_rush_step"
                            )

                        elif ((unit.health_max - unit.health > 0) and
                              not (self.bot.time < 150 and self.bot.closest_unit_dist(unit=unit,
                                                                                      units=dangerous_structures) < 10) and
                              not need_to_run_deep):
                            self.bot.accurate_attack(unit, attack_on_way=True)

                        else:
                            self.bot.accurate_attack(unit, attack_on_way=False)

                    else:
                        self.bot.accurate_attack(unit, attack_on_way=False)

            self.bot.manage_queen_attack()

        elif not self.bot.need_to_attack_main_base:
            await self.bot.find_final_structures(forces=forces, army=(
                    self.bot.units(UnitTypeId.ROACH) | self.bot.units(UnitTypeId.OVERLORD)))

        if self.bot.need_to_attack_main_base:
            await self.bot.is_opponents_main_won()
