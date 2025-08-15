from sc2.units import Units
from sc2.ids.unit_typeid import UnitTypeId
from coordinate_functions import *
from sc2.data import Race, ActionResult
from sc2.ids.ability_id import AbilityId
from sc2.ids.upgrade_id import UpgradeId
from _universal_functions import *
from _speed_mining import *


async def roach_rush_macro_element(self):
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
                w.random.gather(extractor)  # !!!

    if self.structures(UnitTypeId.SPAWNINGPOOL).ready.exists:
        if not self.structures(UnitTypeId.LAIR).exists and not self.structures(
                UnitTypeId.HIVE).exists and first_base.is_idle:
            if self.can_afford(UnitTypeId.LAIR):
                first_base.build(UnitTypeId.LAIR)

    if self.structures(UnitTypeId.LAIR).ready.exists:   # ROACHVAREN
        if not (self.structures(UnitTypeId.SPIRE).exists or self.already_pending(UnitTypeId.SPIRE)):
            if self.can_afford(UnitTypeId.SPIRE):
                dronny = self.units(UnitTypeId.DRONE).random
                await self.build(UnitTypeId.SPIRE, build_worker=dronny, near=first_base)
                if dronny not in self.building_workers:
                    self.building_workers.append(dronny)

    if self.structures(UnitTypeId.SPIRE).ready.exists:  # ROACH
        if self.units(UnitTypeId.LARVA).exists:
            larva = self.units(UnitTypeId.LARVA).random
            if self.can_afford(UnitTypeId.MUTALISK):
                larva.train(UnitTypeId.MUTALISK)
                return


