from sc2.ids.unit_typeid import UnitTypeId
from src.managers.action_registry import ActionPriority
from src.utils.coordinate_functions import get_distance


class BaseStrategy:
    """Common building blocks shared between rush strategies (roach, ravager, zergling-drone)."""

    def __init__(self, bot):
        self.bot = bot

    def dangerous_structures(self):
        return (self.bot.enemy_structures(UnitTypeId.PHOTONCANNON) |
                self.bot.enemy_structures(UnitTypeId.BUNKER) |
                self.bot.enemy_structures(UnitTypeId.SPINECRAWLER))

    def should_attack_main_base(self, army_count):
        """Return True if there are army units or opponent main is known and time conditions are met."""
        return (army_count > 0 or (
                not self.bot.unit_helper.no_units_in_opponent_main() and self.bot.time > 100)
                ) and self.bot.need_to_attack_main_base

    def find_dronny(self):
        """Get current building-drone unit from bot.dronny_tag, or pick a new one closest to enemy start."""
        dronny = self.bot.units.find_by_tag(self.bot.dronny_tag) if self.bot.dronny_tag else None
        if not dronny:
            drones_without_minerals = [unit for unit in self.bot.units(UnitTypeId.DRONE)
                                        if not unit.is_carrying_resource]
            if len(drones_without_minerals) >= 1:
                chosen = self.bot.unit_helper.closest_unit(drones_without_minerals, self.bot.enemy_start_locations[0])
                self.bot.dronny_tag = chosen.tag if chosen else None
                dronny = chosen
        return dronny

    def mark_building_worker(self, tag):
        if tag not in self.bot.building_workers_tags:
            self.bot.building_workers_tags.append(tag)

    def emergency_attack_no_townhalls(self, forces):
        """When no townhalls left, send everything to attack the enemy start location.

        Returns True if the emergency branch was triggered (caller should return afterwards)."""
        if self.bot.townhalls.exists:
            return False
        for unit in self.bot.units(UnitTypeId.QUEEN) | forces:
            self.bot.action_registry.submit_action(
                tag=unit.tag,
                action=lambda u=unit, t=self.bot.enemy_start_locations[0]: u.attack(t),
                priority=ActionPriority.NORMAL,
                source="base_strategy_emergency_attack"
            )
        return True

    def check_main_base_health(self):
        """Returns True if the first base is critically low and proxy handling was triggered."""
        first_base = self.bot.townhalls.first
        if first_base.health < 401:
            self.bot.unit_helper.proxy()
            return True
        return False

    def update_known_enemies(self):
        """Refresh the known_enemy_u list: drop stale entries, add newly visible ground units."""
        for unit_in_known in list(self.bot.known_enemy_u):
            if unit_in_known not in self.bot.enemy_units:
                self.bot.known_enemy_u.remove(unit_in_known)

        if self.bot.enemy_units.exists:
            for enemy_unit in self.bot.enemy_units:
                if (enemy_unit not in self.bot.known_enemy_u) and (
                        enemy_unit not in self.bot.enemy_structures) and (
                        enemy_unit not in self.bot.enemy_units(UnitTypeId.LARVA)) and (
                        not enemy_unit.is_flying):
                    self.bot.known_enemy_u.append(enemy_unit)

    def build_spawning_pool(self, dronny, first_base, move_priority=ActionPriority.LOW,
                             build_priority=ActionPriority.HIGH, distance=8):
        """Common spawning pool build logic used by rush strategies.

        Returns the position where the pool was ordered to be built (or None)."""
        if self.bot.structures(UnitTypeId.SPAWNINGPOOL).amount + self.bot.already_pending(
                UnitTypeId.SPAWNINGPOOL) != 0:
            return None

        if self.bot.time < 70 and dronny is not None:
            if 200 > self.bot.minerals > 140 and not dronny.is_carrying_resource and get_distance(
                    dronny.position, self.bot.start_location) < distance:
                self.bot.action_registry.submit_action(
                    tag=dronny.tag,
                    action=lambda d=dronny, t=self.bot.enemy_start_locations[0]: d.move(t),
                    priority=move_priority,
                    source="base_strategy_pool_move_to_enemy"
                )
                self.mark_building_worker(dronny.tag)

            elif self.bot.can_afford(UnitTypeId.SPAWNINGPOOL):
                pool_position = dronny.position
                self.bot.action_registry.submit_action(
                    tag=dronny.tag,
                    action=lambda d=dronny, tid=UnitTypeId.SPAWNINGPOOL, p=pool_position: d.build(tid, p),
                    priority=build_priority,
                    source="base_strategy_pool_build"
                )
                self.mark_building_worker(dronny.tag)
                return pool_position

            elif get_distance(dronny.position, self.bot.start_location) >= distance and self.bot.minerals > 160:
                self.bot.action_registry.submit_action(
                    tag=dronny.tag,
                    action=lambda d=dronny: d.move(d.position),
                    priority=move_priority,
                    source="base_strategy_pool_stay"
                )

        elif self.bot.minerals >= 200 and self.bot.units(UnitTypeId.DRONE).amount > 0 and dronny is not None:
            self.bot.action_registry.submit_action(
                tag=dronny.tag,
                action=lambda d=dronny, tid=UnitTypeId.SPAWNINGPOOL, p=first_base.position: d.build(tid, p),
                priority=build_priority,
                source="base_strategy_pool_build_late"
            )
            self.mark_building_worker(dronny.tag)

        return None

    def build_first_extractor(self, dronny, priority=ActionPriority.HIGH):
        if not (self.bot.structures(UnitTypeId.SPAWNINGPOOL).amount >= 1 and
                (self.bot.structures(UnitTypeId.EXTRACTOR).amount +
                 self.bot.already_pending(UnitTypeId.EXTRACTOR) == 0)):
            return
        if self.bot.can_afford(UnitTypeId.EXTRACTOR) and dronny is not None:
            target = self.bot.vespene_geyser.closest_to(dronny.position)
            self.bot.action_registry.submit_action(
                tag=dronny.tag,
                action=lambda d=dronny, t=target: d.build(UnitTypeId.EXTRACTOR, t),
                priority=priority,
                source="base_strategy_build_extractor"
            )
            self.mark_building_worker(dronny.tag)

    def assign_gas_gatherers(self):
        for extractor in self.bot.structures(UnitTypeId.EXTRACTOR):
            if extractor.assigned_harvesters < extractor.ideal_harvesters and \
                    self.bot.structures(UnitTypeId.EXTRACTOR).ready.exists and not self.bot.defence:
                w = self.bot.workers.closer_than(6, extractor)
                drones_without_minerals = [unit for unit in w
                                            if not unit.is_carrying_resource
                                            and unit.tag != self.bot.dronny_tag
                                            and unit.tag not in self.bot.building_workers_tags]
                if len(drones_without_minerals) > 0:
                    drone = drones_without_minerals[0]
                    self.bot.action_registry.submit_action(
                        tag=drone.tag,
                        action=lambda d=drone, e=extractor: d.gather(e),
                        priority=ActionPriority.NORMAL,
                        source="base_strategy_gather_gas"
                    )
                    if drone.tag not in self.bot.drones_on_gas_tags:
                        self.bot.drones_on_gas_tags.append(drone.tag)

    def train_overlord_if_needed(self, larvae, supply_threshold, extra_condition=True):
        """Common overlord training trigger."""
        if self.bot.supply_left <= supply_threshold and extra_condition and \
                not self.bot.already_pending(UnitTypeId.OVERLORD):
            if self.bot.can_afford(UnitTypeId.OVERLORD) and larvae.exists:
                larva = larvae.random
                self.bot.action_registry.submit_action(
                    tag=larva.tag,
                    action=lambda l=larva: l.train(UnitTypeId.OVERLORD),
                    priority=ActionPriority.HIGH,
                    source="base_strategy_train_overlord"
                )
                return True
        return False
