from sc2.ids.unit_typeid import UnitTypeId
from coordinate_functions import *
from sc2.data import Race, ActionResult
from sc2.ids.ability_id import AbilityId
import random


def refresh_unit(self, unit):
    for u in self.all_own_units:
        if u == unit:
            return u


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
    result = []
    dr = list(self.expansion_locations.items())
    for i in range(len(dr)):
        result.append(dr[i][0])

    return result


async def base_scout(self, unit, loc_n):
    locations = self.get_locations()
    unit.attack(locations[loc_n])


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
        d = get_distance(unit.position, obj.position)
        if d < minimal:
            minimal = d
            result = unit
    return result


def enemy_locations(self):
    itog_locations = []
    dictionary = {}
    locations = self.get_locations()
    enemy_main = self.enemy_start_locations[0]
    for location in locations:
        dist = get_distance(location, enemy_main)
        dictionary.update({location: dist})

    distances = sorted(list(dictionary.values()))

    for i in distances:
        for j in dictionary.keys():
            if dictionary[j] == i and j not in itog_locations:
                itog_locations.append(j)

    return itog_locations


async def overlord_management(self):
    if len(self.busy_overlords) < len(self.get_locations()) - 2:
        for overlord in self.units(UnitTypeId.OVERLORD):
            if overlord not in self.busy_overlords:

                if self.enemy_race == Race.Terran:
                    overlord.move(self.enemy_locations()[len(self.busy_overlords) + 1])
                else:
                    overlord.move(self.enemy_locations()[len(self.busy_overlords)])

                self.busy_overlords.append(overlord)


async def map_scout(self, army):
    locations = self.locations
    idle_massiv = []

    for i in army:
        if i not in self.home_dronny:
            idle_massiv.append(i)

    if len(idle_massiv) >= len(locations):
        for i in range(len(locations)):
            if idle_massiv[i] not in self.in_scout:
                await self.base_scout(idle_massiv[i], i)
                self.in_scout.append(idle_massiv[i])

    else:
        for a in army:
            if a not in self.home_dronny:
                dist = get_distance(a.position, locations[self.location_counter])
                if dist < 5:
                    self.location_counter += 1

            for j in army:
                if j not in self.home_dronny and j not in self.units(UnitTypeId.OVERLORD):
                    await self.base_scout(j, self.location_counter)


def need_group(self, middle_unit, max_distance, max_middle_group_dist):
    forces = []
    for unit in self.units(UnitTypeId.DRONE) | self.units(UnitTypeId.ZERGLING):

        if unit not in self.home_dronny and unit != middle_unit and unit not in self.wall_breakers:
            forces.append(unit)

    distances = []
    for unit in forces:
        distances.append(get_distance(unit.position, self.enemy_start_locations[0].position))

    amount = sum(distances)
    length = len(distances)
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
        if unit not in self.home_dronny and unit not in self.wall_breakers:
            forces.append(unit)

    positions = []

    for unit in forces:
        d = get_distance(middle_unit.position, unit.position)
        if d < max_distance:
            positions.append(unit.position)

    x = 0
    y = 0

    for pos in positions:
        x += pos.position[0]
        y += pos.position[1]
    lp = len(positions)

    medium_position = [x / lp, y / lp]
    medium_position = sc2.position.Point2(medium_position)

    for unit in forces:
        unit.move(medium_position)


async def defending(self):
    piece = True

    if len(self.enemy_units) > 0:
        for enemy in self.enemy_units:
            if get_distance(enemy.position, self.start_location) < 6 and not self.is_units_health_max():
                print("Defending")
                piece = False
                for unit in self.units(UnitTypeId.DRONE) | self.units(UnitTypeId.ZERGLING):
                    unit.attack(self.enemy_start_locations[0])

                self.defence = True
            break

        if piece and self.defence:
            self.defence = False
            await self.distribute_workers()

    if len(self.enemy_units) == 0 and self.defence:
        await self.distribute_workers()
        self.defence = False


