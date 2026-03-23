from sc2.units import Units
from sc2.ids.unit_typeid import UnitTypeId
from src.utils.coordinate_functions import *
from sc2.data import Race, ActionResult
from sc2.ids.ability_id import AbilityId
from sc2.ids.upgrade_id import UpgradeId
from src.utils.universal_functions import *
from src.utils.speed_mining import *


class RavagerStrategy:
    
    def __init__(self, bot):
        self.bot = bot
    
    def morph_ravagers(self):
        """Morph all available Roaches into Ravagers, but limit to 15 Ravagers total."""
        roaches = self.bot.units(UnitTypeId.ROACH)
    
        if not self.bot.structures(UnitTypeId.ROACHWARREN).ready.exists:
            return
    
        current_ravagers = self.bot.units(UnitTypeId.RAVAGER).amount
        if current_ravagers >= 15:
            return
    
        available_minerals = self.bot.minerals
        available_gas = self.bot.vespene
    
        for roach in roaches:
            if current_ravagers >= 15:
                break
            if available_minerals >= 25 and available_gas >= 75 and roach.is_ready:
                roach(AbilityId.MORPHTORAVAGER_RAVAGER)
                available_minerals -= 25
                available_gas -= 75
                current_ravagers += 1

    async def use_corrosive_bile(self):
        """Delegate Corrosive Bile usage to the ravager manager."""
        ravagers = self.bot.units(UnitTypeId.RAVAGER)
        roaches = self.bot.units(UnitTypeId.ROACH)
        if not ravagers.exists and not roaches.exists:
            return set()
    
        return await self.bot.ravager_manager.manage(
            bot=self.bot,
            ravagers=ravagers,
            roaches=roaches,
            enemy_units=self.bot.enemy_units,
            enemy_structures=self.bot.enemy_structures,
            enemy_start_location=self.bot.enemy_start_locations[0],
            own_start_location=self.bot.start_location,
            game_loop=self.bot.state.game_loop,
        )
    
    async def ravager_rush_step(self, iteration):
        await self.bot.mining_iteration()
        await self.bot.overlord_manager.manage(overlords=self.bot.units(UnitTypeId.OVERLORD),
                                           enemies=self.bot.air_danger_units())
        await self.bot.queen_management()
        self.morph_ravagers()
        self.bot.handled_by_micro = await self.use_corrosive_bile()
    
        if self.bot.units(UnitTypeId.RAVAGER).amount >= 8:
            if self.bot.enemy_race == Race.Terran and not self.bot.need_to_attack_main_base:
                self.bot.need_air_units = True
    
        forces = (self.bot.units(UnitTypeId.ZERGLING) | self.bot.units(UnitTypeId.ROACH) |
                  self.bot.units(UnitTypeId.RAVAGER) | self.bot.units(UnitTypeId.MUTALISK))
        with_drone_forces = (self.bot.units(UnitTypeId.DRONE) | self.bot.units(UnitTypeId.ZERGLING) |
                             self.bot.units(UnitTypeId.ROACH) | self.bot.units(UnitTypeId.RAVAGER) |
                             self.bot.units(UnitTypeId.MUTALISK))
        larvae = self.bot.units(UnitTypeId.LARVA)
        dangerous_structures = (self.bot.enemy_structures(UnitTypeId.PHOTONCANNON) |
                                self.bot.enemy_structures(UnitTypeId.BUNKER) |
                                self.bot.enemy_structures(UnitTypeId.SPINECRAWLER))
    
        if not self.bot.townhalls.exists:
            for unit in self.bot.units(UnitTypeId.QUEEN) | with_drone_forces:
                unit.attack(self.bot.enemy_start_locations[0])
            return
        else:
            first_base = self.bot.townhalls.first
            if first_base.health < 401:
                self.bot.proxy()
                return
    
        if not self.bot.units(UnitTypeId.ROACH).exists and not self.bot.units(UnitTypeId.RAVAGER).exists:
            await self.bot.defending()
        else:
            self.bot.defence = False
    
        if (not self.bot.stop_drone) and (
                self.bot.supply_workers >= 14 or
                (not (self.bot.structures(UnitTypeId.SPAWNINGPOOL).exists or self.bot.already_pending(UnitTypeId.SPAWNINGPOOL)))) \
                and not self.bot.dangerous_structures_exist():
            self.bot.stop_drone = True
    
        elif self.bot.stop_drone and (
                self.bot.structures(UnitTypeId.SPAWNINGPOOL).exists or self.bot.already_pending(UnitTypeId.SPAWNINGPOOL)) and (
                self.bot.structures(UnitTypeId.EXTRACTOR).exists or self.bot.already_pending(UnitTypeId.EXTRACTOR)) and (
                self.bot.supply_workers < 14 or self.bot.need_air_units):
            self.bot.stop_drone = False
    
        if iteration == 30:
            await self.bot.chat_send("gl hf!")
            print(f"\nOpponent_id: {self.bot.opponent_id}\n\nMap size: {self.bot.game_info.map_size[0]} {self.bot.game_info.map_size[1]}\n\nStart location: {self.bot.start_location.position[0]} {self.bot.start_location[1]}")
    
        if len(self.bot.locations) == 0:
            self.bot.locations = self.bot.get_locations()
    
        # BUILDING DRONES
        if self.bot.structures(UnitTypeId.ROACHWARREN).amount + self.bot.already_pending(UnitTypeId.ROACHWARREN) == 0:
            if len(self.bot.mining_drones) < first_base.ideal_harvesters and (self.bot.need_air_units or not self.bot.stop_drone):
                if self.bot.can_afford(UnitTypeId.DRONE) and larvae.exists:
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
                    dronny.move(self.bot.enemy_start_locations[0])
                    if dronny not in self.bot.building_workers:
                        self.bot.building_workers.append(dronny)
    
                elif self.bot.can_afford(UnitTypeId.SPAWNINGPOOL):
                    await self.bot.build(UnitTypeId.SPAWNINGPOOL, build_worker=dronny, near=dronny)
                    if dronny not in self.bot.building_workers:
                        self.bot.building_workers.append(dronny)
    
                elif get_distance(dronny.position, self.bot.start_location) >= distance and self.bot.minerals > 160:
                    dronny.move(dronny.position)
    
            elif self.bot.minerals >= 200 and self.bot.units(UnitTypeId.DRONE).amount > 0 and dronny is not None:
                await self.bot.build(UnitTypeId.SPAWNINGPOOL, build_worker=dronny, near=first_base)
                if dronny not in self.bot.building_workers:
                    self.bot.building_workers.append(dronny)
    
        # BUILDING EXTRACTORS
        if self.bot.structures(UnitTypeId.SPAWNINGPOOL).amount >= 1 and \
                (self.bot.structures(UnitTypeId.EXTRACTOR).amount + self.bot.already_pending(UnitTypeId.EXTRACTOR) == 0):
            self.bot.dronny = self.bot.refresh_unit(self.bot.dronny)
            dronny = self.bot.dronny
            if self.bot.can_afford(UnitTypeId.EXTRACTOR) and dronny is not None:
                target = self.bot.vespene_geyser.closest_to(
                    dronny.position)  # "When building the gas structure, the target needs to be a unit (the vespene geyser) not the position of the vespene geyser."
                dronny.build(UnitTypeId.EXTRACTOR, target)
                if dronny not in self.bot.building_workers:
                    self.bot.building_workers.append(dronny)
    
        if self.bot.structures(UnitTypeId.SPAWNINGPOOL).amount >= 1 and \
                self.bot.structures(UnitTypeId.EXTRACTOR).ready.exists and \
                (self.bot.structures(UnitTypeId.EXTRACTOR).amount + self.bot.already_pending(UnitTypeId.EXTRACTOR) == 1):
            existing_extractor = self.bot.structures(UnitTypeId.EXTRACTOR).first
            free_geysers = [g for g in self.bot.vespene_geyser.closer_than(15, first_base)
                            if get_distance(g.position, existing_extractor.position) > 2]
            if free_geysers and self.bot.can_afford(UnitTypeId.EXTRACTOR):
                drones_without_minerals = [unit for unit in self.bot.units(UnitTypeId.DRONE)
                                           if not unit.is_carrying_resource and unit != self.bot.dronny and unit not in self.bot.building_workers]
                if drones_without_minerals:
                    worker = drones_without_minerals[0]
                    worker.build(UnitTypeId.EXTRACTOR, free_geysers[0])
                    if worker not in self.bot.building_workers:
                        self.bot.building_workers.append(worker)
    
        for extractor in self.bot.structures(UnitTypeId.EXTRACTOR):
            if extractor.assigned_harvesters < extractor.ideal_harvesters and \
                    self.bot.structures(UnitTypeId.EXTRACTOR).ready.exists and not self.bot.defence:
                w = self.bot.workers.closer_than(6, extractor)
                if w.exists:
                    drone = w.random
                    if drone != self.bot.dronny:
                        drone.gather(extractor)
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
                    dronny.move(self.bot.enemy_start_locations[0])
                    if dronny not in self.bot.building_workers:
                        self.bot.building_workers.append(dronny)
    
                elif self.bot.structures(UnitTypeId.SPAWNINGPOOL).ready.exists and self.bot.can_afford(UnitTypeId.ROACHWARREN):
                    await self.bot.build(UnitTypeId.ROACHWARREN, build_worker=dronny, near=dronny)
                    if dronny not in self.bot.building_workers:
                        self.bot.building_workers.append(dronny)
    
                elif get_distance(dronny.position, self.bot.start_location) >= distance:
                    dronny.move(dronny.position)
    
        # GOING MACRO
        if self.bot.need_air_units:
            if self.bot.units(UnitTypeId.MUTALISK).amount > 4:
                self.bot.need_air_units = False
            else:
                await self.bot.macro_element()
    
        if first_base.is_idle:
            min_minerals = 225 + larvae.amount * 75
            if self.bot.minerals >= min_minerals and self.bot.already_pending_upgrade(UpgradeId.BURROW) == 1 and \
                    (not self.bot.need_air_units or self.bot.structures(UnitTypeId.LAIR).amount >= 1) and self.bot.supply_left >= 2:
                first_base.train(UnitTypeId.QUEEN)
    
        if self.bot.structures(UnitTypeId.ROACHWARREN).amount + self.bot.already_pending(UnitTypeId.ROACHWARREN) > 0:
            if (self.bot.supply_left <= 1 or (self.bot.units(UnitTypeId.DRONE).amount >= 13 and self.bot.supply_left <= 2)) and \
                    not self.bot.already_pending(UnitTypeId.OVERLORD):
                if self.bot.can_afford(UnitTypeId.OVERLORD) and larvae.exists:
                    larvae.random.train(UnitTypeId.OVERLORD)
    
        if self.bot.structures(UnitTypeId.ROACHWARREN).ready.exists and \
                self.bot.can_afford(UnitTypeId.ROACH) and \
                larvae.exists and not self.bot.need_air_units:
            larvae.random.train(UnitTypeId.ROACH)
    
        # ATTACK
        army_count = (self.bot.units(UnitTypeId.ROACH).amount + self.bot.units(UnitTypeId.RAVAGER).amount)
    
        if (army_count > 0 or (
                not self.bot.no_units_in_opponent_main() and self.bot.time > 100)) and self.bot.need_to_attack_main_base:
    
            for unit in forces:
                # Skip units managed by ravager_manager
                if hasattr(self.bot, 'handled_by_micro') and self.bot.handled_by_micro is not None and unit.tag in self.bot.handled_by_micro:
                    continue
    
                for unit_in_known in self.bot.known_enemy_u:
                    if unit_in_known not in self.bot.enemy_units:
                        self.bot.known_enemy_u.remove(unit_in_known)
    
                if self.bot.enemy_units.exists:
                    closest_enemy_to_unit = self.bot.closest_enemy_unit(unit)
                    closest_enemy_to_base = self.bot.closest_enemy_unit(self.bot.townhalls.first)
                    enemy_near_home_and_unit = (
                        get_distance(closest_enemy_to_base.position, self.bot.townhalls.first.position) < 12 and
                        get_distance(closest_enemy_to_base.position, unit.position) < 13)
                    enemy_is_close = get_distance(unit.position, closest_enemy_to_unit.position) < 5
    
                    for enemy_unit in self.bot.enemy_units:
                        if (enemy_unit not in self.bot.known_enemy_u) and (
                                enemy_unit not in self.bot.enemy_structures) and (
                                enemy_unit not in self.bot.enemy_units(UnitTypeId.LARVA)) and (
                                not enemy_unit.is_flying):
                            self.bot.known_enemy_u.append(enemy_unit)
    
                    need_to_run_deep = ((self.bot.time < 180) and
                                        (self.bot.closest_unit_dist(unit=unit, units=dangerous_structures) < 15) and
                                        (get_distance(unit.position, self.bot.enemy_start_locations[0].position) > 8) and
                                        (self.bot.units(UnitTypeId.RAVAGER).amount < 3))
    
                    if (len(self.bot.known_enemy_u) > 0 and
                          (enemy_is_close or enemy_near_home_and_unit) and
                          (not closest_enemy_to_base.is_flying) and
                          (self.bot.time > 120 or self.bot.closest_unit_dist(unit=unit, units=dangerous_structures) > 10) and
                          (not need_to_run_deep)):
                        unit.attack(closest_enemy_to_base.position)
    
                    elif get_distance(unit.position, self.bot.enemy_start_locations[0]) < 7:
                        unit.attack(self.bot.enemy_start_locations[0])
    
                    elif ((unit.health_max - unit.health > 0) and
                            not need_to_run_deep):
                        self.bot.accurate_attack(unit, attack_on_way=True)
    
                    else:
                        self.bot.accurate_attack(unit, attack_on_way=False)
    
                else:
                    self.bot.accurate_attack(unit, attack_on_way=False)
    
            self.bot.manage_queen_attack()
    
        elif not self.bot.need_to_attack_main_base:
            await self.bot.find_final_structures(forces=forces,
                                             army=(self.bot.units(UnitTypeId.ROACH) |
                                                   self.bot.units(UnitTypeId.RAVAGER) |
                                                   self.bot.units(UnitTypeId.OVERLORD)))
    
        if self.bot.need_to_attack_main_base:
            await self.bot.is_opponents_main_won()
