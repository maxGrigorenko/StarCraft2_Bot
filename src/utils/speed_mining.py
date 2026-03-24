from sc2.ids.unit_typeid import UnitTypeId
from .coordinate_functions import *
from src.managers.action_registry import ActionPriority


def assign_mining_positions(self):
    hatcheries = list(filter(self.is_hatchery_for_mining,
                             self.structures(UnitTypeId.HATCHERY) | self.structures(UnitTypeId.LAIR) | self.structures(
                                 UnitTypeId.HIVE)))

    for hatchery in hatcheries:
        for mineral_field in self.mining_hatchery_data.get(hatchery, []):
            for drone_tag in self.mining_mineral_data.get(mineral_field, []):
                if drone_tag in self.mining_drones_tags:

                    if drone_tag not in self.mining_drone_data:
                        self.mining_drone_data[drone_tag] = []

                    if len(self.mining_drone_data[drone_tag]) == 0:
                        hatchery_position_mining, mineral_position_mining = find_mining_positions(hatchery, mineral_field)
                        self.mining_drone_data[drone_tag] = [hatchery_position_mining, mineral_position_mining]

                else:
                    if drone_tag in self.mining_drone_data:
                        del self.mining_drone_data[drone_tag]
                    mineral_list = self.mining_mineral_data.get(mineral_field, [])
                    if drone_tag in mineral_list:
                        mineral_list.remove(drone_tag)


def check_reorganization(self):
    mineral_filed_distances = dict(sorted(self.mineral_field_distances.items(), key=lambda x: x[1]))
    all_drones = len(self.mining_drones_tags)
    used_drones = 0

    mineral_fields = list(mineral_filed_distances.keys())

    for i in range(len(mineral_fields)):
        mineral_field = mineral_fields[i]
        drones = len(self.mining_mineral_data.get(mineral_field, []))
        used_drones += drones
        free_drones = all_drones - used_drones

        if drones < 2 and free_drones > 0:
            need_drones = 2 - drones

            for j in range(len(mineral_fields) - 1, i, -1):
                field = mineral_fields[j]
                for k in range(2):
                    if need_drones > 0 and free_drones > 0:
                        field_drones = self.mining_mineral_data.get(field, [])
                        if len(field_drones) > 0:
                            drone_tag = field_drones[0]
                            self.mining_mineral_data[mineral_field].append(drone_tag)
                            field_drones.remove(drone_tag)

                            if drone_tag in self.mining_drone_data:
                                del self.mining_drone_data[drone_tag]

                            used_drones += 1
                            free_drones -= 1
                            need_drones -= 1
                    else:
                        break

        elif free_drones == 0:
            return


def refresh_mining_data(self, drones):
    drones = drones.copy()
    drone_tags = [d.tag for d in drones]

    all_mineral_fields = self.mineral_field
    hatcheries = list(filter(self.is_hatchery_for_mining, self.structures(UnitTypeId.HATCHERY) | self.structures(
        UnitTypeId.LAIR) | self.structures(UnitTypeId.HIVE)))

    for hatchery in hatcheries:
        if hatchery not in self.mining_hatchery_data:
            self.mining_hatchery_data[hatchery] = []

    for mineral_field in all_mineral_fields:
        closest_hatchery = self.closest_unit(hatcheries, mineral_field)
        distance = get_distance(closest_hatchery.position, mineral_field.position)

        if distance < 10 and mineral_field not in self.mining_mineral_data:
            self.mining_mineral_data[mineral_field] = []
            self.mineral_field_distances[mineral_field] = distance

            if mineral_field not in self.mining_hatchery_data[closest_hatchery]:
                self.mining_hatchery_data[closest_hatchery].append(mineral_field)

    mineral_filed_distances = dict(sorted(self.mineral_field_distances.items(), key=lambda x: x[1]))

    for mineral_field in list(self.mining_mineral_data.keys()):
        busy_drone_tags = self.mining_mineral_data[mineral_field]
        for drone_tag in busy_drone_tags[:]:
            if drone_tag in drone_tags:
                drone_obj = next((d for d in drones if d.tag == drone_tag), None)
                if drone_obj is not None:
                    drones.remove(drone_obj)
            else:
                busy_drone_tags.remove(drone_tag)
                if drone_tag in self.mining_drone_data:
                    del self.mining_drone_data[drone_tag]

    for mineral_field in mineral_filed_distances.keys():
        drones_quantity = len(self.mining_mineral_data.get(mineral_field, []))
        if drones_quantity < 2:
            for i in range(2 - drones_quantity):
                if len(drones) > 0:
                    closest_drone = self.closest_unit(drones, mineral_field)
                    if closest_drone is None:
                        break
                    self.mining_mineral_data[mineral_field].append(closest_drone.tag)
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
            distances[field] = get_distance(field.position, mineral_field.position)

    mineral_filed_distances = dict(sorted(distances.items(), key=lambda x: x[1]))
    return list(mineral_filed_distances.keys())[0], list(mineral_filed_distances.keys())[1]


