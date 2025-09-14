import pytest
from sc2.position import Point2
from src.utils.coordinate_functions import go_from_point, go_towards_point, get_distance

class TestCoordinateFunctions:
    def test_go_from_point_horizontal(self):
        unit_pos = Point2((3, 1))
        danger_pos = Point2((1, 1))
        result = go_from_point(unit_pos, danger_pos, 1)

        expected = Point2((4, 1))
        assert abs(result - expected) < 0.001

    def test_go_from_point_vertical(self):
        unit_pos = Point2((1, 3))
        danger_pos = Point2((1, 1))
        result = go_from_point(unit_pos, danger_pos, 1)

        expected = Point2((1, 4))
        assert abs(result - expected) < 0.001

    def test_go_from_point_diagonal(self):
        unit_pos = Point2((2, 2))
        danger_pos = Point2((1, 1))
        result = go_from_point(unit_pos, danger_pos, 2 ** 0.5)

        expected = Point2((3, 3))
        assert abs(result - expected) < 0.001

    def test_go_towards_point_horizontal(self):
        unit_pos = Point2((3, 1))
        target_pos = Point2((1, 1))
        result = go_towards_point(unit_pos, target_pos, 1)

        expected = Point2((2, 1))
        assert abs(result - expected) < 0.001

    def test_go_towards_point_vertical(self):
        unit_pos = Point2((1, 3))
        target_pos = Point2((1, 1))
        result = go_towards_point(unit_pos, target_pos, 1)

        expected = Point2((1, 2))
        assert abs(result - expected) < 0.001
        
    def test_go_towards_point_diagonal(self):
        unit_pos = Point2((3, 3))
        danger_pos = Point2((1, 1))
        result = go_towards_point(unit_pos, danger_pos, 2 ** 0.5)

        expected = Point2((2, 2))
        assert abs(result - expected) < 0.001

    def test_go_from_point_same_position(self):
        unit_pos = Point2((1, 1))
        danger_pos = Point2((1, 1))
        result = go_from_point(unit_pos, danger_pos, 1)
        assert result != unit_pos
        distance = get_distance(unit_pos, result)
        assert abs(distance - 1) < 0.001

    def test_go_towards_point_same_position(self):
        unit_pos = Point2((0, 0))
        target_pos = Point2((0, 0))
        result = go_towards_point(unit_pos, target_pos, 1)

        assert result != unit_pos
        distance = get_distance(unit_pos, result)
        assert abs(distance - 1) < 0.001



