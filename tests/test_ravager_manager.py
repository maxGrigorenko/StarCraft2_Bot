import pytest
from unittest.mock import MagicMock, AsyncMock
from sc2.position import Point2
from sc2.ids.unit_typeid import UnitTypeId
from sc2.ids.ability_id import AbilityId
from src.utils.coordinate_functions import go_from_point, go_towards_point, get_distance
from src.managers.ravager_manager import (
    RavagerManager,
    is_in_static_defense_range,
    find_safe_bile_position,
    calculate_retreat_position,
    find_closest_enemy,
    find_bile_target,
    get_priority_structures,
    get_dangerous_structures,
    STATIC_DEFENSE_RANGES,
    BILE_RANGE,
    BILE_SAFE_MARGIN,
)


def make_mock_unit(type_id, position, tag=1, weapon_ready=True, is_flying=False,
                   is_hallucination=False, health=100, health_max=100):
    unit = MagicMock()
    unit.type_id = type_id
    unit.position = Point2(position)
    unit.tag = tag
    unit.weapon_ready = weapon_ready
    unit.is_flying = is_flying
    unit.is_hallucination = is_hallucination
    unit.health = health
    unit.health_max = health_max
    unit.is_ready = True
    return unit


def make_mock_structure(type_id, position, build_progress=1.0, is_detector=False):
    struct = MagicMock()
    struct.type_id = type_id
    struct.position = Point2(position)
    struct.build_progress = build_progress
    struct.is_detector = is_detector
    return struct


class TestIsInStaticDefenseRange:
    def test_unit_inside_cannon_range(self):
        cannon = make_mock_structure(UnitTypeId.PHOTONCANNON, (10, 10))
        # Cannon range is 7.0, unit at distance 5
        unit_pos = Point2((15, 10))
        assert is_in_static_defense_range(unit_pos, cannon) is True

    def test_unit_outside_cannon_range(self):
        cannon = make_mock_structure(UnitTypeId.PHOTONCANNON, (10, 10))
        # Cannon range is 7.0, unit at distance 10
        unit_pos = Point2((20, 10))
        assert is_in_static_defense_range(unit_pos, cannon) is False

    def test_unit_at_exact_range_boundary(self):
        cannon = make_mock_structure(UnitTypeId.PHOTONCANNON, (10, 10))
        # Cannon range is 7.0, unit at exactly 7.0
        unit_pos = Point2((17, 10))
        assert is_in_static_defense_range(unit_pos, cannon) is True

    def test_unit_outside_with_margin(self):
        cannon = make_mock_structure(UnitTypeId.PHOTONCANNON, (10, 10))
        # Distance = 7.5, range = 7.0, margin = 1.0 => 7.5 <= 8.0 => True
        unit_pos = Point2((17.5, 10))
        assert is_in_static_defense_range(unit_pos, cannon, margin=1.0) is True

    def test_bunker_range(self):
        bunker = make_mock_structure(UnitTypeId.BUNKER, (10, 10))
        # Bunker range is 6.0
        unit_pos = Point2((15, 10))  # distance 5
        assert is_in_static_defense_range(unit_pos, bunker) is True

        unit_pos_far = Point2((17, 10))  # distance 7
        assert is_in_static_defense_range(unit_pos_far, bunker) is False

    def test_spine_crawler_range(self):
        spine = make_mock_structure(UnitTypeId.SPINECRAWLER, (10, 10))
        # Spine range is 7.0
        unit_pos = Point2((16, 10))  # distance 6
        assert is_in_static_defense_range(unit_pos, spine) is True


class TestFindSafeBilePosition:
    def test_safe_when_no_structures(self):
        unit_pos = Point2((10, 10))
        target_pos = Point2((20, 10))
        result = find_safe_bile_position(unit_pos, target_pos, [])
        assert result is None

    def test_safe_when_outside_all_ranges(self):
        cannon = make_mock_structure(UnitTypeId.PHOTONCANNON, (30, 30))
        unit_pos = Point2((10, 10))
        target_pos = Point2((20, 10))
        result = find_safe_bile_position(unit_pos, target_pos, [cannon])
        assert result is None

    def test_returns_position_when_in_range(self):
        cannon = make_mock_structure(UnitTypeId.PHOTONCANNON, (10, 10))
        # Cannon range 7.0 + margin 1.0 = 8.0. Unit at distance 5
        unit_pos = Point2((15, 10))
        target_pos = Point2((10, 10))
        result = find_safe_bile_position(unit_pos, target_pos, [cannon])
        assert result is not None
        # The result should be further from the cannon than the attack range + margin
        dist_from_cannon = get_distance(result, cannon.position)
        assert dist_from_cannon >= STATIC_DEFENSE_RANGES[UnitTypeId.PHOTONCANNON] + BILE_SAFE_MARGIN - 0.5


