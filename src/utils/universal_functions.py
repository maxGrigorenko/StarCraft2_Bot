from sc2.ids.effect_id import EffectId
from sc2.ids.unit_typeid import UnitTypeId
from .coordinate_functions import *
from sc2.data import Race, ActionResult
from sc2.ids.ability_id import AbilityId
from src.managers.action_registry import ActionPriority
from sc2.position import Point2
import random


def refresh_unit(self, unit_or_tag):
    if unit_or_tag is None:
        # print('got None')
        return None
    if isinstance(unit_or_tag, int):
        try:
            return self.units.by_tag(unit_or_tag)
        except KeyError:
            # print('KeyError for tag')
            return None
    # If it's a Unit object, refresh it by tag
    try:
        return self.units.by_tag(unit_or_tag.tag)
    except KeyError:
        # print('KeyError for Unit')
        return None


def enemy_dangerous_structures(self):
    if self.enemy_race == Race.Terran:
        return self.enemy_structures(UnitTypeId.BUNKER)
    elif self.enemy_race == Race.Zerg:
        return self.enemy_structures(UnitTypeId.SPINECRAWLER)
    else:
        return self.enemy_structures(UnitTypeId.PHOTONCANNON)


def dangerous_structures_exist(self):
    return (self.enemy_structures(UnitTypeId.SPINECRAWLER).exists or self.enemy_structures(
        UnitTypeId.PHOTONCANNON).exists or self.enemy_structures(UnitTypeId.BUNKER).exists)


def select_target(self):
    if self.enemy_structures.exists:
        return random.choice(self.enemy_structures).position

    return self.enemy_start_locations[0]


def get_locations(self):
    return self.expansion_locations_list


async def base_scout(self, unit, loc_n):
    locations = self.get_locations()
    target = locations[loc_n]
    self.action_registry.submit_action(
        tag=unit.tag,
        action=lambda u=unit, t=target: u.attack(t),
        priority=ActionPriority.LOW,
        source="uf_base_scout"
    )


def is_units_health_max(self):
    for u in self.units(UnitTypeId.DRONE):
        if u.health_max - u.health > 0:
            return False

    return True


def all_flying_enemies(self):
    if len(self.enemy_units) == 0:
        return False

    if self.enemy_units.exists:
        for enemy in self.enemy_units:
            if not enemy.is_flying:
                return False
    return True


def all_known_structures_flying(self):
    if len(self.enemy_structures) == 0:
        return False

    for i in self.enemy_structures:
        if not i.is_flying:
            return False

    return True


def closest_enemy_unit(self, unit):
    closest_unit = self.all_enemy_units[0]
    minimal_distance = 100
    for enemy in self.enemy_units:
        if enemy in self.known_enemy_u:
            distance_now = get_distance(unit.position, enemy.position)
            if distance_now < minimal_distance:
                minimal_distance = distance_now
                closest_unit = enemy

    return closest_unit


def closest_unit(self, units, obj):
    result = units[0]
    minimal = 300
    for unit in units:
        unit = self.refresh_unit(unit)
        if unit is None:
            continue
        d = get_distance(unit.position, obj.position)
        if d < minimal:
            minimal = d
            result = unit
    return result


def sorted_enemy_locations(self):
    locations = self.get_locations()
    enemy_main = self.enemy_start_locations[0]
    sorted_locations = sorted(locations, key=lambda x: get_distance(x, enemy_main))
    return sorted_locations


def air_danger_units(self):
    air_attack_enemy_units = [unit for unit in self.enemy_units if unit.can_attack_air]
    for struct in self.enemy_structures:
        if struct.can_attack_air:
            air_attack_enemy_units.append(struct)
    return air_attack_enemy_units


async def map_scout(self, army):
    locations = self.locations
    idle_massiv = []

    for i in army:
        if i.tag not in self.home_dronny_tags:
            idle_massiv.append(i)

    if len(idle_massiv) >= len(locations):
        for i in range(len(locations)):
            if idle_massiv[i].tag not in self.in_scout_tags:
                await self.base_scout(idle_massiv[i], i)
                self.in_scout_tags.add(idle_massiv[i].tag)

    else:
        for a in army:
            if a.tag not in self.home_dronny_tags:
                dist = get_distance(a.position, locations[self.location_counter])
                if dist < 5:
                    self.location_counter += 1

            for j in army:
                if j.tag not in self.home_dronny_tags and j.type_id != UnitTypeId.OVERLORD:
                    await self.base_scout(j, self.location_counter)


