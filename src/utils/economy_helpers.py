from sc2.ids.unit_typeid import UnitTypeId
from .coordinate_functions import get_distance
from src.managers.action_registry import ActionPriority
from .speed_mining import refresh_mining_data, assign_mining_positions, speed_mining, \
    check_mineral_fields_near_base, is_hatchery_for_mining


class EconomyHelper:
    """Macro economy: mining, extractors, switching to air units."""

    def __init__(self, bot):
        self.bot = bot

    async def mining_iteration(self):
        bases = self.bot.structures(UnitTypeId.HATCHERY) | self.bot.structures(UnitTypeId.LAIR) | self.bot.structures(
            UnitTypeId.HIVE)
        bases_amount = self.bot.structures(UnitTypeId.HATCHERY).amount + self.bot.structures(
            UnitTypeId.LAIR).amount + self.bot.structures(UnitTypeId.HIVE).amount

        if len(self.bot.drones_on_gas_tags) > 0:
            self.bot.drones_on_gas_tags = self.bot.unit_helper.remove_idle_drones_tags(self.bot.drones_on_gas_tags)

        if len(self.bot.attack_drones_tags) > 0:
            self.bot.attack_drones_tags = self.bot.unit_helper.remove_idle_drones_tags(self.bot.attack_drones_tags)

        if self.bot.units(UnitTypeId.DRONE).amount > 0 and bases_amount > 0 and self.bot.mineral_field.amount > 0:
            drones = []
            for drone in self.bot.units(UnitTypeId.DRONE):
                if (drone.tag not in self.bot.wall_breakers_tags) and \
                        (drone.tag not in self.bot.attack_drones_tags) and \
                        (drone.tag not in self.bot.building_workers_tags) and \
                        (drone.tag not in self.bot.drones_on_gas_tags) and \
                        get_distance(drone.position, self.bot.unit_helper.closest_unit(bases, drone).position) < 20:
                    drones.append(drone)

            self.bot.mining_drones_tags = [drone.tag for drone in drones]

            try:
                refresh_mining_data(self.bot, drones)   # pass bot to speed_mining module
                await speed_mining(self.bot)
            except BaseException as e:
                print(f"Mining exception: {e}")

    async def macro_element(self):
        first_base = self.bot.townhalls.first
        if self.bot.structures(UnitTypeId.EXTRACTOR).amount + self.bot.already_pending(UnitTypeId.EXTRACTOR) < 2 and len(
                self.bot.mining_drones_tags) > 12:
            if self.bot.can_afford(UnitTypeId.EXTRACTOR):
                dronny = self.bot.unit_helper.refresh_unit(self.bot.dronny_tag)
                if not dronny or dronny is None:
                    free_drones = [unit for unit in self.bot.units(UnitTypeId.DRONE) if not unit.is_carrying_resource]
                    if not free_drones:
                        return
                    dronny = self.bot.unit_helper.closest_unit(free_drones, self.bot.start_location)
                    self.bot.dronny_tag = dronny.tag

                if dronny is None:
                    return

                if self.bot.can_afford(UnitTypeId.EXTRACTOR):
                    home_geysers = self.bot.vespene_geyser.filter(lambda unit: get_distance(self.bot.start_location, unit.position) < 9)
                    extractors = self.bot.units(UnitTypeId.EXTRACTOR)
                    if not extractors.exists:
                        without_extractor = home_geysers
                    else:
                        without_extractor = home_geysers.filter(lambda g: get_distance(g, extractors.closest_to(g.position)) > 0.5)

                    if len(without_extractor) == 0:
                        print("No extractors found")
                        return

                    target = without_extractor[0]
                    if target is not None:
                        print("building second extractor")
                        await self.bot.build(UnitTypeId.EXTRACTOR, target, build_worker=dronny)
                        if dronny.tag not in self.bot.building_workers_tags:
                            self.bot.building_workers_tags.append(dronny.tag)
                        return

        for extractor in self.bot.structures(UnitTypeId.EXTRACTOR):
            if extractor.assigned_harvesters < extractor.ideal_harvesters:
                w = self.bot.workers.closer_than(6, extractor)
                if w.exists:
                    drone = w.random
                    self.bot.action_registry.submit_action(
                        tag=drone.tag,
                        action=lambda d=drone, e=extractor: d.gather(e),
                        priority=ActionPriority.LOW,
                        source="uf_macro_element_gather_gas"
                    )
                    if drone.tag not in self.bot.drones_on_gas_tags:
                        self.bot.drones_on_gas_tags.append(drone.tag)

        if self.bot.structures(UnitTypeId.SPAWNINGPOOL).ready.exists:
            if not self.bot.structures(UnitTypeId.LAIR).exists and not self.bot.structures(
                    UnitTypeId.HIVE).exists and first_base.is_idle:
                if self.bot.can_afford(UnitTypeId.LAIR):
                    self.bot.action_registry.submit_action(
                        tag=first_base.tag,
                        action=lambda fb=first_base: fb.build(UnitTypeId.LAIR),
                        priority=ActionPriority.NORMAL,
                        source="uf_macro_element_build_lair"
                    )

        if self.bot.structures(UnitTypeId.LAIR).ready.exists:
            if not (self.bot.structures(UnitTypeId.SPIRE).exists or self.bot.already_pending(UnitTypeId.SPIRE)):
                if self.bot.can_afford(UnitTypeId.SPIRE):
                    dronny = self.bot.unit_helper.refresh_unit(self.bot.dronny_tag)
                    if dronny is None:
                        free_drones = [unit for unit in self.bot.units(UnitTypeId.DRONE) if not unit.is_carrying_resource
                                       and unit.tag not in self.bot.building_workers_tags]
                        if not free_drones:
                            return
                        dronny = self.bot.unit_helper.closest_unit(free_drones, self.bot.start_location)
                        self.bot.dronny_tag = dronny.tag

                    if dronny is None:
                        return

                    spawning_pool = self.bot.structures(UnitTypeId.SPAWNINGPOOL)
                    print("building spire")
                    if spawning_pool.exists:
                        await self.bot.build(UnitTypeId.SPIRE, build_worker=dronny,
                                             near=spawning_pool[0])
                    else:
                        await self.bot.build(UnitTypeId.SPIRE, build_worker=dronny,
                                             near=self.bot.start_location)
                    if dronny.tag not in self.bot.building_workers_tags:
                        self.bot.building_workers_tags.append(dronny.tag)

        if self.bot.structures(UnitTypeId.SPIRE).ready.exists:
            if self.bot.units(UnitTypeId.LARVA).exists:
                larva = self.bot.units(UnitTypeId.LARVA).random
                if self.bot.can_afford(UnitTypeId.MUTALISK):
                    self.bot.action_registry.submit_action(
                        tag=larva.tag,
                        action=lambda l=larva: l.train(UnitTypeId.MUTALISK),
                        priority=ActionPriority.NORMAL,
                        source="uf_macro_element_train_mutalisk"
                    )
                    if not self.bot.muta_tagged:
                        await self.bot.chat_send(message="Tag:muta", team_only=True)
                        self.bot.muta_tagged = True
                    return
