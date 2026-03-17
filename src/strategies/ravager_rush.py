from sc2.units import Units
from sc2.ids.unit_typeid import UnitTypeId
from src.utils.coordinate_functions import *
from sc2.data import Race, ActionResult
from sc2.ids.ability_id import AbilityId
from sc2.ids.upgrade_id import UpgradeId
from src.utils.universal_functions import *
from src.utils.speed_mining import *


def find_priority_targets(self):
    """Find priority defensive structures to target with Corrosive Bile."""
    priority_structures = (
        self.enemy_structures(UnitTypeId.PHOTONCANNON) |
        self.enemy_structures(UnitTypeId.SHIELDBATTERY) |
        self.enemy_structures(UnitTypeId.BUNKER) |
        self.enemy_structures(UnitTypeId.SPINECRAWLER) |
        self.enemy_structures(UnitTypeId.SPORECRAWLER)
    )
    return priority_structures


def find_bile_targets(self):
    """Find all valid targets for Corrosive Bile, prioritizing defensive structures,
    then buildings under construction, then other structures."""
    priority = find_priority_targets(self)

    constructing = [s for s in self.enemy_structures if s.build_progress < 1.0]

    other_structures = [s for s in self.enemy_structures
                        if s not in priority and s not in constructing]

    targets = list(priority) + constructing + other_structures
    return targets


def use_corrosive_bile(self):
    """Cast Corrosive Bile on the best available target for each Ravager."""
    ravagers = self.units(UnitTypeId.RAVAGER)
    if not ravagers.exists:
        return

    bile_targets = find_bile_targets(self)

    dangerous_enemies = [u for u in self.enemy_units if not u.is_flying and not u.is_hallucination]

    all_targets = list(bile_targets) + list(dangerous_enemies)

    if len(all_targets) == 0:
        return

    for ravager in ravagers:
        abilities = ravager.abilities
        if AbilityId.EFFECT_CORROSIVEBILE not in abilities:
            continue

        best_target = None
        best_dist = 999

        for target in bile_targets:
            d = get_distance(ravager.position, target.position)
            if d < 9 and d < best_dist:
                best_dist = d
                best_target = target

        if best_target is None:
            for target in dangerous_enemies:
                d = get_distance(ravager.position, target.position)
                if d < 9 and d < best_dist:
                    best_dist = d
                    best_target = target

        if best_target is not None:
            ravager(AbilityId.EFFECT_CORROSIVEBILE, best_target.position)


def morph_ravagers(self):
    """Morph Roaches into Ravagers, keeping some Roaches as a frontline."""
    roaches = self.units(UnitTypeId.ROACH)
    ravager_count = self.units(UnitTypeId.RAVAGER).amount

    max_ravagers = 8
    min_roaches_to_keep = 2

    if ravager_count >= max_ravagers:
        return

    if not self.structures(UnitTypeId.ROACHWARREN).ready.exists:
        return

    for roach in roaches:
        if ravager_count >= max_ravagers:
            break
        if roaches.amount - 1 < min_roaches_to_keep:
            break
        if self.can_afford(UnitTypeId.RAVAGER) and roach.is_ready:
            roach(AbilityId.MORPHTORAVAGER_RAVAGER)
            ravager_count += 1


