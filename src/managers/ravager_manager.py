from src.utils.coordinate_functions import go_from_point, go_towards_point, get_distance
from sc2.ids.unit_typeid import UnitTypeId
from sc2.ids.ability_id import AbilityId
from sc2.ids.effect_id import EffectId
from sc2.position import Point2
from src.managers.action_registry import ActionPriority


STATIC_DEFENSE_RANGES = {
    UnitTypeId.PHOTONCANNON: 7.0,
    UnitTypeId.SHIELDBATTERY: 6.0,
    UnitTypeId.BUNKER: 6.0,
    UnitTypeId.SPINECRAWLER: 7.0,
    UnitTypeId.SPORECRAWLER: 7.0,
}

BILE_RANGE = 9.0
BILE_SAFE_MARGIN = 1.0
BILE_DAMAGE = 60
BILE_RADIUS = 0.5  # area-of-effect radius of Corrosive Bile
SHIELD_BATTERY_HEAL_RANGE = 6.0


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


def count_incoming_bile_damage(target, bile_effects):
    """Calculate total incoming Corrosive Bile damage for a target
    based on already-launched bile effects."""
    total_damage = 0
    target_pos = target.position
    target_radius = target.radius

    for effect in bile_effects:
        for bile_pos in effect.positions:
            dist = get_distance(target_pos, bile_pos)
            if dist <= target_radius + BILE_RADIUS:
                total_damage += BILE_DAMAGE

    return total_damage


def is_being_healed(target, enemy_units, enemy_structures):
    """Check whether the target is currently being healed, repaired or shield-recharged."""
    target_pos = target.position

    for unit in enemy_units:
        if unit.type_id == UnitTypeId.SCV and unit.is_repairing:
            dist = get_distance(unit.position, target_pos)
            if dist <= target.radius + 1.0:
                return True

    return False


def is_target_already_doomed(target, bile_effects, enemy_units=None, enemy_structures=None):
    """Find the best target for Corrosive Bile within range.
    Priority targets (static defense) are preferred over other targets.
    Also ensure that no own unit is within radius + 0.5 of the target position."""

    incoming_damage = count_incoming_bile_damage(target, bile_effects)
    if incoming_damage <= 0:
        return False

    if enemy_units is not None and enemy_structures is not None:
        if is_being_healed(target, enemy_units, enemy_structures):
            return False

    current_hp = target.health + target.shield

    if hasattr(target, 'build_progress') and target.build_progress < 1.0:
        effective_hp = current_hp + BILE_DAMAGE
    else:
        effective_hp = current_hp

    return incoming_damage >= effective_hp


def get_pylon_priority(pylon, enemy_structures):
    """Return the priority level of a Pylon based on what it powers:
        1 - powers a Stargate (highest priority)
        2 - powers a Photon Cannon or Shield Battery
        3 - other pylons
    """
    stargate_types = {UnitTypeId.STARGATE, UnitTypeId.FLEETBEACON}
    photon_battery_types = {UnitTypeId.PHOTONCANNON, UnitTypeId.SHIELDBATTERY}

    pylon_pos = pylon.position
    PYLON_POWER_RADIUS = 6.5

    powers_stargate = False
    powers_photon_or_battery = False

    for structure in enemy_structures:
        if structure.type_id not in stargate_types and structure.type_id not in photon_battery_types:
            continue
        dist = get_distance(pylon_pos, structure.position)
        if dist <= PYLON_POWER_RADIUS:
            if structure.type_id in stargate_types:
                powers_stargate = True
            elif structure.type_id in photon_battery_types:
                powers_photon_or_battery = True

    if powers_stargate:
        return 1
    if powers_photon_or_battery:
        return 2
    return 3


