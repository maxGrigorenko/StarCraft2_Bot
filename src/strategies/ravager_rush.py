from sc2.ids.unit_typeid import UnitTypeId
from sc2.ids.ability_id import AbilityId
from src.utils.coordinate_functions import *
from sc2.data import Race, ActionResult
from sc2.ids.upgrade_id import UpgradeId
from src.managers.action_registry import ActionPriority
from src.utils.coordinate_functions import get_distance
from src.strategies.base_strategy import BaseStrategy


class RavagerStrategy(BaseStrategy):

    def __init__(self, bot):
        super().__init__(bot)

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
            if available_minerals >= 25 and available_gas >= 75 and roach.is_ready and get_distance(roach.position, self.bot.start_location) > 4:
                self.bot.action_registry.submit_action(
                    tag=roach.tag,
                    action=lambda r=roach: r(AbilityId.MORPHTORAVAGER_RAVAGER),
                    priority=ActionPriority.HIGH,
                    source="ravager_rush_morph"
                )
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

    # ------------------------------------------------------------------
    # Helper methods
    # ------------------------------------------------------------------
    def _update_drone_production(self):
        stop = False
        resume = False
        drone_supply = self.bot.supply_workers
        pool_exists = self.bot.structures(UnitTypeId.SPAWNINGPOOL).exists or self.bot.already_pending(
            UnitTypeId.SPAWNINGPOOL)
        extractor_exists = self.bot.structures(UnitTypeId.EXTRACTOR).exists or self.bot.already_pending(
            UnitTypeId.EXTRACTOR)
        dangerous_structures = self.bot.unit_helper.dangerous_structures_exist()

        if self.bot.stop_drone:
            if pool_exists and extractor_exists and (drone_supply < 14 or self.bot.need_air_units):
                resume = True
        else:
            if (drone_supply >= 14 or not pool_exists) and not dangerous_structures:
                stop = True

        if stop:
            self.bot.stop_drone = True
        elif resume:
            self.bot.stop_drone = False

    def _ravager_attack_micro(self, unit, dangerous_structures):
        self.update_known_enemies()

        if not self.bot.enemy_units.exists:
            self.bot.combat_helper.accurate_attack(unit, need_additional_attack_command=False)
            return

        closest_enemy_to_unit = self.bot.combat_helper.closest_enemy_unit(unit)
        closest_enemy_to_base = self.bot.combat_helper.closest_enemy_unit(self.bot.townhalls.first)
        enemy_near_home_and_unit = (
            get_distance(closest_enemy_to_base.position, self.bot.townhalls.first.position) < 12 and
            get_distance(closest_enemy_to_base.position, unit.position) < 13)
        enemy_is_close = get_distance(unit.position, closest_enemy_to_unit.position) < 5

        if (len(self.bot.known_enemy_u) > 0 and
                (enemy_is_close or enemy_near_home_and_unit) and
                (not closest_enemy_to_base.is_flying) and
                (self.bot.time > 120 or self.bot.combat_helper.closest_unit_dist(
                    unit=unit, units=dangerous_structures) > 10)):
            self.bot.action_registry.submit_action(
                tag=unit.tag,
                action=lambda u=unit, t=closest_enemy_to_base.position: u.attack(t),
                priority=ActionPriority.HIGH-1,
                source="ravager_rush_attack_enemy"
            )
            return

        if get_distance(unit.position, self.bot.enemy_start_locations[0]) < 7:
            self.bot.action_registry.submit_action(
                tag=unit.tag,
                action=lambda u=unit, t=self.bot.enemy_start_locations[0]: u.attack(t),
                priority=ActionPriority.NORMAL,
                source="ravager_rush_attack_start_loc"
            )
            return

        if self.bot.enemy_race == Race.Zerg:
            self.bot.combat_helper.accurate_attack(unit, attack_on_way=True)
        else:
            self.bot.combat_helper.accurate_attack(unit, need_additional_attack_command=False)

    # ------------------------------------------------------------------
    # Main step
    # ------------------------------------------------------------------
    async def ravager_rush_step(self, iteration):
        await self.bot.economy_helper.mining_iteration()
        await self.bot.overlord_manager.manage(overlords=self.bot.units(UnitTypeId.OVERLORD),
                                               enemies=self.bot.scouting_helper.air_danger_units())
        await self.bot.combat_helper.queen_management()
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
        dangerous_structures = self.dangerous_structures()

        if self.emergency_attack_no_townhalls(with_drone_forces):
            return

        first_base = self.bot.townhalls.first
        if self.check_main_base_health():
            return

        if not self.bot.units(UnitTypeId.ROACH).exists and not self.bot.units(UnitTypeId.RAVAGER).exists:
            await self.bot.combat_helper.defending()
        else:
            self.bot.defence = False

        self._update_drone_production()

        if iteration == 30:
            await self.bot.chat_send("gl hf!")
            print(
                f"\nOpponent_id: {self.bot.opponent_id}\n\nMap size: {self.bot.game_info.map_size[0]} {self.bot.game_info.map_size[1]}\n\nStart location: {self.bot.start_location.position[0]} {self.bot.start_location[1]}")

        if len(self.bot.locations) == 0:
            self.bot.locations = self.bot.scouting_helper.get_locations()

        # BUILDING DRONES
        if self.bot.structures(UnitTypeId.ROACHWARREN).amount + self.bot.already_pending(UnitTypeId.ROACHWARREN) == 0:
            if len(self.bot.mining_drones_tags) < first_base.ideal_harvesters and (
                    self.bot.need_air_units or not self.bot.stop_drone):
                if self.bot.can_afford(UnitTypeId.DRONE) and larvae.exists:
                    self.bot.train(UnitTypeId.DRONE)

        dronny = self.find_dronny()

        # BUILDING SPAWNING POOL
        self.build_spawning_pool(dronny, first_base)

        # BUILDING EXTRACTORS
        dronny = self.find_dronny()
        self.build_first_extractor(dronny)

        if self.bot.structures(UnitTypeId.SPAWNINGPOOL).amount >= 1 and \
                self.bot.structures(UnitTypeId.EXTRACTOR).ready.exists and \
                (self.bot.structures(UnitTypeId.EXTRACTOR).amount + self.bot.already_pending(
                    UnitTypeId.EXTRACTOR) == 1):

            existing_extractor = self.bot.structures(UnitTypeId.EXTRACTOR).first
            free_geysers = [g for g in self.bot.vespene_geyser.closer_than(15, first_base)
                            if get_distance(g.position, existing_extractor.position) > 2]

            if free_geysers and self.bot.can_afford(UnitTypeId.EXTRACTOR):
                drones_without_minerals = [unit for unit in self.bot.units(UnitTypeId.DRONE)
                                           if not unit.is_carrying_resource
                                           and unit.tag != self.bot.dronny_tag
                                           and unit.tag not in self.bot.building_workers_tags]

                if drones_without_minerals:
                    worker = drones_without_minerals[0]
                    self.bot.action_registry.submit_action(
                        tag=worker.tag,
                        action=lambda w=worker, g=free_geysers[0]: w.build(UnitTypeId.EXTRACTOR, g),
                        priority=60,
                        source="ravager_rush_build_second_extractor"
                    )
                    self.mark_building_worker(worker.tag)

        self.assign_gas_gatherers()

        # BUILDING ROACH WARREN
        if self.bot.structures(UnitTypeId.SPAWNINGPOOL).amount >= 1 and \
                (self.bot.structures(UnitTypeId.ROACHWARREN).amount + self.bot.already_pending(
                    UnitTypeId.ROACHWARREN) == 0):
            dronny = self.find_dronny()

            distance = 8
            if dronny is not None:
                if self.bot.time > 55 and not dronny.is_carrying_resource and \
                        get_distance(dronny.position, self.bot.start_location) < distance:
                    self.bot.action_registry.submit_action(
                        tag=dronny.tag,
                        action=lambda d=dronny, t=self.bot.enemy_start_locations[0]: d.move(t),
                        priority=ActionPriority.LOW,
                        source="ravager_rush_drone_move_to_enemy"
                    )
                    self.mark_building_worker(dronny.tag)

                elif self.bot.structures(UnitTypeId.SPAWNINGPOOL).ready.exists and self.bot.can_afford(
                        UnitTypeId.ROACHWARREN):
                    await self.bot.build(UnitTypeId.ROACHWARREN, build_worker=dronny, near=dronny)
                    self.mark_building_worker(dronny.tag)

                elif get_distance(dronny.position, self.bot.start_location) >= distance:
                    self.bot.action_registry.submit_action(
                        tag=dronny.tag,
                        action=lambda d=dronny: d.move(d.position),
                        priority=ActionPriority.LOW,
                        source="ravager_rush_drone_move_self"
                    )

        # GOING MACRO
        if self.bot.need_air_units:
            if self.bot.units(UnitTypeId.MUTALISK).amount > 4:
                self.bot.need_air_units = False
            else:
                await self.bot.economy_helper.macro_element()

        if first_base.is_idle:
            min_minerals = 225 + larvae.amount * 75
            if self.bot.minerals >= min_minerals and self.bot.already_pending_upgrade(UpgradeId.BURROW) == 1 and \
                    (not self.bot.need_air_units or self.bot.structures(
                        UnitTypeId.LAIR).amount >= 1) and self.bot.supply_left >= 2:
                self.bot.action_registry.submit_action(
                    tag=first_base.tag,
                    action=lambda fb=first_base: fb.train(UnitTypeId.QUEEN),
                    priority=60,
                    source="ravager_rush_train_queen"
                )

        if self.bot.structures(UnitTypeId.ROACHWARREN).amount + self.bot.already_pending(UnitTypeId.ROACHWARREN) > 0:
            extra_condition = self.bot.supply_left <= 1 or (
                    self.bot.units(UnitTypeId.DRONE).amount >= 13 and self.bot.supply_left <= 2)
            self.train_overlord_if_needed(larvae, supply_threshold=2, extra_condition=extra_condition)

        if self.bot.structures(UnitTypeId.ROACHWARREN).ready.exists and \
                self.bot.can_afford(UnitTypeId.ROACH) and \
                larvae.exists and not self.bot.need_air_units:
            larva = larvae.random
            self.bot.action_registry.submit_action(
                tag=larva.tag,
                action=lambda l=larva: l.train(UnitTypeId.ROACH),
                priority=80,
                source="ravager_rush_train_roach"
            )

        # ATTACK
        army_count = self.bot.units(UnitTypeId.ROACH).amount + self.bot.units(UnitTypeId.RAVAGER).amount
        if self.should_attack_main_base(army_count):

            for unit in forces:
                self._ravager_attack_micro(unit, dangerous_structures)

            self.bot.combat_helper.manage_queen_attack()

        elif not self.bot.need_to_attack_main_base:
            await self.bot.combat_helper.find_final_structures(forces=forces,
                                                 army=(self.bot.units(UnitTypeId.ROACH) |
                                                       self.bot.units(UnitTypeId.RAVAGER) |
                                                       self.bot.units(UnitTypeId.OVERLORD)))

        if self.bot.need_to_attack_main_base:
            await self.bot.combat_helper.is_opponents_main_won()
