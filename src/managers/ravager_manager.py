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


def find_bile_target(ravager, priority_targets, other_targets, own_units):
    """Find the best target for Corrosive Bile within range.
    Priority targets (static defense) are preferred over other targets.
    Also ensure that no own unit is within radius + 0.5 of the target position."""
    all_targets = list(priority_targets) + list(other_targets)
    best_sieged_tank = None
    best_sieged_dist = 9999
    
    for target in all_targets:
        # Проверяем, является ли цель осадным танком (UnitTypeId.SIEGETANKSIEGED)
        # В sc2.ids.unit_typeid есть SIEGETANK и SIEGETANKSIEGED
        from sc2.ids.unit_typeid import UnitTypeId
        if hasattr(target, 'type_id'):
            if target.type_id == UnitTypeId.SIEGETANKSIEGED:
                d = get_distance(ravager.position, target.position)
                if d <= BILE_RANGE and d < best_sieged_dist:
                    # Проверяем безопасность для своих юнитов
                    target_pos = target.position
                    safe = True
                    for unit in own_units:
                        dist_to_unit = get_distance(target_pos, unit.position)
                        if dist_to_unit <= unit.radius + 0.5:
                            safe = False
                            break
                    if safe:
                        best_sieged_dist = d
                        best_sieged_tank = target
    
    if best_sieged_tank is not None:
        return best_sieged_tank

    best_target = None
    best_dist = 9999

    for target in priority_targets:
        d = get_distance(ravager.position, target.position)
        if d <= BILE_RANGE and d < best_dist:
            target_pos = target.position
            safe = True
            for unit in own_units:
                dist_to_unit = get_distance(target_pos, unit.position)
                if dist_to_unit <= unit.radius + 0.5:
                    safe = False
                    break
            if safe:
                best_dist = d
                best_target = target

    if best_target is not None:
        return best_target

    best_dist = 9999
    for target in other_targets:
        d = get_distance(ravager.position, target.position)
        if d <= BILE_RANGE and d < best_dist:
            target_pos = target.position
            safe = True
            for unit in own_units:
                if unit.tag == ravager.tag:
                    continue
                dist_to_unit = get_distance(target_pos, unit.position)
                if dist_to_unit <= unit.radius + 0.5:
                    safe = False
                    break
            if safe:
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
    """Get structures that can attack ground units and are active.
    Excludes:
        - SporeCrawler (doesn't attack ground)
        - PhotonCannon without power (is_powered == False)
        - Empty Bunker (no units inside)
        - Structures still building (build_progress < 1.0)
    """
    dangerous_type_ids = {
        UnitTypeId.PHOTONCANNON,
        UnitTypeId.BUNKER,
        UnitTypeId.SPINECRAWLER,
    }
    result = []
    for s in enemy_structures:
        if s.type_id not in dangerous_type_ids:
            continue
        if s.type_id == UnitTypeId.PHOTONCANNON and not s.is_powered:
            continue
        if s.type_id == UnitTypeId.BUNKER and not s.has_cargo:
            continue
        if s.build_progress < 1.0:
            continue
        result.append(s)
    return result


class RavagerManager:

    def __init__(self):
        pass

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
            can_cast_bile = await bot.can_cast(ravager, AbilityId.EFFECT_CORROSIVEBILE, only_check_energy_and_cooldown=True)
            
            min_danger_dist = 9999
            for struct in dangerous_structures:
                d = get_distance(ravager.position, struct.position)
                if d < min_danger_dist:
                    min_danger_dist = d
                    closest_danger = struct

            min_dist = 15.0
            if closest_danger is not None and can_cast_bile:
                if closest_danger.is_visible:
                    min_dist = 8.5
                else:
                    min_dist = 3.0

            # 1. STRICT DISTANCE CHECK
            if (closest_danger is not None) and (min_danger_dist < min_dist):
                safe_pos = go_from_point(
                    unit_position=ravager.position,
                    dangerous_position=closest_danger.position,
                    dist=15.0-min_danger_dist
                )
                ravager.move(safe_pos)
                handled = True

            # 2. BILE CASTING (Can cast if safe, i.e., >= 8.0)
            if not handled and (len(priority_targets) > 0 or len(other_bile_targets) > 0 or len(ground_enemies) > 0):
                own_units = list(ravagers) + list(roaches)
                bile_target = find_bile_target(ravager, priority_targets, other_bile_targets + ground_enemies, own_units)
                if bile_target is not None:
                    if can_cast_bile:
                        bile_position = go_towards_point(unit_position=bile_target.position, target_position=ravager.position, dist=bile_target.radius+0.2)
                        safe_cast = True
                        for unit in own_units:
                            if unit.tag == ravager.tag:
                                continue
                            dist_to_unit = get_distance(bile_position, unit.position)
                            if dist_to_unit <= unit.radius + 0.5:
                                safe_cast = False
                                break
                        if safe_cast:
                            ravager(AbilityId.EFFECT_CORROSIVEBILE, bile_position)
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
            critic_distance = 12.0
            if can_cast_bile:
                critic_distance = 8.5
                if (closest_danger is not None) and (not closest_danger.is_visible):
                    critic_distance = 3.0

            if (not handled) and (closest_danger is not None) and (min_danger_dist < critic_distance):
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
            if closest_danger is not None and min_danger_dist < 12.0:
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
            if not handled and closest_danger is not None and min_danger_dist < 15.0:
                roach.stop()
                handled = True

            if handled:
                handled_tags.add(roach.tag)

        return handled_tags