def need_group(self, middle_unit, max_distance, max_middle_group_dist):
    forces = []
    for unit in self.units(UnitTypeId.DRONE) | self.units(UnitTypeId.ZERGLING):
        if unit.tag not in self.home_dronny_tags and unit.tag != middle_unit.tag and unit.tag not in self.wall_breakers_tags:
            forces.append(unit)

    distances = []
    for unit in forces:
        distances.append(get_distance(unit.position, self.enemy_start_locations[0].position))

    amount = sum(distances)
    length = len(distances)

    if length == 0:
        return False

    middle_distance = amount / length

    if middle_distance < 70:
        self.stop_group = True
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

    middle_dist = amount_dist / quantity
    if middle_dist > max_middle_group_dist:
        result = True
    else:
        result = False

    return result


async def group_units(self, middle_unit, max_distance):
    forces = []
    for unit in self.units(UnitTypeId.DRONE) | self.units(UnitTypeId.ZERGLING):
        if unit.tag not in self.home_dronny_tags and unit.tag not in self.wall_breakers_tags:
            forces.append(unit)

    positions = []

    for unit in forces:
        d = get_distance(middle_unit.position, unit.position)
        if d < max_distance:
            positions.append(unit.position)

    x = 0
    y = 0

    for pos in positions:
        x += pos.x
        y += pos.y
    lp = len(positions)

    if lp == 0:
        return

    medium_position = sc2.position.Point2((x / lp, y / lp))

    for unit in forces:
        self.action_registry.submit_action(
            tag=unit.tag,
            action=lambda u=unit, mp=medium_position: u.move(mp),
            priority=ActionPriority.LOW,
            source="uf_group_units"
        )


async def defending(self):
    piece = True

    close_enemies = []
    if len(self.enemy_units) > 0 and not self.is_units_health_max():
        for enemy in self.enemy_units:
            if get_distance(enemy.position, self.start_location) < 15:
                close_enemies.append(enemy)

        enemies_in_attack_amount = len(close_enemies)
        if enemies_in_attack_amount > 0:
            print("Defending")
            piece = False

            if enemies_in_attack_amount <= 3:
                defenders_amount = enemies_in_attack_amount + 1
            elif enemies_in_attack_amount <= 6:
                defenders_amount = enemies_in_attack_amount + 2
            else:
                defenders_amount = int(enemies_in_attack_amount * 1.3) + 1

            if len(self.attack_drones_tags) < defenders_amount:
                for unit in self.units(UnitTypeId.DRONE) | self.units(UnitTypeId.ZERGLING):
                    if unit.health > 5:
                        self.attack_drones_tags.add(unit.tag)
                        if unit.tag in self.drones_on_gas_tags:
                            self.drones_on_gas_tags.discard(unit.tag)
                        if len(self.attack_drones_tags) >= defenders_amount:
                            break

            mineral_field = min(self.mineral_field, key=lambda x: get_distance(x.position, self.start_location))
            for tag in self.attack_drones_tags:
                unit = self.refresh_unit(tag)
                if unit is None:
                    continue

                if unit.tag not in self.in_micro_tags:
                    closest = self.closest_unit(close_enemies, unit)
                    if closest is None:
                        continue
                    target_pos = closest.position

                    if not unit.weapon_ready:
                        self.action_registry.submit_action(
                            tag=unit.tag,
                            action=lambda u=unit, mf=mineral_field: u.gather(mf),
                            priority=ActionPriority.HIGH,
                            source="uf_defence_micro_gather"
                        )

                    else:
                        self.action_registry.submit_action(
                            tag=unit.tag,
                            action=lambda u=unit, t=target_pos: u.attack(t),
                            priority=ActionPriority.NORMAL,
                            source="uf_defending"
                        )

            self.defence = True

        if piece and self.defence:
            self.defence = False
            self.attack_drones_tags.clear()

    if len(close_enemies) == 0 and self.defence:
        self.defence = False
        self.attack_drones_tags.clear()