async def micro_element(self):
    if self.is_units_health_max() or not self.enemy_units.exists:
        return

    drones = []

    for drone in self.units(UnitTypeId.DRONE):
        if drone not in self.home_dronny and drone not in self.wall_breakers:
            drones.append(drone)

    back_distance = 1

    for unit in drones:
        fighter = self.closest_enemy_unit(unit)
        if int(unit.health) in [1, 2, 3, 4, 5, 11, 12, 13, 14, 15, 30, 31, 32, 33, 34]:
            if get_distance(unit.position, fighter.position) <= back_distance:
                self.in_micro.append(unit)
                unit.gather(self.mineral_field[10])  # mineral field must be not at the enemy`s base
                # print("Moving unit out", get_distance(unit.position, fighter.position))
                self.go_back_points.append(unit)

        if unit in self.go_back_points:
            fighter_pos = fighter.position
            if get_distance(unit.position, fighter_pos) > back_distance - 0.05:
                self.go_back_points.remove(unit)
                self.in_micro.remove(unit)
                # print("Unit back", get_distance(unit.position, fighter_pos))
                unit.attack(self.enemy_start_locations[0])


async def queen_management(self):
    for queen in self.units(UnitTypeId.QUEEN):
        dist = get_distance(queen.position, self.start_location)

        if queen.is_idle and dist < 40:
            if queen.energy >= 25 and self.structures(UnitTypeId.HATCHERY).amount > 0:
                queen(AbilityId.EFFECT_INJECTLARVA, self.townhalls.first)

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
            drone.build(UnitTypeId.EXTRACTOR, target)
            if drone not in self.building_workers:
                self.building_workers.append(drone)
            break


async def mining_iteration(self):
    bases = self.structures(UnitTypeId.HATCHERY) | self.structures(UnitTypeId.LAIR) | self.structures(
        UnitTypeId.HIVE)
    bases_amount = self.structures(UnitTypeId.HATCHERY).amount + self.structures(
        UnitTypeId.LAIR).amount + self.structures(UnitTypeId.HIVE).amount

    if self.units(UnitTypeId.DRONE).amount > 0 and bases_amount > 0 and self.mineral_field.amount > 0:

        drones = []
        for drone in self.units(UnitTypeId.DRONE):

            if (drone not in self.wall_breakers) and\
                    (drone not in self.attack_drones) and\
                    (drone not in self.building_workers) and\
                    (drone not in self.drones_on_gas) and\
                    get_distance(drone.position, self.closest_unit(bases, drone).position) < 20:
                drones.append(drone)

        self.mining_drones = drones

        try:
            self.refresh_mining_data(drones)  # (self, drones)
            await self.speed_mining()  # (self), imported functions

        except BaseException:
            print("Mining exception")

    # if self.state.game_loop % (22.4 * 5) == 0:
    #    logger.info(f"{self.time_formatted} Mined a total of {int(self.state.score.collected_minerals)} minerals")

    # if iteration % 30 == 0:
    #   print(f"\n{len(drones)} drones:\n{self.mining_mineral_data}\n{self.mining_hatchery_data}\n")


async def find_final_structures(self, forces, army):
    self.wall_breakers = []
    # print("Now, we don't need to attack enemies main")
    if len(self.enemy_structures) > 0 and not self.all_known_structures_flying():
        for enemy_struct in self.enemy_structures:
            for unit in forces:
                if unit not in self.home_dronny and unit.is_idle:
                    unit.attack(enemy_struct.position)
            self.in_scout = []

    elif len(self.enemy_units) > 0 and not self.all_flying_enemies():
        for unit in forces:
            if unit not in self.home_dronny:
                unit.attack(self.enemy_units[0].position)
        self.in_scout = []

    else:
        await self.map_scout(army)
        if self.enemy_structures.exists and self.units(UnitTypeId.QUEEN).exists:
            for queen in self.units(UnitTypeId.QUEEN):
                if queen.is_idle:
                    queen.attack(self.enemy_structures[0])

        if (not self.need_air_units) and (self.all_known_structures_flying()) and (
                not self.units(UnitTypeId.MUTALISK).exists):
            await self.chat_send("Do not try to escape from me!")
            self.need_air_units = True

        if self.units(UnitTypeId.MUTALISK).exists:
            if len(self.enemy_structures) > 0:
                for muta in self.units(UnitTypeId.MUTALISK):
                    if muta.is_idle:
                        muta.attack(self.enemy_structures[0])

            else:
                for unit in forces:
                    if unit.is_idle:
                        unit.attack(sc2.position.Point2([random.randint(0, int(self.game_info.map_size[0])),
                                                         random.randint(0, int(self.game_info.map_size[1]))]))


async def is_opponents_main_won(self):
    forces = self.units(UnitTypeId.DRONE) | self.units(UnitTypeId.ZERGLING) | self.units(UnitTypeId.ROACH) | self.units(
        UnitTypeId.MUTALISK)
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