async def ravager_rush_step(self, iteration):
    await self.mining_iteration()
    await self.overlord_manager.manage(overlords=self.units(UnitTypeId.OVERLORD),
                                       enemies=self.air_danger_units())
    await self.queen_management()
    await self.micro_element()
    self.morph_ravagers()
    self.use_corrosive_bile()

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

    if (not self.stop_drone) and (
            self.supply_workers >= 16 or
            (not (self.structures(UnitTypeId.SPAWNINGPOOL).exists or self.already_pending(UnitTypeId.SPAWNINGPOOL)))) \
            and not self.dangerous_structures_exist():
        self.stop_drone = True

    elif self.stop_drone and (
            self.structures(UnitTypeId.SPAWNINGPOOL).exists or self.already_pending(UnitTypeId.SPAWNINGPOOL)) and (
            self.structures(UnitTypeId.EXTRACTOR).exists or self.already_pending(UnitTypeId.EXTRACTOR)) and (
            self.supply_workers < 16 or self.need_air_units):
        self.stop_drone = False

    if iteration == 30:
        await self.chat_send("gl hf!")
        print(f"\nOpponent_id: {self.opponent_id}\n\nMap size: {self.game_info.map_size[0]} {self.game_info.map_size[1]}\n\nStart location: {self.start_location.position[0]} {self.start_location[1]}")

    if len(self.locations) == 0:
        self.locations = self.get_locations()

    # BUILDING DRONES

    if len(self.mining_drones) < first_base.ideal_harvesters and (self.need_air_units or not self.stop_drone):
        if self.can_afford(UnitTypeId.DRONE) and larvae.exists and (
                (self.time < 70 and self.supply_used < 14) or self.structures(UnitTypeId.ROACHWARREN).ready.exists):
            self.train(UnitTypeId.DRONE)

    if not self.dronny or self.dronny is None:
        drones_without_minerals = [unit for unit in self.units(UnitTypeId.DRONE) if not unit.is_carrying_resource]
        if len(drones_without_minerals) >= 1:
            self.dronny = self.closest_unit(drones_without_minerals, self.enemy_start_locations[0])

    # BUILDING SPAWNING POOL

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

    # BUILDING EXTRACTOR

    if self.structures(UnitTypeId.SPAWNINGPOOL).amount >= 1 and \
            (self.structures(UnitTypeId.EXTRACTOR).amount + self.already_pending(UnitTypeId.EXTRACTOR) == 0):
        self.dronny = self.refresh_unit(self.dronny)
        dronny = self.dronny
        if self.can_afford(UnitTypeId.EXTRACTOR) and dronny is not None:
            target = self.vespene_geyser.closest_to(dronny.position)
            dronny.build(UnitTypeId.EXTRACTOR, target)
            if dronny not in self.building_workers:
                self.building_workers.append(dronny)

    # SECOND EXTRACTOR (ravagers need more gas)

    if self.structures(UnitTypeId.ROACHWARREN).ready.exists and \
            self.structures(UnitTypeId.EXTRACTOR).ready.amount >= 1 and \
            self.structures(UnitTypeId.EXTRACTOR).amount + self.already_pending(UnitTypeId.EXTRACTOR) < 2:
        free_geysers = self.vespene_geyser.closer_than(10, first_base)
        taken_geysers = self.structures(UnitTypeId.EXTRACTOR)
        available_geysers = [g for g in free_geysers
                             if all(get_distance(g.position, t.position) > 1 for t in taken_geysers)]
        if len(available_geysers) > 0 and self.can_afford(UnitTypeId.EXTRACTOR):
            worker = self.workers.closest_to(available_geysers[0])
            if worker is not None and worker != self.dronny:
                worker.build(UnitTypeId.EXTRACTOR, available_geysers[0])
                if worker not in self.building_workers:
                    self.building_workers.append(worker)

    for extractor in self.structures(UnitTypeId.EXTRACTOR):
        if extractor.assigned_harvesters < extractor.ideal_harvesters and \
                self.structures(UnitTypeId.EXTRACTOR).ready.exists and not self.defence:
            w = self.workers.closer_than(6, extractor)
            if w.exists:
                drone = w.random
                if drone != self.dronny:
                    drone.gather(extractor)
                    self.drones_on_gas.append(drone)

    # BUILDING ROACH WARREN

    if self.structures(UnitTypeId.SPAWNINGPOOL).amount >= 1 and \
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

            elif self.structures(UnitTypeId.SPAWNINGPOOL).ready.exists and self.can_afford(UnitTypeId.ROACHWARREN):
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

    if first_base.is_idle:
        min_minerals = 225 + larvae.amount * 75
        if self.minerals >= min_minerals and \
                (not self.need_air_units or self.structures(UnitTypeId.LAIR).amount >= 1) and self.supply_left >= 2:
            first_base.train(UnitTypeId.QUEEN)

    if (self.supply_left <= 0 or (self.units(UnitTypeId.DRONE).amount >= 14 and self.supply_left <= 1)) and \
            not self.already_pending(UnitTypeId.OVERLORD):
        if self.can_afford(UnitTypeId.OVERLORD) and larvae.exists:
            larvae.random.train(UnitTypeId.OVERLORD)

    # BUILD ROACHES (they will be morphed into Ravagers)

    if self.structures(UnitTypeId.ROACHWARREN).ready.exists and \
            self.can_afford(UnitTypeId.ROACH) and \
            larvae.exists and not self.need_air_units:
        larvae.random.train(UnitTypeId.ROACH)

    # ATTACK

    army_count = (self.units(UnitTypeId.ROACH).amount + self.units(UnitTypeId.RAVAGER).amount)

    if (army_count > 0 or (
            not self.no_units_in_opponent_main() and self.time > 100)) and self.need_to_attack_main_base:

        for unit in forces:
            if unit not in self.in_burrow_process:
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

                    # Ravagers should push through defenses, so less retreating
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