async def micro_element(self):
    if not self.enemy_units.exists:
        return

    drones = []
    mineral_field = min(self.mineral_field, key=lambda x: get_distance(x.position, self.start_location))

    for drone in self.units(UnitTypeId.DRONE):
        if drone.tag not in self.home_dronny_tags and drone.tag not in self.wall_breakers_tags:
            drones.append(drone)

    for unit in drones:
        fighter = self.closest_enemy_unit(unit)
        if not unit.weapon_ready:
            if unit.tag not in self.in_micro_tags:
                self.in_micro_tags.add(unit.tag)
            self.action_registry.submit_action(
                tag=unit.tag,
                action=lambda u=unit, mf=mineral_field: u.gather(mf),
                priority=ActionPriority.HIGH,
                source="uf_micro_element_gather"
            )
            if unit.tag not in self.go_back_points_tags:
                self.go_back_points_tags.add(unit.tag)

        if unit.tag in self.go_back_points_tags and unit.health > 5:
            if unit.weapon_ready:
                if unit.tag in self.go_back_points_tags:
                    self.go_back_points_tags.discard(unit.tag)
                if unit.tag in self.in_micro_tags:
                    self.in_micro_tags.discard(unit.tag)
                enemy_loc = self.enemy_start_locations[0]
                self.action_registry.submit_action(
                    tag=unit.tag,
                    action=lambda u=unit, t=enemy_loc: u.attack(t),
                    priority=ActionPriority.HIGH,
                    source="uf_micro_element_attack"
                )


async def queen_management(self):
    for queen in self.units(UnitTypeId.QUEEN):
        dist = get_distance(queen.position, self.start_location)
        bases_amount = self.structures(UnitTypeId.HATCHERY).amount + self.structures(
            UnitTypeId.LAIR).amount + self.structures(UnitTypeId.HIVE).amount
        if queen.is_idle and dist < 40:
            if queen.energy >= 25 and bases_amount > 0:
                first_townhall = self.townhalls.first
                self.action_registry.submit_action(
                    tag=queen.tag,
                    action=lambda q=queen, th=first_townhall: q(AbilityId.EFFECT_INJECTLARVA, th),
                    priority=ActionPriority.HIGH,
                    source="uf_queen_management_inject"
                )

        '''
        for second_queen in self.units(UnitTypeId.QUEEN): 
            if (10 > get_distance(queen.position, second_queen.position) > 0) and second_queen.health < second_queen.health_max * 0.6:
                if AbilityId.TRANSFUSION_TRANSFUSION in abilities:
                    queen(AbilityId.TRANSFUSION_TRANSFUSION, second_queen)
                    print("Doing Transfusion")
        '''


def no_units_in_opponent_main(self):
    for unit in self.units(UnitTypeId.DRONE) | self.units(UnitTypeId.ZERGLING) | self.units(UnitTypeId.QUEEN):
        if get_distance(unit.position, self.enemy_start_locations[0]) < 30:
            return False

    return True


def proxy(self):
    for drone in self.units(UnitTypeId.DRONE):
        if get_distance(drone.position, self.start_location) > 100 and self.minerals >= 25:
            print("Building proxy")
            target = self.vespene_geyser.closest_to(drone.position)
            if target is None:
                break
            self.action_registry.submit_action(
                tag=drone.tag,
                action=lambda d=drone, t=target: d.build(UnitTypeId.EXTRACTOR, t),
                priority=ActionPriority.NORMAL,
                source="uf_proxy"
            )
            if drone.tag not in self.building_workers_tags:
                self.building_workers_tags.add(drone.tag)
            break


def remove_idle_drones_tags(self, drones_tags):
    to_remove = []
    for drone_tag in drones_tags:
        drone = self.units.find_by_tag(drone_tag)
        if drone is not None and drone.is_idle:
            to_remove.append(drone_tag)
    for tag in to_remove:
        drones_tags.discard(tag)

    return drones_tags


async def mining_iteration(self):
    bases = self.structures(UnitTypeId.HATCHERY) | self.structures(UnitTypeId.LAIR) | self.structures(
        UnitTypeId.HIVE)
    bases_amount = self.structures(UnitTypeId.HATCHERY).amount + self.structures(
        UnitTypeId.LAIR).amount + self.structures(UnitTypeId.HIVE).amount

    if len(self.drones_on_gas_tags) > 0:
        self.drones_on_gas_tags = self.remove_idle_drones_tags(self.drones_on_gas_tags)
        
    if len(self.attack_drones_tags) > 0:
        self.attack_drones_tags = self.remove_idle_drones_tags(self.attack_drones_tags)

    if self.units(UnitTypeId.DRONE).amount > 0 and bases_amount > 0 and self.mineral_field.amount > 0:

        drones = []
        for drone in self.units(UnitTypeId.DRONE):
            if (drone.tag not in self.wall_breakers_tags) and \
                    (drone.tag not in self.attack_drones_tags) and \
                    (drone.tag not in self.building_workers_tags) and \
                    (drone.tag not in self.drones_on_gas_tags) and \
                    get_distance(drone.position, self.closest_unit(bases, drone).position) < 20:
                drones.append(drone)

        self.mining_drones_tags = {drone.tag for drone in drones}

        try:
            self.refresh_mining_data(drones)  # (self, drones)
            await self.speed_mining()  # (self), imported functions

        except BaseException:
            print("Mining exception")


