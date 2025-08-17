from sc2.units import Units
from sc2.ids.unit_typeid import UnitTypeId
from coordinate_functions import *
from sc2.data import Race, ActionResult
from sc2.ids.ability_id import AbilityId
from sc2.ids.upgrade_id import UpgradeId
from _universal_functions import *
from _speed_mining import *


def burrow_micro(self):
    if UpgradeId.BURROW not in self.state.upgrades:
        return

    for roach in self.units(UnitTypeId.ROACH):
        if roach.health <= 40 and not roach.is_burrowed:
            roach(AbilityId.BURROWDOWN_ROACH)
    for burrowed_roach in self.units(UnitTypeId.ROACHBURROWED):
        health_up_border = 110
        if self.units(UnitTypeId.ROACH).amount > 0:
            closest_roach = self.closest_unit([unit for unit in self.units(UnitTypeId.ROACH)], burrowed_roach)
            if get_distance(burrowed_roach.position, closest_roach.position) < 3:
                health_up_border = 70
        if burrowed_roach.health >= health_up_border and burrowed_roach.is_burrowed:
            burrowed_roach(AbilityId.BURROWUP_ROACH)

    for queen in self.units(UnitTypeId.QUEEN):
        if queen.health <= 40 and not queen.is_burrowed:
            queen(AbilityId.BURROWDOWN_QUEEN)
    for burrowed_queen in self.units(UnitTypeId.QUEENBURROWED):
        if burrowed_queen.health >= 110 and burrowed_queen.is_burrowed:
            burrowed_queen(AbilityId.BURROWUP_QUEEN)


async def roach_rush_step(self, iteration):
    await self.mining_iteration()
    await self.overlord_management()
    await self.queen_management()
    await self.micro_element()
    self.burrow_micro()

    if self.units(UnitTypeId.ROACH).amount >= 16:
        if self.enemy_race == Race.Terran and not self.need_to_attack_main_base:
            self.need_air_units = True

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
        print(f"\nOpponent_id: {self.opponent_id}\n\nMap size: {self.game_info.map_size[0]} {self.game_info.map_size[1]}\n\nStart location: {self.start_location.position[0]} {self.start_location[1]}")

    if len(self.locations) == 0:
        self.locations = self.get_locations()

    # BUILDING DRONES

    if len(self.mining_drones) < first_base.ideal_harvesters and (self.need_air_units or not self.stop_drone):
        if self.can_afford(UnitTypeId.DRONE) and larvae.exists and (
                self.time < 67 or self.structures(UnitTypeId.ROACHWARREN).ready.exists):
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

    if self.structures(UnitTypeId.SPAWNINGPOOL).amount >= 1 and\
            (self.structures(UnitTypeId.EXTRACTOR).amount + self.already_pending(UnitTypeId.EXTRACTOR) == 0):
        self.dronny = self.refresh_unit(self.dronny)
        dronny = self.dronny
        if self.can_afford(UnitTypeId.EXTRACTOR) and dronny is not None:
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
        if self.minerals >= min_minerals and self.already_pending_upgrade(UpgradeId.BURROW) == 1 and \
                (not self.need_air_units or self.structures(UnitTypeId.LAIR).amount >= 1) and self.supply_left >= 2:
            first_base.train(UnitTypeId.QUEEN)

    if (self.supply_left <= 0 or (self.units(UnitTypeId.DRONE).amount >= 14 and self.supply_left <= 1)) and \
            not self.already_pending(UnitTypeId.OVERLORD):
        if self.can_afford(UnitTypeId.OVERLORD) and larvae.exists:
            larvae.random.train(UnitTypeId.OVERLORD)

    if self.already_pending_upgrade(UpgradeId.BURROW) == 0 and self.can_afford(
            UpgradeId.BURROW
    ):
        self.research(UpgradeId.BURROW)

    if self.structures(UnitTypeId.ROACHWARREN).ready.exists and \
            self.can_afford(UnitTypeId.ROACH) and \
            larvae.exists and not self.need_air_units:
        larvae.random.train(UnitTypeId.ROACH)

    # ATTACK

    if (self.units(UnitTypeId.ROACH).amount > 0 or (
            not self.no_units_in_opponent_main() and self.time > 100)) and self.need_to_attack_main_base:

        for unit in forces:

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
                                                                self.closest_enemy_unit(unit).position) < 5:
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