def find_bile_target(ravager, priority_targets, other_targets, own_units, bile_effects,
                     enemy_structures, enemy_units=None):
    """Find the best Corrosive Bile target for a ravager, respecting multiple priority
    levels and already in-flight bile projectiles.

    Priority levels:
        1 - Pylon powering a Stargate
        2 - Pylon powering a Photon Cannon or Shield Battery
        3 - Other pylons and dangerous structures
        4 - Non-priority targets (other_targets)

    Targets that are already doomed by in-flight biles are skipped.
    Targets that are being healed/repaired/recharged are not considered doomed.
    """
    if enemy_units is None:
        enemy_units = []

    # --- Special case: Siege Tanks (highest threat, checked first) ---
    best_sieged_tank = None
    best_sieged_dist = 9999

    all_targets = list(priority_targets) + list(other_targets)
    for target in all_targets:
        if hasattr(target, 'type_id') and target.type_id == UnitTypeId.SIEGETANKSIEGED:
            if is_target_already_doomed(target, bile_effects, enemy_units, enemy_structures):
                continue
            d = get_distance(ravager.position, target.position)
            if d <= BILE_RANGE + 4.0 and d < best_sieged_dist:
                best_sieged_dist = d
                best_sieged_tank = target

    if best_sieged_tank is not None:
        return best_sieged_tank

    # --- Split priority_targets into pylons and dangerous non-pylon structures ---
    pylons_priority1 = []  # power Stargate
    pylons_priority2 = []  # power Photon Cannon / Shield Battery
    pylons_priority3 = []  # other pylons
    dangerous_non_pylon = []  # dangerous structures that are not pylons

    for target in priority_targets:
        if not hasattr(target, 'type_id'):
            dangerous_non_pylon.append(target)
            continue
        if target.type_id == UnitTypeId.PYLON:
            prio = get_pylon_priority(target, enemy_structures)
            if prio == 1:
                pylons_priority1.append(target)
            elif prio == 2:
                pylons_priority2.append(target)
            else:
                pylons_priority3.append(target)
        else:
            dangerous_non_pylon.append(target)

    def find_best_in_list(targets, max_range):
        """Return the closest alive target within max_range that is not already doomed."""
        best = None
        lower_dist = 9999
        for pot_target in targets:
            if is_target_already_doomed(pot_target, bile_effects, enemy_units, enemy_structures):
                continue
            dist = get_distance(ravager.position, pot_target.position)
            if dist <= max_range and dist < lower_dist:
                lower_dist = dist
                best = pot_target
        return best

    # Priority 1: pylons powering Stargates
    result = find_best_in_list(pylons_priority1, BILE_RANGE + 4.0)
    if result is not None:
        return result

    # Priority 2: pylons powering Photon Cannons / Shield Batteries
    result = find_best_in_list(pylons_priority2, BILE_RANGE + 3.5)
    if result is not None:
        return result

    # Priority 3: other pylons + dangerous non-pylon structures
    priority3_targets = pylons_priority3 + dangerous_non_pylon
    result = find_best_in_list(priority3_targets, BILE_RANGE + 3.0)
    if result is not None:
        return result

    # Priority 4: non-priority targets (other_targets)
    best_target = None
    best_dist = 9999
    for target in other_targets:
        if is_target_already_doomed(target, bile_effects, enemy_units, enemy_structures):
            continue
        d = get_distance(ravager.position, target.position)
        if d <= BILE_RANGE and d < best_dist:
            target_pos = target.position
            safe = True
            for unit in own_units:
                if unit.tag == ravager.tag:
                    continue
                dist_to_unit = get_distance(target_pos, unit.position)
                if dist_to_unit <= unit.radius + 3.5:
                    safe = False
                    break
            if safe:
                best_dist = d
                best_target = target

    return best_target


def get_priority_targets(enemy_structures, enemy_units):
    """Get static defense structures and burrowed enemy units that are priority targets."""
    result = []
    for s in enemy_structures:
        if s.type_id in STATIC_DEFENSE_RANGES or s.type_id == UnitTypeId.PYLON:
            result.append(s)
    for u in enemy_units:
        if u.is_burrowed:  # requires detection :(
            result.append(u)
    return result