async def find_final_structures(self, forces, army):
    self.wall_breakers_tags.clear()
    if len(self.enemy_structures) > 0 and not self.all_known_structures_flying():
        for enemy_struct in self.enemy_structures:
            for unit in forces:
                if unit.tag not in self.home_dronny_tags and unit.is_idle:
                    target_pos = enemy_struct.position
                    self.action_registry.submit_action(
                        tag=unit.tag,
                        action=lambda u=unit, t=target_pos: u.attack(t),
                        priority=ActionPriority.NORMAL,
                        source="uf_find_final_structures_attack_struct"
                    )
            self.in_scout_tags.clear()

    elif len(self.enemy_units) > 0 and not self.all_flying_enemies():
        enemy_pos = self.enemy_units[0].position
        for unit in forces:
            if unit.tag not in self.home_dronny_tags:
                self.action_registry.submit_action(
                    tag=unit.tag,
                    action=lambda u=unit, t=enemy_pos: u.attack(t),
                    priority=ActionPriority.NORMAL,
                    source="uf_find_final_structures_attack_unit"
                )
        self.in_scout_tags.clear()

    else:
        await self.map_scout(army)
        if self.enemy_structures.exists and self.units(UnitTypeId.QUEEN).exists:
            for queen in self.units(UnitTypeId.QUEEN):
                if queen.is_idle:
                    enemy_struct = self.enemy_structures[0]
                    self.action_registry.submit_action(
                        tag=queen.tag,
                        action=lambda q=queen, t=enemy_struct: q.attack(t),
                        priority=ActionPriority.NORMAL,
                        source="uf_find_final_structures_queen_attack"
                    )

        if (not self.need_air_units) and (self.all_known_structures_flying()) and (
                not self.units(UnitTypeId.MUTALISK).exists):
            await self.chat_send("Do not try to escape from me!")
            self.need_air_units = True

        if self.units(UnitTypeId.MUTALISK).exists:
            if len(self.enemy_structures) > 0:
                for muta in self.units(UnitTypeId.MUTALISK):
                    if muta.is_idle:
                        enemy_struct = self.enemy_structures[0]
                        self.action_registry.submit_action(
                            tag=muta.tag,
                            action=lambda m=muta, t=enemy_struct: m.attack(t),
                            priority=ActionPriority.NORMAL,
                            source="uf_find_final_structures_muta_attack"
                        )

            else:
                map_w = int(self.game_info.map_size[0])
                map_h = int(self.game_info.map_size[1])
                for unit in forces:
                    if unit.is_idle:
                        rand_point = sc2.position.Point2(
                            [random.randint(0, map_w), random.randint(0, map_h)]
                        )
                        self.action_registry.submit_action(
                            tag=unit.tag,
                            action=lambda u=unit, t=rand_point: u.attack(t),
                            priority=ActionPriority.NORMAL,
                            source="uf_find_final_structures_random_attack"
                        )


async def is_opponents_main_won(self):
    forces = self.units(UnitTypeId.DRONE) | self.units(UnitTypeId.ZERGLING) | self.units(UnitTypeId.ROACH) | self.units(
        UnitTypeId.RAVAGER) | self.units(UnitTypeId.MUTALISK)
    for army_unit in forces:
        dist = get_distance(army_unit.position, self.enemy_start_locations[0])

        if dist < 1:
            if len(self.known_enemy_u) > 0:
                if get_distance(army_unit.position, self.closest_enemy_unit(army_unit).position) > 4:
                    await self.chat_send("We won opponent's main!")
                    self.need_to_attack_main_base = False
                    break

            else:
                await self.chat_send("We won opponent's main!")
                self.need_to_attack_main_base = False
                break


