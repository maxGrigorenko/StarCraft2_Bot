from sc2.ids.unit_typeid import UnitTypeId
from .coordinate_functions import get_distance
from src.managers.action_registry import ActionPriority
import random
import sc2.position


class ScoutingHelper:
    """Methods for scouting and navigation around the map."""

    def __init__(self, bot):
        self.bot = bot

    def get_locations(self):
        return self.bot.expansion_locations_list

    def sorted_enemy_locations(self):
        locations = self.get_locations()
        enemy_main = self.bot.enemy_start_locations[0]
        return sorted(locations, key=lambda x: get_distance(x, enemy_main))

    async def base_scout(self, unit, loc_n):
        locations = self.get_locations()
        target = locations[loc_n]
        self.bot.action_registry.submit_action(
            tag=unit.tag,
            action=lambda u=unit, t=target: u.attack(t),
            priority=ActionPriority.LOW,
            source="uf_base_scout"
        )

    async def map_scout(self, army):
        locations = self.bot.locations
        idle_massiv = []
        for i in army:
            if i.tag not in self.bot.home_dronny_tags:
                idle_massiv.append(i)
        if len(idle_massiv) >= len(locations):
            for i in range(len(locations)):
                if idle_massiv[i].tag not in self.bot.in_scout_tags:
                    await self.base_scout(idle_massiv[i], i)
                    self.bot.in_scout_tags.append(idle_massiv[i].tag)
        else:
            for a in army:
                if a.tag not in self.bot.home_dronny_tags:
                    dist = get_distance(a.position, locations[self.bot.location_counter])
                    if dist < 5:
                        self.bot.location_counter += 1
            for j in army:
                if j.tag not in self.bot.home_dronny_tags and j.type_id != UnitTypeId.OVERLORD:
                    await self.base_scout(j, self.bot.location_counter)

    def find_expand(self):
        main_ramp_pos = self.bot.two_enemy_ramps[0].bottom_center
        locations = self.sorted_enemy_locations()[1:]
        expand = locations[0]
        for location in locations:
            if get_distance(main_ramp_pos, location) < get_distance(main_ramp_pos, expand):
                expand = location
        return expand

    def has_expand_ramp(self):
        if not self.bot.expand:
            self.bot.expand = self.find_expand()
        sorted_ramps = sorted(self.bot.game_info.map_ramps,
                              key=lambda x: get_distance(x.top_center, self.bot.expand.position))
        closest_ramp = sorted_ramps[0]
        if closest_ramp == self.bot.two_enemy_ramps[0]:
            closest_ramp = sorted_ramps[1]
        self.bot.two_enemy_ramps[1] = closest_ramp
        ramp_distance = get_distance(self.bot.expand, closest_ramp.top_center)
        print(f"{ramp_distance=}")
        return ramp_distance > 14

    def air_danger_units(self):
        air_units = [unit for unit in self.bot.enemy_units if unit.can_attack_air]
        for struct in self.bot.enemy_structures:
            if struct.can_attack_air:
                air_units.append(struct)
        return air_units

    def select_target(self):
        if self.bot.enemy_structures.exists:
            return random.choice(self.bot.enemy_structures).position
        return self.bot.enemy_start_locations[0]
