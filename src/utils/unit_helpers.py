from sc2.ids.unit_typeid import UnitTypeId
from sc2.data import Race
from .coordinate_functions import get_distance
import sc2.position

class UnitHelper:
    """Helper methods for working with units."""

    def __init__(self, bot):
        self.bot = bot

    def refresh_unit(self, unit_or_tag):
        """Return the current unit by tag or by Unit object."""
        if unit_or_tag is None:
            return None
        if isinstance(unit_or_tag, int):
            try:
                return self.bot.units.by_tag(unit_or_tag)
            except KeyError:
                return None
        try:
            return self.bot.units.by_tag(unit_or_tag.tag)
        except KeyError:
            return None

    def is_units_health_max(self):
        """Check whether all drones have full health."""
        for u in self.bot.units(UnitTypeId.DRONE):
            if u.health_max - u.health > 0:
                return False
        return True

    def remove_idle_drones_tags(self, drones_tags):
        """Remove tags of idle drones from the list."""
        for drone_tag in list(drones_tags):
            drone = self.bot.units.find_by_tag(drone_tag)
            if drone is not None and drone.is_idle:
                drones_tags.remove(drone_tag)
        return drones_tags

    def closest_unit(self, units, obj):
        """Closest unit to the given object."""
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

    def no_units_in_opponent_main(self):
        """Check whether there are any own units in the opponent's main base."""
        for unit in self.bot.units(UnitTypeId.DRONE) | self.bot.units(UnitTypeId.ZERGLING) | self.bot.units(UnitTypeId.QUEEN):
            if get_distance(unit.position, self.bot.enemy_start_locations[0]) < 30:
                return False
        return True

    def proxy(self):
        """Build a proxy extractor if the drone is far from own base."""
        for drone in self.bot.units(UnitTypeId.DRONE):
            if get_distance(drone.position, self.bot.start_location) > 100 and self.bot.minerals >= 25:
                print("Building proxy")
                target = self.bot.vespene_geyser.closest_to(drone.position)
                if target is None:
                    break
                self.bot.action_registry.submit_action(
                    tag=drone.tag,
                    action=lambda d=drone, t=target: d.build(UnitTypeId.EXTRACTOR, t),
                    priority=50,
                    source="uf_proxy"
                )
                if drone.tag not in self.bot.building_workers_tags:
                    self.bot.building_workers_tags.append(drone.tag)
                break

    def enemy_dangerous_structures(self):
        """Return dangerous static defense structures of the enemy."""
        if self.bot.enemy_race == Race.Terran:
            return self.bot.enemy_structures(UnitTypeId.BUNKER)
        elif self.bot.enemy_race == Race.Zerg:
            return self.bot.enemy_structures(UnitTypeId.SPINECRAWLER)
        else:
            return self.bot.enemy_structures(UnitTypeId.PHOTONCANNON)

    def dangerous_structures_exist(self):
        """Check whether any dangerous structures exist."""
        return (
            self.bot.enemy_structures(UnitTypeId.SPINECRAWLER).exists or
            self.bot.enemy_structures(UnitTypeId.PHOTONCANNON).exists or
            self.bot.enemy_structures(UnitTypeId.BUNKER).exists
        )

    def all_flying_enemies(self):
        """Check whether all visible enemy ground units are flying."""
        if len(self.bot.enemy_units) == 0:
            return False
        for enemy in self.bot.enemy_units:
            if not enemy.is_flying:
                return False
        return True

    def all_known_structures_flying(self):
        """Check whether all known enemy structures are flying."""
        if len(self.bot.enemy_structures) == 0:
            return False
        for s in self.bot.enemy_structures:
            if not s.is_flying:
                return False
        return True