async def macro_element(self):
    first_base = self.townhalls.first
    if self.structures(UnitTypeId.EXTRACTOR).amount + self.already_pending(UnitTypeId.EXTRACTOR) < 2 and len(
            self.mining_drones_tags) > 12:
        if self.can_afford(UnitTypeId.EXTRACTOR):

            dronny = self.refresh_unit(self.dronny_tag)
            if not dronny or dronny is None:
                free_drones = [unit for unit in self.units(UnitTypeId.DRONE) if not unit.is_carrying_resource]
                if not free_drones:
                    return
                dronny = self.closest_unit(free_drones, self.start_location)
                self.dronny_tag = dronny.tag

            if dronny is None:
                return

            if self.can_afford(UnitTypeId.EXTRACTOR):
                home_geysers = self.vespene_geyser.filter(lambda unit: get_distance(self.start_location, unit.position) < 9)
                extractors = self.units(UnitTypeId.EXTRACTOR)
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
                    await self.build(UnitTypeId.EXTRACTOR, target, build_worker=dronny)
                    if dronny.tag not in self.building_workers_tags:
                        self.building_workers_tags.add(dronny.tag)
                    return

    for extractor in self.structures(UnitTypeId.EXTRACTOR):
        if extractor.assigned_harvesters < extractor.ideal_harvesters:
            w = self.workers.closer_than(6, extractor)
            if w.exists:
                drone = w.random
                self.action_registry.submit_action(
                    tag=drone.tag,
                    action=lambda d=drone, e=extractor: d.gather(e),
                    priority=ActionPriority.LOW,
                    source="uf_macro_element_gather_gas"
                )
                if drone.tag not in self.drones_on_gas_tags:
                    self.drones_on_gas_tags.add(drone.tag)

    if self.structures(UnitTypeId.SPAWNINGPOOL).ready.exists:
        if not self.structures(UnitTypeId.LAIR).exists and not self.structures(
                UnitTypeId.HIVE).exists and first_base.is_idle:
            if self.can_afford(UnitTypeId.LAIR):
                self.action_registry.submit_action(
                    tag=first_base.tag,
                    action=lambda fb=first_base: fb.build(UnitTypeId.LAIR),
                    priority=ActionPriority.NORMAL,
                    source="uf_macro_element_build_lair"
                )

    if self.structures(UnitTypeId.LAIR).ready.exists:
        if not (self.structures(UnitTypeId.SPIRE).exists or self.already_pending(UnitTypeId.SPIRE)):
            if self.can_afford(UnitTypeId.SPIRE):
                dronny = self.refresh_unit(self.dronny_tag)
                if dronny is None:
                    free_drones = [unit for unit in self.units(UnitTypeId.DRONE) if not unit.is_carrying_resource
                                   and unit.tag not in self.building_workers_tags]
                    if not free_drones:
                        return
                    dronny = self.closest_unit(free_drones, self.start_location)
                    self.dronny_tag = dronny.tag

                if dronny is None:
                    return

                spawning_pool = self.structures(UnitTypeId.SPAWNINGPOOL)
                print("building spire")
                if spawning_pool.exists:
                    await self.build(UnitTypeId.SPIRE, build_worker=dronny,
                                     near=spawning_pool[0])
                else:
                    await self.build(UnitTypeId.SPIRE, build_worker=dronny,
                                     near=self.start_location)
                if dronny.tag not in self.building_workers_tags:
                    self.building_workers_tags.add(dronny.tag)

    if self.structures(UnitTypeId.SPIRE).ready.exists:
        if self.units(UnitTypeId.LARVA).exists:
            larva = self.units(UnitTypeId.LARVA).random
            if self.can_afford(UnitTypeId.MUTALISK):
                self.action_registry.submit_action(
                    tag=larva.tag,
                    action=lambda l=larva: l.train(UnitTypeId.MUTALISK),
                    priority=ActionPriority.NORMAL,
                    source="uf_macro_element_train_mutalisk"
                )
                if not self.muta_tagged:
                    await self.chat_send(message="Tag:muta", team_only=True)
                    self.muta_tagged = True
                return


