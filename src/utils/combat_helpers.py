from sc2.ids.unit_typeid import UnitTypeId
from sc2.ids.ability_id import AbilityId
from sc2.ids.effect_id import EffectId
from sc2.data import Race
from .coordinate_functions import get_distance, go_from_point
from src.managers.action_registry import ActionPriority
import sc2.position
import random


class CombatHelper:
    """Combat maneuvers, micro-control and grouping."""

    def __init__(self, bot):
        self.bot = bot

    def closest_enemy_unit(self, unit):
        closest = self.bot.all_enemy_units[0]
        min_dist = 100
        for enemy in self.bot.enemy_units:
            if enemy in self.bot.known_enemy_u:
                d = get_distance(unit.position, enemy.position)
                if d < min_dist:
                    min_dist = d
                    closest = enemy
        return closest

    def closest_unit_dist(self, unit, units):
        d = 1000
        for structure in units:
            d = min(d, get_distance(unit.position, structure.position))
        return d

    async def defending(self):
        piece = True
        close_enemies = []
        if len(self.bot.enemy_units) > 0 and not self.bot.unit_helper.is_units_health_max():
            for enemy in self.bot.enemy_units:
                if get_distance(enemy.position, self.bot.start_location) < 15:
                    close_enemies.append(enemy)
            enemies_in_attack = len(close_enemies)
            if enemies_in_attack > 0:
                print("Defending")
                piece = False
                if enemies_in_attack <= 3:
                    defenders = enemies_in_attack + 1
                elif enemies_in_attack <= 6:
                    defenders = enemies_in_attack + 2
                else:
                    defenders = int(enemies_in_attack * 1.3) + 1
                if len(self.bot.attack_drones_tags) < defenders:
                    for unit in self.bot.units(UnitTypeId.DRONE) | self.bot.units(UnitTypeId.ZERGLING):
                        if unit.health > 5:
                            self.bot.attack_drones_tags.append(unit.tag)
                            if unit.tag in self.bot.drones_on_gas_tags:
                                self.bot.drones_on_gas_tags.remove(unit.tag)
                            if len(self.bot.attack_drones_tags) >= defenders:
                                break
                mineral_field = min(self.bot.mineral_field, key=lambda x: get_distance(x.position, self.bot.start_location))
                for tag in self.bot.attack_drones_tags:
                    unit = self.bot.unit_helper.refresh_unit(tag)
                    if unit is None:
                        continue
                    if unit.tag not in self.bot.in_micro_tags:
                        closest = self.bot.unit_helper.closest_unit(close_enemies, unit)
                        if closest is None:
                            continue
                        target_pos = closest.position
                        if not unit.weapon_ready:
                            self.bot.action_registry.submit_action(
                                tag=unit.tag,
                                action=lambda u=unit, mf=mineral_field: u.gather(mf),
                                priority=ActionPriority.HIGH,
                                source="uf_defence_micro_gather"
                            )
                        else:
                            self.bot.action_registry.submit_action(
                                tag=unit.tag,
                                action=lambda u=unit, t=target_pos: u.attack(t),
                                priority=ActionPriority.NORMAL,
                                source="uf_defending"
                            )
                self.bot.defence = True
            if piece and self.bot.defence:
                self.bot.defence = False
                self.bot.attack_drones_tags.clear()
        if len(close_enemies) == 0 and self.bot.defence:
            self.bot.defence = False
            self.bot.attack_drones_tags.clear()

    async def micro_element(self):
        if not self.bot.enemy_units.exists:
            return
        drones = []
        mineral_field = min(self.bot.mineral_field, key=lambda x: get_distance(x.position, self.bot.start_location))
        for drone in self.bot.units(UnitTypeId.DRONE):
            if drone.tag not in self.bot.home_dronny_tags and drone.tag not in self.bot.wall_breakers_tags:
                drones.append(drone)
        for unit in drones:
            fighter = self.closest_enemy_unit(unit)
            if not unit.weapon_ready:
                if unit.tag not in self.bot.in_micro_tags:
                    self.bot.in_micro_tags.append(unit.tag)
                self.bot.action_registry.submit_action(
                    tag=unit.tag,
                    action=lambda u=unit, mf=mineral_field: u.gather(mf),
                    priority=ActionPriority.HIGH,
                    source="uf_micro_element_gather"
                )
                if unit.tag not in self.bot.go_back_points_tags:
                    self.bot.go_back_points_tags.append(unit.tag)
            if unit.tag in self.bot.go_back_points_tags and unit.health > 5:
                if unit.weapon_ready:
                    if unit.tag in self.bot.go_back_points_tags:
                        self.bot.go_back_points_tags.remove(unit.tag)
                    if unit.tag in self.bot.in_micro_tags:
                        self.bot.in_micro_tags.remove(unit.tag)
                    enemy_loc = self.bot.enemy_start_locations[0]
                    self.bot.action_registry.submit_action(
                        tag=unit.tag,
                        action=lambda u=unit, t=enemy_loc: u.attack(t),
                        priority=ActionPriority.HIGH,
                        source="uf_micro_element_attack"
                    )

    async def queen_management(self):
        for queen in self.bot.units(UnitTypeId.QUEEN):
            dist = get_distance(queen.position, self.bot.start_location)
            bases_amount = self.bot.structures(UnitTypeId.HATCHERY).amount + self.bot.structures(
                UnitTypeId.LAIR).amount + self.bot.structures(UnitTypeId.HIVE).amount
            if queen.is_idle and dist < 40:
                if queen.energy >= 25 and bases_amount > 0:
                    first_townhall = self.bot.townhalls.first
                    self.bot.action_registry.submit_action(
                        tag=queen.tag,
                        action=lambda q=queen, th=first_townhall: q(AbilityId.EFFECT_INJECTLARVA, th),
                        priority=ActionPriority.HIGH,
                        source="uf_queen_management_inject"
                    )

    def manage_queen_attack(self):
        for queen in self.bot.units(UnitTypeId.QUEEN):
            if queen.is_idle and \
                    not (get_distance(queen.position, self.bot.townhalls.first.position) < 8 and queen.energy >= 25):
                if self.bot.enemy_units.exists:
                    closest_enemy = self.closest_enemy_unit(self.bot.townhalls.first)
                    if closest_enemy is None:
                        continue
                    if get_distance(closest_enemy.position, self.bot.townhalls.first.position) < 14 and \
                            get_distance(closest_enemy.position, queen.position) < 20:
                        target_pos = closest_enemy.position
                        self.bot.action_registry.submit_action(
                            tag=queen.tag,
                            action=lambda q=queen, t=target_pos: q.attack(t),
                            priority=ActionPriority.HIGH,
                            source="uf_manage_queen_attack_close"
                        )
                    else:
                        enemy_loc = self.bot.enemy_start_locations[0]
                        self.bot.action_registry.submit_action(
                            tag=queen.tag,
                            action=lambda q=queen, t=enemy_loc: q.attack(t),
                            priority=ActionPriority.NORMAL,
                            source="uf_manage_queen_attack_main"
                        )
                else:
                    enemy_loc = self.bot.enemy_start_locations[0]
                    self.bot.action_registry.submit_action(
                        tag=queen.tag,
                        action=lambda q=queen, t=enemy_loc: q.attack(t),
                        priority=ActionPriority.NORMAL,
                        source="uf_manage_queen_attack_no_enemies"
                    )

    def need_group(self, middle_unit, max_distance, max_middle_group_dist):
        forces = []
        for unit in self.bot.units(UnitTypeId.DRONE) | self.bot.units(UnitTypeId.ZERGLING):
            if unit.tag not in self.bot.home_dronny_tags and unit.tag != middle_unit.tag and unit.tag not in self.bot.wall_breakers_tags:
                forces.append(unit)
        distances = []
        for unit in forces:
            distances.append(get_distance(unit.position, self.bot.enemy_start_locations[0].position))
        if len(distances) == 0:
            return False
        middle_distance = sum(distances) / len(distances)
        if middle_distance < 70:
            self.bot.stop_group = True
            return False
        elif middle_distance > 80:
            return False
        amount_dist = 0
        quantity = 0
        for unit in forces:
            d = get_distance(middle_unit.position, unit.position)
            if d < max_distance:
                amount_dist += d
                quantity += 1
        if quantity < 3:
            return False
        return (amount_dist / quantity) > max_middle_group_dist

    async def group_units(self, middle_unit, max_distance):
        forces = []
        for unit in self.bot.units(UnitTypeId.DRONE) | self.bot.units(UnitTypeId.ZERGLING):
            if unit.tag not in self.bot.home_dronny_tags and unit.tag not in self.bot.wall_breakers_tags:
                forces.append(unit)
        positions = []
        for unit in forces:
            d = get_distance(middle_unit.position, unit.position)
            if d < max_distance:
                positions.append(unit.position)
        if len(positions) == 0:
            return
        x = sum(p.x for p in positions) / len(positions)
        y = sum(p.y for p in positions) / len(positions)
        medium_position = sc2.position.Point2((x, y))
        for unit in forces:
            self.bot.action_registry.submit_action(
                tag=unit.tag,
                action=lambda u=unit, mp=medium_position: u.move(mp),
                priority=ActionPriority.LOW,
                source="uf_group_units"
            )

    def accurate_attack(self, unit, attack_on_way=False, need_additional_attack_command=True):
        close_to_expand_ramp = get_distance(unit.position, self.bot.two_enemy_ramps[1].top_center) < 2
        close_to_main_ramp = get_distance(unit.position, self.bot.two_enemy_ramps[0].top_center) < 2
        if unit.tag not in self.bot.expand_ramp_passed_tags and self.bot.expand_rump_exist:
            target = self.bot.two_enemy_ramps[1].top_center
            if close_to_expand_ramp:
                self.bot.expand_ramp_passed_tags.append(unit.tag)
        elif unit.tag not in self.bot.main_ramp_passed_tags:
            target = self.bot.two_enemy_ramps[0].top_center
            if close_to_main_ramp:
                self.bot.main_ramp_passed_tags.append(unit.tag)
        else:
            target = self.bot.enemy_start_locations[0].position
        close_to_main = get_distance(unit.position, self.bot.enemy_start_locations[0].position) < 3
        if need_additional_attack_command and (attack_on_way or (close_to_expand_ramp and self.bot.expand_rump_exist)
                                               or close_to_main_ramp or close_to_main):
            self.bot.action_registry.submit_action(
                tag=unit.tag,
                action=lambda u=unit, t=target: u.attack(t),
                priority=ActionPriority.NORMAL,
                source="uf_accurate_attack_attack"
            )
        else:
            self.bot.action_registry.submit_action(
                tag=unit.tag,
                action=lambda u=unit, t=target: u.move(t),
                priority=ActionPriority.LOW + 1,
                source="uf_accurate_attack_move"
            )

    def dodge_corrosive_bile(self):
        BILE_DODGE_RADIUS = 5.0
        for effect in self.bot.state.effects:
            if effect.id != EffectId.RAVAGERCORROSIVEBILECP:
                continue
            for bile_pos in effect.positions:
                bile_point = sc2.position.Point2(bile_pos)
                units_in_range = self.bot.units.filter(
                    lambda u: u.distance_to(bile_point) <= BILE_DODGE_RADIUS
                )
                for unit in units_in_range:
                    tag = unit.tag
                    if unit.is_burrowed:
                        self.bot.action_registry.submit_action(
                            tag=tag,
                            action=lambda u=unit: u(AbilityId.BURROWUP),
                            priority=ActionPriority.CRITICAL,
                            source="dodge_corrosive_bile_unburrow"
                        )
                        continue
                    retreat_point = go_from_point(unit_position=unit.position,
                                                  dangerous_position=bile_point,
                                                  dist=2)
                    self.bot.action_registry.submit_action(
                        tag=tag,
                        action=lambda u=unit, p=retreat_point: u.move(p),
                        priority=ActionPriority.CRITICAL,
                        source="dodge_corrosive_bile"
                    )

    async def is_opponents_main_won(self):
        forces = self.bot.units(UnitTypeId.DRONE) | self.bot.units(UnitTypeId.ZERGLING) | self.bot.units(
            UnitTypeId.ROACH) | self.bot.units(UnitTypeId.RAVAGER) | self.bot.units(UnitTypeId.MUTALISK)
        for army_unit in forces:
            dist = get_distance(army_unit.position, self.bot.enemy_start_locations[0])
            if dist < 1:
                if len(self.bot.known_enemy_u) > 0:
                    if get_distance(army_unit.position, self.closest_enemy_unit(army_unit).position) > 4:
                        await self.bot.chat_send("We won opponent's main!")
                        self.bot.need_to_attack_main_base = False
                        break
                else:
                    await self.bot.chat_send("We won opponent's main!")
                    self.bot.need_to_attack_main_base = False
                    break

    async def find_final_structures(self, forces, army):
        self.bot.wall_breakers_tags.clear()
        if len(self.bot.enemy_structures) > 0 and not self.bot.unit_helper.all_known_structures_flying():
            for enemy_struct in self.bot.enemy_structures:
                for unit in forces:
                    if unit.tag not in self.bot.home_dronny_tags and unit.is_idle:
                        target_pos = enemy_struct.position
                        self.bot.action_registry.submit_action(
                            tag=unit.tag,
                            action=lambda u=unit, t=target_pos: u.attack(t),
                            priority=ActionPriority.NORMAL,
                            source="uf_find_final_structures_attack_struct"
                        )
            self.bot.in_scout_tags.clear()
        elif len(self.bot.enemy_units) > 0 and not self.bot.unit_helper.all_flying_enemies():
            enemy_pos = self.bot.enemy_units[0].position
            for unit in forces:
                if unit.tag not in self.bot.home_dronny_tags:
                    self.bot.action_registry.submit_action(
                        tag=unit.tag,
                        action=lambda u=unit, t=enemy_pos: u.attack(t),
                        priority=ActionPriority.NORMAL,
                        source="uf_find_final_structures_attack_unit"
                    )
            self.bot.in_scout_tags.clear()
        else:
            await self.bot.scouting_helper.map_scout(army)
            if self.bot.enemy_structures.exists and self.bot.units(UnitTypeId.QUEEN).exists:
                for queen in self.bot.units(UnitTypeId.QUEEN):
                    if queen.is_idle:
                        enemy_struct = self.bot.enemy_structures[0]
                        self.bot.action_registry.submit_action(
                            tag=queen.tag,
                            action=lambda q=queen, t=enemy_struct: q.attack(t),
                            priority=ActionPriority.NORMAL,
                            source="uf_find_final_structures_queen_attack"
                        )
            if (not self.bot.need_air_units) and self.bot.unit_helper.all_known_structures_flying() and (
                    not self.bot.units(UnitTypeId.MUTALISK).exists):
                await self.bot.chat_send("Do not try to escape from me!")
                self.bot.need_air_units = True
            if self.bot.units(UnitTypeId.MUTALISK).exists:
                if len(self.bot.enemy_structures) > 0:
                    for muta in self.bot.units(UnitTypeId.MUTALISK):
                        if muta.is_idle:
                            enemy_struct = self.bot.enemy_structures[0]
                            self.bot.action_registry.submit_action(
                                tag=muta.tag,
                                action=lambda m=muta, t=enemy_struct: m.attack(t),
                                priority=ActionPriority.NORMAL,
                                source="uf_find_final_structures_muta_attack"
                            )
                else:
                    map_w = int(self.bot.game_info.map_size[0])
                    map_h = int(self.bot.game_info.map_size[1])
                    for unit in forces:
                        if unit.is_idle:
                            rand_point = sc2.position.Point2(
                                [random.randint(0, map_w), random.randint(0, map_h)]
                            )
                            self.bot.action_registry.submit_action(
                                tag=unit.tag,
                                action=lambda u=unit, t=rand_point: u.attack(t),
                                priority=ActionPriority.NORMAL,
                                source="uf_find_final_structures_random_attack"
                            )
