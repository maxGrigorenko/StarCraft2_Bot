from sc2.ids.unit_typeid import UnitTypeId
from coordinate_functions import *


def assign_mining_positions(self):
    hatcheries = list(filter(self.is_hatchery_for_mining,
                             self.structures(UnitTypeId.HATCHERY) | self.structures(UnitTypeId.LAIR) | self.structures(
                                 UnitTypeId.HIVE)))

    for hatchery in hatcheries:
        for mineral_field in self.mining_hatchery_data[hatchery]:
            for drone in self.mining_mineral_data[mineral_field]:
                if drone in self.mining_drones:

                    if drone not in self.mining_drone_data.keys():
                        self.mining_drone_data.update({drone: []})

                    if len(self.mining_drone_data[drone]) == 0:
                        hatchery_position_mining, mineral_position_mining = find_mining_positions(hatchery, mineral_field)
                        self.mining_drone_data[drone] = [hatchery_position_mining, mineral_position_mining]

                else:
                    if drone in self.mining_drone_data.keys():
                        del self.mining_drone_data[drone]
                        self.mining_mineral_data[mineral_field].remove(drone)


def check_reorganization(self):
    mineral_filed_distances = dict(sorted(self.mineral_field_distances.items(), key=lambda x: x[1]))
    all_drones = len(self.mining_drones)
    used_drones = 0

    mineral_fields = list(mineral_filed_distances.keys())

    for i in range(len(mineral_fields)):
        mineral_field = mineral_fields[i]
        drones = len(self.mining_mineral_data[mineral_field])
        used_drones += drones
        free_drones = all_drones - used_drones

        if drones < 2 and free_drones > 0:
            need_drones = 2 - drones

            for j in range(len(mineral_fields) - 1, i, -1):
                field = mineral_fields[j]
                for k in range(2):
                    if need_drones > 0 and free_drones > 0:

                        if len(self.mining_mineral_data[field]) > 0:
                            drone = self.mining_mineral_data[field][0]
                            self.mining_mineral_data[mineral_field].append(drone)
                            self.mining_mineral_data[field].remove(drone)

                            if drone in self.mining_drone_data:
                                del self.mining_drone_data[drone]

                            used_drones += 1
                            free_drones -= 1
                            need_drones -= 1
                    else:
                        break

        elif free_drones == 0:
            return


def refresh_mining_data(self, drones):
    drones = drones.copy()
    all_mineral_fields = self.mineral_field
    hatcheries = list(filter(self.is_hatchery_for_mining, self.structures(UnitTypeId.HATCHERY) | self.structures(
        UnitTypeId.LAIR) | self.structures(UnitTypeId.HIVE)))

    for hatchery in hatcheries:
        if hatchery not in self.mining_hatchery_data.keys():
            self.mining_hatchery_data.update({hatchery: []})

    for mineral_field in all_mineral_fields:
        closest_hatchery = self.closest_unit(hatcheries, mineral_field)
        distance = get_distance(closest_hatchery.position, mineral_field.position)

        if distance < 10 and mineral_field not in self.mining_mineral_data.keys():
            self.mining_mineral_data.update({mineral_field: []})
            self.mineral_field_distances.update({mineral_field: distance})

            if mineral_field not in self.mining_hatchery_data[closest_hatchery]:
                self.mining_hatchery_data[closest_hatchery].append(mineral_field)

    mineral_filed_distances = dict(sorted(self.mineral_field_distances.items(), key=lambda x: x[1]))

    for mineral_field in self.mining_mineral_data.keys():  # mineral_data.values() = [[drone1, drone2], [drone1, drone2], ...]
        busy_drones_array = self.mining_mineral_data[mineral_field]
        if len(busy_drones_array) > 0:
            for busy_drone in busy_drones_array:
                if busy_drone in drones:
                    drones.remove(busy_drone)
                else:
                    self.mining_mineral_data[mineral_field].remove(busy_drone)

    for mineral_field in mineral_filed_distances.keys():  # [mineral1, mineral2, ...]
        drones_quantity = len(self.mining_mineral_data[mineral_field])
        if drones_quantity < 2:
            for i in range(2 - drones_quantity):
                if len(drones) > 0:
                    closest_drone = self.closest_unit(drones, mineral_field)
                    self.mining_mineral_data[mineral_field].append(closest_drone)
                    drones.remove(closest_drone)

    self.check_reorganization()
    self.assign_mining_positions()


def check_mineral_fields_near_base(self, base):
    for mineral_field in self.mineral_field:
        distance = get_distance(base.position, mineral_field.position)
        if distance < 10:
            return True
    return False


def is_hatchery_for_mining(self, hatchery):
    closest_mineral_fields = self.mineral_field.closer_than(10, hatchery)
    if len(closest_mineral_fields) >= 1:
        result = True
    else:
        result = False
    return result


def neighbor_mineral_fields(self, mineral_field):
    distances = {}
    for field in self.mineral_field:
        if field != mineral_field:
            distances.update({field: get_distance(field.position, mineral_field.position)})

    mineral_filed_distances = dict(sorted(distances.items(), key=lambda x: x[1]))
    return list(mineral_filed_distances.keys())[0], list(mineral_filed_distances.keys())[1]


async def speed_mining(self):
    drone_radius = 0.375
    mineral_radius = 0.4  # around
    hatchery_radius = 2.75
    r = 1.125  # mineral_field_radius

    min_drone_mineral_distance = drone_radius + mineral_radius
    min_drone_hatchery_distance = drone_radius + self.townhalls.first.radius

    for mineral_field in self.mining_mineral_data.keys():
        for drone in self.mining_mineral_data[mineral_field]:
            if drone in self.mining_drones:

                drone = self.refresh_unit(drone)
                hatchery = self.closest_unit(
                    self.structures(UnitTypeId.HATCHERY) | self.structures(UnitTypeId.LAIR) | self.structures(
                        UnitTypeId.HIVE), drone)
                distance_to_hatch = get_distance(drone.position, hatchery.position)
                distance_to_mineral = get_distance(drone.position, mineral_field.position)
                mineral_hatch_distance = get_distance(hatchery.position, mineral_field.position)

                if drone.is_carrying_resource:

                    if distance_to_hatch > min_drone_hatchery_distance + 1:
                        position = self.mining_drone_data[drone][0]
                        drone.move(position)
                        drone.return_resource(queue=True)

                    else:
                        drone.return_resource()
                        drone.gather(mineral_field, queue=True)

                else:

                    if not (mineral_hatch_distance > 6.9 and len(self.mining_mineral_data[
                                                                     mineral_field]) == 2) and distance_to_mineral > min_drone_mineral_distance + 1:
                        position = self.mining_drone_data[drone][1]
                        drone.move(position)
                        drone.gather(mineral_field, queue=True)

                    else:
                        drone.gather(mineral_field)
                        drone.return_resource(queue=True)