def manage_queen_attack(self):
    for queen in self.units(UnitTypeId.QUEEN):
        if queen.is_idle and \
                not (get_distance(queen.position, self.townhalls.first.position) < 8 and queen.energy >= 25):
            if self.enemy_units.exists:
                closest_enemy = self.closest_enemy_unit(self.townhalls.first)
                if closest_enemy is None:
                    continue
                if get_distance(closest_enemy.position, self.townhalls.first.position) < 14 and \
                        get_distance(closest_enemy.position, queen.position) < 20:
                    target_pos = closest_enemy.position
                    self.action_registry.submit_action(
                        tag=queen.tag,
                        action=lambda q=queen, t=target_pos: q.attack(t),
                        priority=ActionPriority.HIGH,
                        source="uf_manage_queen_attack_close"
                    )
                else:
                    enemy_loc = self.enemy_start_locations[0]
                    self.action_registry.submit_action(
                        tag=queen.tag,
                        action=lambda q=queen, t=enemy_loc: q.attack(t),
                        priority=ActionPriority.NORMAL,
                        source="uf_manage_queen_attack_main"
                    )
            else:
                enemy_loc = self.enemy_start_locations[0]
                self.action_registry.submit_action(
                    tag=queen.tag,
                    action=lambda q=queen, t=enemy_loc: q.attack(t),
                    priority=ActionPriority.NORMAL,
                    source="uf_manage_queen_attack_no_enemies"
                )


def find_expand(self):
    main_rump_position = self.two_enemy_ramps[0].bottom_center
    locations = self.sorted_enemy_locations()[1:]
    expand = locations[0]
    for location in locations:
        if get_distance(main_rump_position, location) < get_distance(main_rump_position, expand):
            expand = location
    return expand


def has_expand_ramp(self):
    if not self.expand:
        self.expand = self.find_expand()

    sorted_ramps = sorted(self.game_info.map_ramps,
                          key=lambda x: get_distance(x.top_center, self.expand.position))

    closest_ramp = sorted_ramps[0]
    if closest_ramp == self.two_enemy_ramps[0]:
        closest_ramp = sorted_ramps[1]
    self.two_enemy_ramps[1] = closest_ramp

    ramp_distance = get_distance(self.expand, closest_ramp.top_center)
    print(f"{ramp_distance=}")

    if ramp_distance > 14:
        return False
    return True


def accurate_attack(self, unit, attack_on_way=False, need_additional_attack_command=True):
    close_to_expand_ramp = get_distance(unit.position, self.two_enemy_ramps[1].top_center) < 2
    close_to_main_ramp = get_distance(unit.position, self.two_enemy_ramps[0].top_center) < 2
    if unit.tag not in self.expand_ramp_passed_tags and self.expand_rump_exist:
        target = self.two_enemy_ramps[1].top_center
        if close_to_expand_ramp:
            self.expand_ramp_passed_tags.add(unit.tag)
    elif unit.tag not in self.main_ramp_passed_tags:
        target = self.two_enemy_ramps[0].top_center
        if close_to_main_ramp:
            self.main_ramp_passed_tags.add(unit.tag)
    else:
        target = self.enemy_start_locations[0].position

    close_to_main = get_distance(unit.position, self.enemy_start_locations[0].position) < 3
    if need_additional_attack_command and (attack_on_way or (close_to_expand_ramp and self.expand_rump_exist)
                                           or close_to_main_ramp or close_to_main):
        self.action_registry.submit_action(
            tag=unit.tag,
            action=lambda u=unit, t=target: u.attack(t),
            priority=ActionPriority.NORMAL,
            source="uf_accurate_attack_attack"
        )
    else:
        self.action_registry.submit_action(
            tag=unit.tag,
            action=lambda u=unit, t=target: u.move(t),
            priority=ActionPriority.LOW + 1,
            source="uf_accurate_attack_move"
        )


def closest_unit_dist(self, unit, units):
    d = 1000
    for structure in units:
        d = min(d, get_distance(unit.position, structure.position))
    return d


def dodge_corrosive_bile(self):
    BILE_DODGE_RADIUS = 5.0

    for effect in self.state.effects:
        if effect.id != EffectId.RAVAGERCORROSIVEBILECP:
            continue

        for bile_position in effect.positions:
            bile_point = Point2(bile_position)

            units_in_range = self.units.filter(
                lambda u: u.distance_to(bile_point) <= BILE_DODGE_RADIUS
            )

            for unit in units_in_range:
                tag = unit.tag

                if unit.is_burrowed:
                    self.action_registry.submit_action(
                        tag=tag,
                        action=lambda u=unit: u(AbilityId.BURROWUP),
                        priority=ActionPriority.CRITICAL,
                        source="dodge_corrosive_bile_unburrow"
                    )
                    continue

                retreat_point = go_from_point(unit_position=unit.position,
                                              dangerous_position=bile_position,
                                              dist=2)

                self.action_registry.submit_action(
                    tag=tag,
                    action=lambda u=unit, p=retreat_point: u.move(p),
                    priority=ActionPriority.CRITICAL,
                    source="dodge_corrosive_bile"
                )
