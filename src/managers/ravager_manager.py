from src.utils.coordinate_functions import go_from_point, go_towards_point, get_distance
from sc2.ids.unit_typeid import UnitTypeId
from sc2.ids.ability_id import AbilityId
from sc2.position import Point2


# Attack ranges of dangerous static defense structures
STATIC_DEFENSE_RANGES = {
    UnitTypeId.PHOTONCANNON: 7.0,
    UnitTypeId.SHIELDBATTERY: 6.0,
    UnitTypeId.BUNKER: 6.0,
    UnitTypeId.SPINECRAWLER: 7.0,
    UnitTypeId.SPORECRAWLER: 7.0,
}

BILE_RANGE = 9.0
BILE_SAFE_MARGIN = 1.0


def is_in_static_defense_range(unit_position, structure, margin=0.0):
    """Check if a unit position is within attack range of a static defense structure."""
    attack_range = STATIC_DEFENSE_RANGES.get(structure.type_id, 7.0)
    dist = get_distance(unit_position, structure.position)
    return dist <= attack_range + margin


def find_safe_bile_position(unit_position, target_position, dangerous_structures):
    """Find a position where the unit can cast Corrosive Bile
    while staying outside the attack range of dangerous structures.
    Returns the position to move to, or None if already safe."""
    for structure in dangerous_structures:
        if is_in_static_defense_range(unit_position, structure, margin=BILE_SAFE_MARGIN):
            attack_range = STATIC_DEFENSE_RANGES.get(structure.type_id, 7.0)
            safe_dist = attack_range + BILE_SAFE_MARGIN
            safe_position = go_from_point(
                unit_position=structure.position,
                dangerous_position=target_position,
                dist=safe_dist
            )
            return safe_position
    return None


def calculate_retreat_position(unit_position, enemy_position, retreat_dist=1.0):
    """Calculate retreat position away from the closest enemy by a given distance."""
    return go_from_point(
        unit_position=unit_position,
        dangerous_position=enemy_position,
        dist=retreat_dist
    )


def find_closest_enemy(unit, enemies):
    """Find the closest enemy to a given unit."""
    if len(enemies) == 0:
        return None
    closest = None
    min_dist = 9999
    for enemy in enemies:
        d = get_distance(unit.position, enemy.position)
        if d < min_dist:
            min_dist = d
            closest = enemy
    return closest


def find_bile_target(ravager, priority_targets, other_targets):
    """Find the best target for Corrosive Bile within range.
    Priority targets (static defense) are preferred over other targets."""
    best_target = None
    best_dist = 9999

    for target in priority_targets:
        d = get_distance(ravager.position, target.position)
        if d <= BILE_RANGE and d < best_dist:
            best_dist = d
            best_target = target

    if best_target is not None:
        return best_target

    best_dist = 9999
    for target in other_targets:
        d = get_distance(ravager.position, target.position)
        if d <= BILE_RANGE and d < best_dist:
            best_dist = d
            best_target = target

    return best_target


def get_priority_structures(enemy_structures):
    """Get static defense structures that are priority targets."""
    result = []
    for s in enemy_structures:
        if s.type_id in STATIC_DEFENSE_RANGES:
            result.append(s)
    return result


def get_dangerous_structures(enemy_structures):
    """Get structures that can attack ground units."""
    dangerous_type_ids = {
        UnitTypeId.PHOTONCANNON,
        UnitTypeId.BUNKER,
        UnitTypeId.SPINECRAWLER,
    }
    result = []
    for s in enemy_structures:
        if s.type_id in dangerous_type_ids:
            result.append(s)
    return result


