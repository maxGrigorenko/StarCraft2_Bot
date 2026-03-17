from sc2.units import Units
from sc2.ids.unit_typeid import UnitTypeId
from src.utils.coordinate_functions import *
from sc2.data import Race, ActionResult
from sc2.ids.ability_id import AbilityId
from sc2.ids.upgrade_id import UpgradeId
from src.utils.universal_functions import *
from src.utils.speed_mining import *


def morph_ravagers(self):
    """Morph all available Roaches into Ravagers."""
    roaches = self.units(UnitTypeId.ROACH)

    if not self.structures(UnitTypeId.ROACHWARREN).ready.exists:
        return

    available_minerals = self.minerals
    available_gas = self.vespene

    for roach in roaches:
        if available_minerals >= 25 and available_gas >= 75 and roach.is_ready:
            roach(AbilityId.MORPHTORAVAGER_RAVAGER)
            available_minerals -= 25
            available_gas -= 75


async def use_corrosive_bile(self):
    """Delegate Corrosive Bile usage to the ravager manager."""
    ravagers = self.units(UnitTypeId.RAVAGER)
    roaches = self.units(UnitTypeId.ROACH)
    if not ravagers.exists and not roaches.exists:
        return set()

    return await self.ravager_manager.manage(
        bot=self,
        ravagers=ravagers,
        roaches=roaches,
        enemy_units=self.enemy_units,
        enemy_structures=self.enemy_structures,
        enemy_start_location=self.enemy_start_locations[0],
        own_start_location=self.start_location,
        game_loop=self.state.game_loop,
    )