async def speed_mining(self):
    drone_radius = 0.375
    mineral_radius = 0.4
    hatchery_radius = 2.75
    r = 1.125

    min_drone_mineral_distance = drone_radius + mineral_radius
    min_drone_hatchery_distance = drone_radius + self.townhalls.first.radius

    for mineral_field in list(self.mining_mineral_data.keys()):
        for drone_tag in self.mining_mineral_data[mineral_field]:
            if drone_tag not in self.mining_drones_tags:
                continue

            drone = self.refresh_unit(drone_tag)
            if drone is None:
                continue

            hatchery = self.closest_unit(
                self.structures(UnitTypeId.HATCHERY) | self.structures(UnitTypeId.LAIR) | self.structures(
                    UnitTypeId.HIVE), drone)
            if hatchery is None:
                continue

            distance_to_hatch = get_distance(drone.position, hatchery.position)
            distance_to_mineral = get_distance(drone.position, mineral_field.position)
            mineral_hatch_distance = get_distance(hatchery.position, mineral_field.position)

            mining_positions = self.mining_drone_data.get(drone_tag, [])

            if drone.is_carrying_resource:
                if distance_to_hatch > min_drone_hatchery_distance + 1:
                    if len(mining_positions) >= 1:
                        hatch_pos = mining_positions[0]
                        self.action_registry.submit_action(
                            drone_tag,
                            lambda d=drone, hp=hatch_pos: d.move(hp),
                            ActionPriority.LOW,
                            "speed_mining"
                        )
                        self.action_registry.submit_action(
                            drone_tag,
                            lambda d=drone, hp=hatch_pos, mf=mineral_field: (
                                d.move(hp),
                                d.return_resource(queue=True)
                            ),
                            ActionPriority.LOW,
                            "speed_mining"
                        )
                    else:
                        self.action_registry.submit_action(
                            drone_tag,
                            lambda d=drone: d.return_resource(),
                            ActionPriority.LOW,
                            "speed_mining"
                        )
                else:
                    self.action_registry.submit_action(
                        drone_tag,
                        lambda d=drone, mf=mineral_field: (
                            d.return_resource(),
                            d.gather(mf, queue=True)
                        ),
                        ActionPriority.LOW,
                        "speed_mining"
                    )
            else:
                if not (mineral_hatch_distance > 6.9 and len(
                        self.mining_mineral_data[mineral_field]) == 2) and distance_to_mineral > min_drone_mineral_distance + 1:
                    if len(mining_positions) >= 2:
                        mineral_pos = mining_positions[1]
                        self.action_registry.submit_action(
                            drone_tag,
                            lambda d=drone, mp=mineral_pos, mf=mineral_field: (
                                d.move(mp),
                                d.gather(mf, queue=True)
                            ),
                            ActionPriority.LOW,
                            "speed_mining"
                        )
                    else:
                        self.action_registry.submit_action(
                            drone_tag,
                            lambda d=drone, mf=mineral_field: d.gather(mf),
                            ActionPriority.LOW,
                            "speed_mining"
                        )
                else:
                    self.action_registry.submit_action(
                        drone_tag,
                        lambda d=drone, mf=mineral_field: (
                            d.gather(mf),
                            d.return_resource(queue=True)
                        ),
                        ActionPriority.LOW,
                        "speed_mining"
                    )