class RavagerManager:

    def __init__(self):
        self.bile_cooldowns = {}  # tag -> game_loop when bile was last used

    def update_cooldown(self, tag, game_loop):
        self.bile_cooldowns[tag] = game_loop

    def is_bile_ready(self, tag, game_loop):
        """Corrosive Bile cooldown is about 7 seconds (~157 game loops at normal speed).
        We use a slightly shorter check to account for latency."""
        if tag not in self.bile_cooldowns:
            return True
        elapsed = game_loop - self.bile_cooldowns[tag]
        return elapsed >= 100  # conservative estimate

    async def manage(self, bot, ravagers, roaches, enemy_units, enemy_structures,
                     enemy_start_location, own_start_location, game_loop):
        """Main management function for ravagers and roaches.
        Handles Corrosive Bile casting, stutter-step micro, and positioning.
        Returns a set of unit tags that were handled by this manager."""

        handled_tags = set()
        dangerous_structures = get_dangerous_structures(enemy_structures)
        priority_targets = get_priority_structures(enemy_structures)

        other_bile_targets = []
        for s in enemy_structures:
            if s not in priority_targets:
                other_bile_targets.append(s)

        ground_enemies = [u for u in enemy_units if not u.is_flying and not u.is_hallucination]

        # Manage Ravagers
        for ravager in ravagers:
            handled = False
            closest_danger = None
            abilities = await bot.get_available_abilities(ravager)
            if AbilityId.EFFECT_CORROSIVEBILE in abilities:
                min_dist = 8.3
            else:
                min_dist = 15.0

            min_danger_dist = 9999
            for struct in dangerous_structures:
                d = get_distance(ravager.position, struct.position)
                if d < min_danger_dist:
                    min_danger_dist = d
                    closest_danger = struct

            # 1. STRICT DISTANCE CHECK
            if closest_danger is not None and min_danger_dist < min_dist:
                safe_pos = go_from_point(
                    unit_position=ravager.position,
                    dangerous_position=closest_danger.position,
                    dist=min_dist-min_danger_dist
                )
                ravager.move(safe_pos)
                handled = True

            # 2. BILE CASTING (Can cast if safe, i.e., >= 8.0)
            if not handled and (len(priority_targets) > 0 or len(other_bile_targets) > 0 or len(ground_enemies) > 0):
                bile_target = find_bile_target(ravager, priority_targets, other_bile_targets + ground_enemies)
                if bile_target is not None and self.is_bile_ready(ravager.tag, game_loop):
                    abilities = await bot.get_available_abilities(ravager)
                    if AbilityId.EFFECT_CORROSIVEBILE in abilities:
                        bile_position = go_towards_point(unit_position=bile_target.position, target_position=ravager.position, dist=bile_target.radius+0.2)
                        ravager(AbilityId.EFFECT_CORROSIVEBILE, bile_position)
                        self.update_cooldown(ravager.tag, game_loop)
                        handled = True

            # 3. Stutter-step micro against ground enemies
            if not handled:
                closest_enemy = find_closest_enemy(ravager, ground_enemies)
                if closest_enemy is not None:
                    dist_to_enemy = get_distance(ravager.position, closest_enemy.position)
                    if dist_to_enemy < 8:
                        if ravager.weapon_ready:
                            ravager.attack(closest_enemy.position)
                        else:
                            retreat_pos = calculate_retreat_position(
                                ravager.position, closest_enemy.position, retreat_dist=1.5
                            )
                            ravager.move(retreat_pos)
                        handled = True

            # 4. Wait safely outside danger zone (prevent macro from walking into cannons)
            if not handled and closest_danger is not None and min_danger_dist < 9.5:
                ravager.stop()
                handled = True

            if handled:
                handled_tags.add(ravager.tag)

        # Manage Roaches with stutter-step
        for roach in roaches:
            handled = False
            closest_danger = None
            min_danger_dist = 9999

            for struct in dangerous_structures:
                d = get_distance(roach.position, struct.position)
                if d < min_danger_dist:
                    min_danger_dist = d
                    closest_danger = struct

            # STRICT DISTANCE CHECK FOR ROACHES TOO
            if closest_danger is not None and min_danger_dist < 8.0:
                safe_pos = go_from_point(
                    unit_position=roach.position,
                    dangerous_position=closest_danger.position,
                    dist=2.0
                )
                roach.move(safe_pos)
                handled = True

            if not handled:
                closest_enemy = find_closest_enemy(roach, ground_enemies)
                if closest_enemy is not None:
                    dist_to_enemy = get_distance(roach.position, closest_enemy.position)
                    if dist_to_enemy < 7:
                        if roach.weapon_ready:
                            roach.attack(closest_enemy.position)
                        else:
                            retreat_pos = calculate_retreat_position(
                                roach.position, closest_enemy.position, retreat_dist=1.0
                            )
                            roach.move(retreat_pos)
                        handled = True

            # Wait safely outside danger zone
            if not handled and closest_danger is not None and min_danger_dist < 8.5:
                roach.stop()
                handled = True

            if handled:
                handled_tags.add(roach.tag)

        return handled_tags