def get_dangerous_structures(enemy_structures):
    """Get structures that can attack ground units and are currently active.

    Excludes:
        - SporeCrawler (does not attack ground)
        - PhotonCannon without power (is_powered == False)
        - Empty Bunkers (no units inside)
        - Structures still under construction (build_progress < 1.0)
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
        priority_targets = get_priority_targets(enemy_structures, enemy_units)

        # Extract only Corrosive Bile effects once and reuse throughout
        bile_effects = [
            effect for effect in bot.state.effects
            if effect.id == EffectId.RAVAGERCORROSIVEBILECP
        ]

        other_bile_targets = []
        for s in enemy_structures:
            if s not in priority_targets:
                other_bile_targets.append(s)

        real_enemies = [u for u in enemy_units if not u.is_hallucination]
        ground_enemies = [u for u in real_enemies if not u.is_flying]

        # Manage Ravagers
        for ravager in ravagers:
            ravager_critical_health = ravager.health < ravager.health_max * 0.4
            ravager_low_health = ravager.health < ravager.health_max * 0.6
            ravager_normal_health = ravager.health < ravager.health_max * 0.8
            handled = False
            closest_danger = None
            can_cast_bile = await bot.can_cast(ravager, AbilityId.EFFECT_CORROSIVEBILE, only_check_energy_and_cooldown=True)

            min_danger_dist = 9999
            for struct in dangerous_structures:
                d = get_distance(ravager.position, struct.position)
                if d < min_danger_dist:
                    min_danger_dist = d
                    closest_danger = struct

            min_dist = 10.0
            if ravager_low_health:
                min_dist = 15.0

            if can_cast_bile:
                if not ravager_normal_health:
                    min_dist = 8.5
                elif not ravager_low_health:
                    min_dist = 9.5
                elif not ravager_critical_health:
                    min_dist = 11.0
                else:
                    min_dist = 15.0

                if (closest_danger is not None) and (not closest_danger.is_visible) and (not ravager_normal_health):
                    min_dist = 4.0

            # 1. Strict distance check — stay outside dangerous structure range
            if (closest_danger is not None) and (min_danger_dist < min_dist):
                safe_pos = go_from_point(
                    unit_position=ravager.position,
                    dangerous_position=closest_danger.position,
                    dist=min(2, 15.0 - min_danger_dist)
                )
                bot.action_registry.submit_action(tag=ravager.tag,
                                                  action=lambda r=ravager, p=safe_pos: r.move(p),
                                                  priority=ActionPriority.HIGH,
                                                  source="RavagerManager")
                handled = True

            # 2. Bile casting (only when safe)
            if not handled and (len(priority_targets) > 0 or len(other_bile_targets) > 0 or len(real_enemies) > 0):
                own_units = list(ravagers) + list(roaches)
                bile_target = find_bile_target(
                    ravager,
                    priority_targets,
                    other_bile_targets + real_enemies,
                    own_units,
                    bile_effects,
                    enemy_structures,
                    enemy_units=enemy_units
                )
                if bile_target is not None:
                    if can_cast_bile:
                        if get_distance(ravager.position, bile_target.position) < (BILE_RANGE - 1):
                            bile_position = bile_target.position
                        else:
                            bile_position = go_towards_point(
                                unit_position=bile_target.position,
                                target_position=ravager.position,
                                dist=bile_target.radius + 0.2
                            )
                        safe_cast = True
                        for unit in own_units:
                            if unit.tag == ravager.tag:
                                continue
                            dist_to_unit = get_distance(bile_position, unit.position)
                            if dist_to_unit <= unit.radius + 0.5:
                                safe_cast = False
                                break
                        if safe_cast:
                            bot.action_registry.submit_action(
                                tag=ravager.tag,
                                action=lambda r=ravager, ab=AbilityId.EFFECT_CORROSIVEBILE, p=bile_position: r(ab, p),
                                priority=ActionPriority.HIGH + 1,
                                source="RavagerManager"
                            )
                            handled = True

            # 3. Stutter-step micro against ground enemies
            if not handled:
                closest_enemy = find_closest_enemy(ravager, ground_enemies)
                if closest_enemy is not None:
                    danger_dist = 7.0
                    if ravager_critical_health:
                        danger_dist = 13.0
                    elif ravager_low_health:
                        danger_dist = 10.0
                    elif ravager_normal_health:
                        danger_dist = 8.5
                    dist_to_enemy = get_distance(ravager.position, closest_enemy.position)
                    if dist_to_enemy < danger_dist:
                        if ravager.weapon_ready and (not ravager_critical_health or dist_to_enemy < 7):
                            bot.action_registry.submit_action(
                                tag=ravager.tag,
                                action=lambda r=ravager, t=closest_enemy: r.attack(t),
                                priority=ActionPriority.HIGH,
                                source="RavagerManager"
                            )
                        else:
                            retreat_pos = calculate_retreat_position(
                                ravager.position, closest_enemy.position, retreat_dist=1.5
                            )
                            bot.action_registry.submit_action(
                                tag=ravager.tag,
                                action=lambda r=ravager, p=retreat_pos: r.move(p),
                                priority=ActionPriority.HIGH + 1,
                                source="RavagerManager"
                            )
                        handled = True

            # 4. Wait safely outside danger zone (prevent macro from walking into cannons)
            critic_distance = 10.0
            if ravager_low_health:
                critic_distance = 15.0

            if can_cast_bile:
                if not ravager_normal_health:
                    critic_distance = 7.5
                elif not ravager_low_health:
                    critic_distance = 8.0
                elif not ravager_critical_health:
                    critic_distance = 8.5
                else:
                    critic_distance = 12.0

                if (closest_danger is not None) and (not closest_danger.is_visible) and (not ravager_normal_health):
                    critic_distance = 3.0

            if (not handled) and (closest_danger is not None) and (min_danger_dist < critic_distance):
                bot.action_registry.submit_action(tag=ravager.tag,
                                                  action=lambda r=ravager: r.stop(),
                                                  priority=ActionPriority.HIGH,
                                                  source="RavagerManager")
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

            # Strict distance check for roaches
            if closest_danger is not None and min_danger_dist < 12.0:
                safe_pos = go_from_point(
                    unit_position=roach.position,
                    dangerous_position=closest_danger.position,
                    dist=2.0
                )
                bot.action_registry.submit_action(tag=roach.tag,
                                                  action=lambda r=roach, p=safe_pos: r.move(p),
                                                  priority=ActionPriority.HIGH,
                                                  source="RavagerManager")
                handled = True

            if not handled:
                closest_enemy = find_closest_enemy(roach, ground_enemies)
                if closest_enemy is not None:
                    dist_to_enemy = get_distance(roach.position, closest_enemy.position)
                    if dist_to_enemy < 7:
                        if roach.weapon_ready:
                            bot.action_registry.submit_action(
                                tag=roach.tag,
                                action=lambda r=roach, t=closest_enemy: r.attack(t),
                                priority=ActionPriority.NORMAL + 1,
                                source="RavagerManager"
                            )
                        else:
                            retreat_pos = calculate_retreat_position(
                                roach.position, closest_enemy.position, retreat_dist=1.0
                            )
                            bot.action_registry.submit_action(
                                tag=roach.tag,
                                action=lambda r=roach, p=retreat_pos: r.move(p),
                                priority=ActionPriority.NORMAL + 1,
                                source="RavagerManager"
                            )
                        handled = True

            # Wait safely outside danger zone
            if not handled and closest_danger is not None and min_danger_dist < 15.0:
                bot.action_registry.submit_action(tag=roach.tag,
                                                  action=lambda r=roach: r.stop(),
                                                  priority=ActionPriority.NORMAL,
                                                  source="RavagerManager")
                handled = True

            if handled:
                handled_tags.add(roach.tag)

        return handled_tags