async def ravager_rush_step(self, iteration):
    await self.mining_iteration()
    await self.overlord_manager.manage(overlords=self.units(UnitTypeId.OVERLORD),
                                       enemies=self.air_danger_units())
    await self.queen_management()
    self.morph_ravagers()
    self.handled_by_micro = await self.use_corrosive_bile()

    if self.units(UnitTypeId.RAVAGER).amount >= 8:
        if self.enemy_race == Race.Terran and not self.need_to_attack_main_base:
            self.need_air_units = True

    forces = (self.units(UnitTypeId.ZERGLING) | self.units(UnitTypeId.ROACH) |
              self.units(UnitTypeId.RAVAGER) | self.units(UnitTypeId.MUTALISK))
    with_drone_forces = (self.units(UnitTypeId.DRONE) | self.units(UnitTypeId.ZERGLING) |
                         self.units(UnitTypeId.ROACH) | self.units(UnitTypeId.RAVAGER) |
                         self.units(UnitTypeId.MUTALISK))
    larvae = self.units(UnitTypeId.LARVA)
    dangerous_structures = (self.enemy_structures(UnitTypeId.PHOTONCANNON) |
                            self.enemy_structures(UnitTypeId.BUNKER) |
                            self.enemy_structures(UnitTypeId.SPINECRAWLER))

    if not self.townhalls.exists:
        for unit in self.units(UnitTypeId.QUEEN) | with_drone_forces:
            unit.attack(self.enemy_start_locations[0])
        return
    else:
        first_base = self.townhalls.first
        if first_base.health < 401:
            self.proxy()
            return

    if not self.units(UnitTypeId.ROACH).exists and not self.units(UnitTypeId.RAVAGER).exists:
        await self.defending()
    else:
        self.defence = False

    pool_started = self.structures(UnitTypeId.SPAWNINGPOOL).amount + self.already_pending(UnitTypeId.SPAWNINGPOOL) > 0

    if not self.stop_drone:
        if self.supply_workers >= 19 or (not pool_started and self.supply_workers >= 14) or self.dangerous_structures_exist():
            self.stop_drone = True
    else:
        if pool_started and self.supply_workers < 19 and not self.dangerous_structures_exist():
            self.stop_drone = False

    if iteration == 30:
        await self.chat_send("gl hf!")
        print(f"\nOpponent_id: {self.opponent_id}\n\nMap size: {self.game_info.map_size[0]} {self.game_info.map_size[1]}\n\nStart location: {self.start_location.position[0]} {self.start_location[1]}")

    if len(self.locations) == 0:
        self.locations = self.get_locations()

    # BUILDING DRONES
    if len(self.mining_drones) < first_base.ideal_harvesters and (self.need_air_units or not self.stop_drone):
        if self.can_afford(UnitTypeId.DRONE) and larvae.exists:
            self.train(UnitTypeId.DRONE)

    if not self.dronny or self.dronny is None:
        drones_without_minerals = [unit for unit in self.units(UnitTypeId.DRONE) if not unit.is_carrying_resource]
        if len(drones_without_minerals) >= 1:
            self.dronny = self.closest_unit(drones_without_minerals, self.enemy_start_locations[0])

    # BUILDING SPAWNING POOL (earliest possible)
    if self.structures(UnitTypeId.SPAWNINGPOOL).amount + self.already_pending(UnitTypeId.SPAWNINGPOOL) == 0:
        self.dronny = self.refresh_unit(self.dronny)
        dronny = self.dronny
        distance = 8
        if self.time < 70 and dronny is not None:
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

        elif self.minerals >= 200 and self.units(UnitTypeId.DRONE).amount > 0 and dronny is not None:
            await self.build(UnitTypeId.SPAWNINGPOOL, build_worker=dronny, near=first_base)
            if dronny not in self.building_workers:
                self.building_workers.append(dronny)

    # BUILDING EXTRACTORS (Parallel)
    if pool_started and self.structures(UnitTypeId.EXTRACTOR).amount + self.already_pending(UnitTypeId.EXTRACTOR) < 2:
        free_geysers = self.vespene_geyser.closer_than(10, first_base)
        taken_geysers = self.structures(UnitTypeId.EXTRACTOR)
        available_geysers = [g for g in free_geysers
                             if all(get_distance(g.position, t.position) > 1 for t in taken_geysers)]
        if len(available_geysers) > 0 and self.can_afford(UnitTypeId.EXTRACTOR):
            drones_without_minerals = [unit for unit in self.units(UnitTypeId.DRONE)
                                       if not unit.is_carrying_resource and unit != self.dronny and unit not in self.building_workers]
            if len(drones_without_minerals) > 0:
                worker = min(drones_without_minerals,
                             key=lambda w: get_distance(w.position, available_geysers[0].position))
                worker.build(UnitTypeId.EXTRACTOR, available_geysers[0])
                if worker not in self.building_workers:
                    self.building_workers.append(worker)

    for extractor in self.structures(UnitTypeId.EXTRACTOR).ready:
        if extractor.assigned_harvesters < extractor.ideal_harvesters and not self.defence:
            w = self.workers.closer_than(10, extractor)
            if w.exists:
                available_drones = [d for d in w if d not in self.drones_on_gas and d != self.dronny and d not in self.building_workers]
                if available_drones:
                    drone = available_drones[0]
                    drone.gather(extractor)
                    self.drones_on_gas.append(drone)

    # BUILDING ROACH WARREN (no burrow upgrade needed for this strategy)
    if self.structures(UnitTypeId.SPAWNINGPOOL).ready.exists and \
            (self.structures(UnitTypeId.ROACHWARREN).amount + self.already_pending(UnitTypeId.ROACHWARREN) == 0):
        self.dronny = self.refresh_unit(self.dronny)
        dronny = self.dronny
        if not dronny or dronny is None:
            drones_without_minerals = [unit for unit in self.units(UnitTypeId.DRONE) if not unit.is_carrying_resource]
            if len(drones_without_minerals) >= 1:
                self.dronny = self.closest_unit(drones_without_minerals, self.enemy_start_locations[0])
                dronny = self.dronny

        distance = 8
        if dronny is not None:
            if self.time > 55 and not dronny.is_carrying_resource and \
                    get_distance(dronny.position, self.start_location) < distance:
                dronny.move(self.enemy_start_locations[0])
                if dronny not in self.building_workers:
                    self.building_workers.append(dronny)

            elif self.can_afford(UnitTypeId.ROACHWARREN):
                await self.build(UnitTypeId.ROACHWARREN, build_worker=dronny, near=dronny)
                if dronny not in self.building_workers:
                    self.building_workers.append(dronny)

            elif get_distance(dronny.position, self.start_location) >= distance:
                dronny.move(dronny.position)

    # GOING MACRO
    if self.need_air_units:
        if self.units(UnitTypeId.MUTALISK).amount > 4:
            self.need_air_units = False
        else:
            await self.macro_element()

    roach_warren_exists_or_pending = (self.structures(UnitTypeId.ROACHWARREN).exists or
                                      self.already_pending(UnitTypeId.ROACHWARREN) > 0)

    if first_base.is_idle and roach_warren_exists_or_pending:
        min_minerals = 225 + larvae.amount * 75
        if self.minerals >= min_minerals and \
                (not self.need_air_units or self.structures(UnitTypeId.LAIR).amount >= 1) and self.supply_left >= 2:
            first_base.train(UnitTypeId.QUEEN)

    # OVERLORD PRODUCTION — proactive supply management for ravager timing
    pending_roach_supply = self.already_pending(UnitTypeId.ROACH) * 2
    pending_ravager_supply = self.already_pending(UnitTypeId.RAVAGER) * 1
    current_army_supply = (self.units(UnitTypeId.ROACH).amount * 2 +
                           self.units(UnitTypeId.RAVAGER).amount * 3)
    pending_overlord_supply = self.already_pending(UnitTypeId.OVERLORD) * 8

    effective_supply_left = self.supply_left + pending_overlord_supply - pending_roach_supply - pending_ravager_supply


    need_overlord = False
    if effective_supply_left <= 2 and not self.already_pending(UnitTypeId.OVERLORD):
        need_overlord = True
    elif roach_warren_exists_or_pending and effective_supply_left <= 6 and not self.already_pending(UnitTypeId.OVERLORD):
        need_overlord = True
    elif (self.supply_left <= 0 or (self.units(UnitTypeId.DRONE).amount >= 14 and self.supply_left <= 1)) and \
            not self.already_pending(UnitTypeId.OVERLORD):
        need_overlord = True

    if roach_warren_exists_or_pending and effective_supply_left <= 12 and \
            self.already_pending(UnitTypeId.OVERLORD) <= 1 and \
            self.units(UnitTypeId.OVERLORD).amount + self.already_pending(UnitTypeId.OVERLORD) < 4:
        need_overlord = True

    if need_overlord:
        if self.can_afford(UnitTypeId.OVERLORD) and larvae.exists:
            larvae.random.train(UnitTypeId.OVERLORD)

    # BUILD ROACHES (they will all be morphed into Ravagers)
    if self.structures(UnitTypeId.ROACHWARREN).ready.exists and \
            self.can_afford(UnitTypeId.ROACH) and \
            larvae.exists and not self.need_air_units and \
            self.supply_left >= 2:
        larvae.random.train(UnitTypeId.ROACH)

    # ATTACK
    army_count = (self.units(UnitTypeId.ROACH).amount + self.units(UnitTypeId.RAVAGER).amount)

    if (army_count > 0 or (
            not self.no_units_in_opponent_main() and self.time > 100)) and self.need_to_attack_main_base:

        for unit in forces:
            # Skip units managed by ravager_manager
            if hasattr(self, 'handled_by_micro') and self.handled_by_micro is not None and unit.tag in self.handled_by_micro:
                continue

            for unit_in_known in self.known_enemy_u:
                if unit_in_known not in self.enemy_units:
                    self.known_enemy_u.remove(unit_in_known)

            if self.enemy_units.exists:
                closest_enemy_to_unit = self.closest_enemy_unit(unit)
                closest_enemy_to_base = self.closest_enemy_unit(self.townhalls.first)
                enemy_near_home_and_unit = (
                    get_distance(closest_enemy_to_base.position, self.townhalls.first.position) < 12 and
                    get_distance(closest_enemy_to_base.position, unit.position) < 13)
                enemy_is_close = get_distance(unit.position, closest_enemy_to_unit.position) < 5

                for enemy_unit in self.enemy_units:
                    if (enemy_unit not in self.known_enemy_u) and (
                            enemy_unit not in self.enemy_structures) and (
                            enemy_unit not in self.enemy_units(UnitTypeId.LARVA)) and (
                            not enemy_unit.is_flying):
                        self.known_enemy_u.append(enemy_unit)

                need_to_run_deep = ((self.time < 180) and
                                    (self.closest_unit_dist(unit=unit, units=dangerous_structures) < 15) and
                                    (get_distance(unit.position, self.enemy_start_locations[0].position) > 8) and
                                    (self.units(UnitTypeId.RAVAGER).amount < 3))

                if (len(self.known_enemy_u) > 0 and
                      (enemy_is_close or enemy_near_home_and_unit) and
                      (not closest_enemy_to_base.is_flying) and
                      (self.time > 120 or self.closest_unit_dist(unit=unit, units=dangerous_structures) > 10) and
                      (not need_to_run_deep)):
                    unit.attack(closest_enemy_to_base.position)

                elif get_distance(unit.position, self.enemy_start_locations[0]) < 7:
                    unit.attack(self.enemy_start_locations[0])

                elif ((unit.health_max - unit.health > 0) and
                        not need_to_run_deep):
                    self.accurate_attack(unit, attack_on_way=True)

                else:
                    self.accurate_attack(unit, attack_on_way=False)

            else:
                self.accurate_attack(unit, attack_on_way=False)

        self.manage_queen_attack()

    elif not self.need_to_attack_main_base:
        await self.find_final_structures(forces=forces,
                                         army=(self.units(UnitTypeId.ROACH) |
                                               self.units(UnitTypeId.RAVAGER) |
                                               self.units(UnitTypeId.OVERLORD)))

    if self.need_to_attack_main_base:
        await self.is_opponents_main_won()