async def roach_rush_step(self, iteration):
    await self.mining_iteration()
    await self.overlord_management()
    await self.queen_management()
    await self.micro_element()

    forces = self.units(UnitTypeId.ZERGLING) | self.units(UnitTypeId.ROACH) | self.units(UnitTypeId.MUTALISK)
    with_drone_forces = self.units(UnitTypeId.DRONE) | self.units(UnitTypeId.ZERGLING) | self.units(UnitTypeId.ROACH) | self.units(
        UnitTypeId.MUTALISK)
    larvae = self.units(UnitTypeId.LARVA)

    if not self.townhalls.exists:
        for unit in self.units(UnitTypeId.QUEEN) | with_drone_forces:
            unit.attack(self.enemy_start_locations[0])
        return
    else:
        first_base = self.townhalls.first
        if first_base.health < 401:
            self.proxy()
            return

    if not self.units(UnitTypeId.ROACH).exists:
        await self.defending()
    else:
        self.defence = False

    if (not self.stop_drone) and (
            self.supply_workers >= 14 or
            (not (self.structures(UnitTypeId.SPAWNINGPOOL).exists or self.already_pending(UnitTypeId.SPAWNINGPOOL)))) \
            and not self.dangerous_structures_exist():
        self.stop_drone = True

    elif self.stop_drone and (
            self.structures(UnitTypeId.SPAWNINGPOOL).exists or self.already_pending(UnitTypeId.SPAWNINGPOOL)) and (
            self.structures(UnitTypeId.EXTRACTOR).exists or self.already_pending(UnitTypeId.EXTRACTOR)) and (
            self.supply_workers < 14 or self.need_air_units):
        self.stop_drone = False

    if iteration == 30:
        await self.chat_send("gl hf!")
        print(
            f"\nOpponent_id: {self.opponent_id}\n\nMap size: {self.game_info.map_size[0]} {self.game_info.map_size[1]}\n\nStart location: {self.start_location.position[0]} {self.start_location[1]}")

    if len(self.locations) == 0:
        self.locations = self.get_locations()

    # BUILDING DRONES

    if len(self.mining_drones) < first_base.ideal_harvesters and (self.need_air_units or not self.stop_drone):
        if self.can_afford(UnitTypeId.DRONE) and larvae.exists and (
                self.time < 67 or self.structures(UnitTypeId.ROACHWARREN).ready.exists):
            self.train(UnitTypeId.DRONE)

    if not self.dronny or self.dronny is None:
        self.dronny = self.closest_unit(
            [unit for unit in self.units(UnitTypeId.DRONE) if not unit.is_carrying_resource],
            self.enemy_start_locations[0])

    # BUILDING SPAWNING POOL

    if self.structures(UnitTypeId.SPAWNINGPOOL).amount + self.already_pending(UnitTypeId.SPAWNINGPOOL) == 0:
        self.dronny = self.refresh_unit(self.dronny)
        dronny = self.dronny
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

    # BUILDING EXTRACTOR

    if self.structures(UnitTypeId.SPAWNINGPOOL).amount >= 1 and\
            (self.structures(UnitTypeId.EXTRACTOR).amount + self.already_pending(UnitTypeId.EXTRACTOR) == 0):
        dronny = self.refresh_unit(self.dronny)
        if self.can_afford(UnitTypeId.EXTRACTOR):
            target = self.vespene_geyser.closest_to(
                dronny.position)  # "When building the gas structure, the target needs to be a unit (the vespene geyser) not the position of the vespene geyser."
            dronny.build(UnitTypeId.EXTRACTOR, target)
            if dronny not in self.building_workers:
                self.building_workers.append(dronny)

    for extractor in self.structures(UnitTypeId.EXTRACTOR):
        if extractor.assigned_harvesters < extractor.ideal_harvesters and \
                self.structures(UnitTypeId.EXTRACTOR).ready.exists:
            w = self.workers.closer_than(6, extractor)
            if w.exists:
                drone = w.random
                drone.gather(extractor)  # !!!
                self.drones_on_gas.append(drone)

    # BUILDING ROACH WARREN

    if self.structures(UnitTypeId.SPAWNINGPOOL).amount >= 1 and \
            (self.structures(UnitTypeId.ROACHWARREN).amount + self.already_pending(UnitTypeId.ROACHWARREN) == 0):
        dronny = self.refresh_unit(self.dronny)
        if not dronny or dronny is None:
            self.dronny = self.closest_unit(
                [unit for unit in self.units(UnitTypeId.DRONE) if not unit.is_carrying_resource],
                self.enemy_start_locations[0])
            dronny = self.dronny

        distance = 8
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

    if (self.supply_left <= 0 or (self.units(UnitTypeId.DRONE).amount >= 14 and self.supply_left <= 1)) and \
            not self.already_pending(UnitTypeId.OVERLORD):
        if self.can_afford(UnitTypeId.OVERLORD) and larvae.exists:
            larvae.random.train(UnitTypeId.OVERLORD)

    if self.already_pending_upgrade(UpgradeId.BURROW) == 0 and self.can_afford(
            UpgradeId.BURROW
    ):
        self.research(UpgradeId.BURROW)

    if self.structures(UnitTypeId.ROACHWARREN).ready.exists and self.can_afford(UnitTypeId.ROACH) and larvae.exists:
        larvae.random.train(UnitTypeId.ROACH)

    # ATTACK

    '''
    for unit in forces:
        unit.attack(self.enemy_start_locations[0])
    '''

    if (self.units(UnitTypeId.ROACH).amount > 0 or (
            not self.no_units_in_opponent_main() and self.time > 100)) and self.need_to_attack_main_base:
        for unit in forces:
            if self.enemy_units.exists:

                for enemy_unit in self.enemy_units:
                    if (enemy_unit not in self.known_enemy_u) and (
                            enemy_unit not in self.enemy_structures) and (
                            enemy_unit not in self.enemy_units(UnitTypeId.LARVA)) and (
                            not enemy_unit.is_flying):
                        self.known_enemy_u.append(enemy_unit)

                for unit_in_known in self.known_enemy_u:
                    if unit_in_known not in self.enemy_units:
                        self.known_enemy_u.remove(unit_in_known)

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
        await self.find_final_structures(forces=forces, army=(self.units(UnitTypeId.ROACH) | self.units(UnitTypeId.OVERLORD)))

    if self.need_to_attack_main_base:
        await self.is_opponents_main_won()
