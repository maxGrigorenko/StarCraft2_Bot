from attr import dataclass
from typing import Any
import enum
from src.utils.coordinate_functions import go_from_point, go_towards_point, get_distance
from sc2.ids.unit_typeid import UnitTypeId
import sc2.unit
import sc2.position
from sc2.data import Race


@dataclass
class OverlordPosition:
    position: sc2.position
    overlord_tag: Any


class OverlordManager:

    def __init__(self, bot=None):
        self.bot = bot
        self.data_loaded = False
        self.positions_calculated = False
        self.positions_assigned = False
        self.enemy_race = None
        self.enemy_expand = None
        self.enemy_ramp = None
        self.enemy_start_location = None
        self.own_start_location = None
        self.enemy_locations = None
        self.overlord_tags: set[int] = set()
        self.tags_positions = []
        self.busy_overlords: set[int] = set()
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
        self.overlord_tags.add(tag)
        self.positions_assigned = False

    def remove_tag(self, tag):
        self.overlord_tags.discard(tag)
        self.positions_assigned = False

    def set_tags(self, tags):
        self.overlord_tags = set(tags)
        self.positions_assigned = False

    def calculate_positions(self):
        if not self.data_loaded:
            return

        if self.enemy_race == Race.Zerg:
            dist_from_bases = 15.0
        else:
            dist_from_bases = 10.0

        self.tags_positions = []
        if self.enemy_race != Race.Zerg:
            first_position = go_from_point(dangerous_position=self.enemy_ramp.top_center,
                                           unit_position=self.enemy_ramp.bottom_center,
                                           dist=2)
            self.tags_positions.append(OverlordPosition(position=first_position, overlord_tag=None))

        for location in self.enemy_locations[1:]:
            if get_distance(location, self.own_start_location) > 5:
                position = go_towards_point(unit_position=location,
                                            target_position=self.own_start_location,
                                            dist=dist_from_bases)
                self.tags_positions.append(OverlordPosition(position=position, overlord_tag=None))

    def assign_positions(self, overlords):
        free_overlord_tags = [overlord_tag for overlord_tag in self.overlord_tags if
                              overlord_tag not in self.busy_overlords]
        if len(free_overlord_tags) == 0:
            return

        for overlord_and_tag in self.tags_positions:
            position = overlord_and_tag.position
            if overlord_and_tag.overlord_tag is not None:
                continue
            free_overlords = [overlord for overlord in overlords if overlord.tag in free_overlord_tags]
            overlord = min(free_overlords, key=lambda x: get_distance(x.position, position))
            overlord_and_tag.overlord_tag = overlord.tag
            self.busy_overlords.add(overlord.tag)
            free_overlord_tags.remove(overlord.tag)
            if len(free_overlord_tags) == 0:
                return

    def _is_near_enemy_base(self, position, threshold=30):
        return get_distance(position, self.enemy_start_location) < threshold

    def _has_own_units_nearby(self, position, own_units, threshold=30):
        for unit in own_units:
            if get_distance(unit.position, position) < threshold:
                return True
        return False

    async def manage(self, overlords, enemies, own_units=None):
        if own_units is None:
            own_units = []

        if self.bot is not None:
            own_units = (self.bot.units(UnitTypeId.DRONE) | self.bot.units(UnitTypeId.ZERGLING) |
                         self.bot.units(UnitTypeId.ROACH) | self.bot.units(UnitTypeId.RAVAGER) |
                         self.bot.units(UnitTypeId.MUTALISK))

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
                    retreat_pos = go_from_point(dangerous_position=closest_enemy.position,
                                                unit_position=overlord.position,
                                                dist=1)
                    self.bot.action_registry.submit_action(tag=overlord.tag,
                                                           action=lambda o=overlord, p=retreat_pos: o.move(p),
                                                           priority=50,
                                                           source="OverlordManager")
                    continue

            if self._is_near_enemy_base(position):
                if not self._has_own_units_nearby(position, own_units):
                    position = go_from_point(unit_position=position,
                                             dangerous_position=self.enemy_start_location,
                                             dist=10)

            if overlord.health > overlord.health_max * 0.6 and get_distance(overlord.position, position) > 0.1:
                self.bot.action_registry.submit_action(tag=overlord.tag,
                                                       action=lambda o=overlord, p=position: o.move(p),
                                                       priority=50,
                                                       source="OverlordManager")