class TestCalculateRetreatPosition:
    def test_retreat_horizontal(self):
        unit_pos = Point2((5, 5))
        enemy_pos = Point2((3, 5))
        result = calculate_retreat_position(unit_pos, enemy_pos, retreat_dist=2.0)
        # Should move away from enemy (to the right)
        assert result[0] > unit_pos[0]
        dist = get_distance(unit_pos, result)
        assert abs(dist - 2.0) < 0.001

    def test_retreat_vertical(self):
        unit_pos = Point2((5, 5))
        enemy_pos = Point2((5, 3))
        result = calculate_retreat_position(unit_pos, enemy_pos, retreat_dist=1.5)
        assert result[1] > unit_pos[1]
        dist = get_distance(unit_pos, result)
        assert abs(dist - 1.5) < 0.001

    def test_retreat_diagonal(self):
        unit_pos = Point2((5, 5))
        enemy_pos = Point2((3, 3))
        result = calculate_retreat_position(unit_pos, enemy_pos, retreat_dist=2.0)
        assert result[0] > unit_pos[0]
        assert result[1] > unit_pos[1]
        dist = get_distance(unit_pos, result)
        assert abs(dist - 2.0) < 0.001

    def test_retreat_same_position(self):
        unit_pos = Point2((5, 5))
        enemy_pos = Point2((5, 5))
        result = calculate_retreat_position(unit_pos, enemy_pos, retreat_dist=1.0)
        # Should still return a point at distance 1.0
        dist = get_distance(unit_pos, result)
        assert abs(dist - 1.0) < 0.001


class TestFindClosestEnemy:
    def test_single_enemy(self):
        unit = make_mock_unit(UnitTypeId.RAVAGER, (10, 10))
        enemy = make_mock_unit(UnitTypeId.ZEALOT, (12, 10))
        result = find_closest_enemy(unit, [enemy])
        assert result == enemy

    def test_multiple_enemies(self):
        unit = make_mock_unit(UnitTypeId.RAVAGER, (10, 10))
        enemy_far = make_mock_unit(UnitTypeId.ZEALOT, (20, 10))
        enemy_close = make_mock_unit(UnitTypeId.STALKER, (11, 10))
        result = find_closest_enemy(unit, [enemy_far, enemy_close])
        assert result == enemy_close

    def test_no_enemies(self):
        unit = make_mock_unit(UnitTypeId.RAVAGER, (10, 10))
        result = find_closest_enemy(unit, [])
        assert result is None


class TestFindBileTarget:
    def test_priority_target_in_range(self):
        ravager = make_mock_unit(UnitTypeId.RAVAGER, (10, 10))
        cannon = make_mock_structure(UnitTypeId.PHOTONCANNON, (15, 10))  # distance 5
        stalker = make_mock_unit(UnitTypeId.STALKER, (12, 10))  # distance 2
        result = find_bile_target(ravager, [cannon], [stalker], own_units=[])
        assert result == cannon  # priority target preferred

    def test_no_priority_falls_back_to_other(self):
        ravager = make_mock_unit(UnitTypeId.RAVAGER, (10, 10))
        stalker = make_mock_unit(UnitTypeId.STALKER, (12, 10))
        result = find_bile_target(ravager, [], [stalker], own_units=[])
        assert result == stalker

    def test_target_out_of_range(self):
        ravager = make_mock_unit(UnitTypeId.RAVAGER, (10, 10))
        cannon = make_mock_structure(UnitTypeId.PHOTONCANNON, (30, 10))  # distance 20
        result = find_bile_target(ravager, [cannon], [], own_units=[])
        assert result is None

    def test_closest_priority_target_selected(self):
        ravager = make_mock_unit(UnitTypeId.RAVAGER, (10, 10))
        cannon_far = make_mock_structure(UnitTypeId.PHOTONCANNON, (18, 10))  # distance 8
        cannon_close = make_mock_structure(UnitTypeId.PHOTONCANNON, (14, 10))  # distance 4
        result = find_bile_target(ravager, [cannon_far, cannon_close], [], own_units=[])
        assert result == cannon_close

    def test_no_targets(self):
        ravager = make_mock_unit(UnitTypeId.RAVAGER, (10, 10))
        result = find_bile_target(ravager, [], [], own_units=[])
        assert result is None


class TestGetPriorityStructures:
    def test_filters_static_defense(self):
        cannon = make_mock_structure(UnitTypeId.PHOTONCANNON, (10, 10))
        nexus = make_mock_structure(UnitTypeId.NEXUS, (20, 20))
        spine = make_mock_structure(UnitTypeId.SPINECRAWLER, (15, 15))
        result = get_priority_structures([cannon, nexus, spine])
        assert cannon in result
        assert spine in result
        assert nexus not in result

    def test_empty_input(self):
        result = get_priority_structures([])
        assert len(result) == 0


class TestGetDangerousStructures:
    def test_filters_ground_attackers(self):
        cannon = make_mock_structure(UnitTypeId.PHOTONCANNON, (10, 10))
        bunker = make_mock_structure(UnitTypeId.BUNKER, (15, 15))
        spore = make_mock_structure(UnitTypeId.SPORECRAWLER, (20, 20))  # not ground-dangerous
        pylon = make_mock_structure(UnitTypeId.PYLON, (25, 25))
        result = get_dangerous_structures([cannon, bunker, spore, pylon])
        assert cannon in result
        assert bunker in result
        assert spore not in result
        assert pylon not in result


