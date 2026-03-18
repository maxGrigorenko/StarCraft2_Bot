from attr import dataclass
from typing import Any
import enum
from src.utils.coordinate_functions import go_from_point, go_towards_point, get_distance
import sc2.unit
import sc2.position
from sc2.data import Race


@dataclass
class OverlordPosition:
    position: sc2.position
    overlord_tag: Any


class OverlordManager:

    def __init__(self):
        self.data_loaded = False
        self.positions_calculated = False
        self.positions_assigned = False
        self.enemy_race = None
        self.enemy_expand = None
        self.enemy_ramp = None
        self.enemy_start_location = None
        self.own_start_location = None
        self.enemy_locations = None
        self.overlord_tags = []
        self.tags_positions = []
        self.busy_overlords = []
        self.enemies = []

    def load_data(self, own_start_location, enemy_start_location,
                  enemy_locations, enemy_ramp, enemy_expand, enemy_race):
        self.enemy_locations = enemy_locations
        self.own_start_location = own_start_location
        self.enemy_start_location = enemy_start_location
        self.enemy_ramp = enemy_ramp
        self.enemy_expand = enemy_expand
        self.enemy_race = enemy_race
        self.data_loaded = True

    def add_tag(self, tag):
        self.overlord_tags.append(tag)
        self.positions_assigned = False

    def remove_tag(self, tag):
        self.overlord_tags.remove(tag)
        self.positions_assigned = False

    def set_tags(self, tags):
        self.overlord_tags = tags
        self.positions_assigned = False

    def calculate_positions(self):
        if not self.data_loaded:
            return

        self.tags_positions = []
        if self.enemy_race != Race.Zerg:
            point_near_ramp = go_from_point(dangerous_position=self.enemy_ramp.top_center,
                                            unit_position=self.enemy_ramp.bottom_center,
                                            dist=2)
            first_position = go_towards_point(unit_position=point_near_ramp,
                                              target_position=self.own_start_location,
                                              dist=2)
            self.tags_positions.append(OverlordPosition(position=first_position, overlord_tag=None))

        for location in self.enemy_locations[1:]:
            if get_distance(location, self.own_start_location) > 5:
                position = go_towards_point(unit_position=location,
                                            target_position=self.own_start_location,
                                            dist=8)
                self.tags_positions.append(OverlordPosition(position=position, overlord_tag=None))

    def assign_positions(self, overlords):
        free_overlord_tags = [overlord_tag for overlord_tag in self.overlord_tags if overlord_tag not in self.busy_overlords]
        if len(free_overlord_tags) == 0:
            return

        for overlord_and_tag in self.tags_positions:
            position = overlord_and_tag.position
            if overlord_and_tag.overlord_tag is not None:
                continue
            free_overlords = [overlord for overlord in overlords if overlord.tag in free_overlord_tags]
            overlord = min(free_overlords, key=lambda x: get_distance(x.position, position))
            overlord_and_tag.overlord_tag = overlord.tag
            self.busy_overlords.append(overlord.tag)
            free_overlord_tags.remove(overlord.tag)
            if len(free_overlord_tags) == 0:
                return

    async def manage(self, overlords, enemies):
        for tag in overlords.tags:
            if tag not in self.overlord_tags:
                self.add_tag(tag)

        for tag in self.overlord_tags:
            if tag not in overlords.tags:
                self.remove_tag(tag)

        self.enemies = enemies

        if not self.positions_calculated:
            self.calculate_positions()
            self.positions_calculated = True

        if not self.positions_assigned:
            self.assign_positions(overlords)
            self.positions_assigned = True

        for tag_and_position in self.tags_positions:
            tag = tag_and_position.overlord_tag
            position = tag_and_position.position
            if tag is None:
                continue
            array = [overlord for overlord in overlords if overlord.tag == tag]
            if len(array) == 0:
                continue

            overlord = array[0]
            if len(self.enemies) > 0:
                closest_enemy = min(self.enemies, key=lambda x: get_distance(x.position, overlord.position))
                if get_distance(overlord.position, closest_enemy.position) < 9.5:
                    overlord.move(go_from_point(dangerous_position=closest_enemy.position,
                                                unit_position=overlord.position,
                                                dist=1))
                    continue
            if overlord.health > overlord.health_max * 0.6 and get_distance(overlord.position, position) > 0.1:
                overlord.move(position)

