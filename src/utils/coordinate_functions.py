import sc2.position

def sign(x):
    if x > 0:
        return 1
    elif x == 0:
        return 0
    else:
        return -1

def find_mining_positions(hatchery, mineral_field):
    k, b = create_straight(hatchery.position, mineral_field.position)

    dist_from_hatchery = 1.775  # drone_radius + hatchery_radius - 1.4 = 3.125 - 1.4 = 1.775
    delta = dist_from_hatchery / (k ** 2 + 1) ** 0.5
    x1, x2 = hatchery.position[0] + delta, hatchery.position[0] - delta
    y1, y2 = x1 * k + b, x2 * k + b

    d1 = get_distance([x1, y1], mineral_field.position)
    d2 = get_distance([x2, y2], mineral_field.position)

    if d1 < d2:
        hatchery_position = sc2.position.Point2([x1, y1])
    else:
        hatchery_position = sc2.position.Point2([x2, y2])

    dist_from_mineral = 0.4
    delta = dist_from_mineral / (k ** 2 + 1) ** 0.5
    x1, x2 = mineral_field.position[0] + delta, mineral_field.position[0] - delta
    y1, y2 = x1 * k + b, x2 * k + b

    d1 = get_distance([x1, y1], hatchery.position)
    d2 = get_distance([x2, y2], hatchery.position)

    if d1 < d2:
        mineral_position = sc2.position.Point2([x1, y1])
    else:
        mineral_position = sc2.position.Point2([x2, y2])

    return hatchery_position, mineral_position


def get_distance(obj1, obj2):  # unit - unit; obj - point2
    return ((obj1[0] - obj2[0]) ** 2 + (obj1[1] - obj2[1]) ** 2) ** 0.5


def create_straight(point1, point2):
    x1, y1 = point1[0], point1[1]
    x2, y2 = point2[0], point2[1]

    if x1 == x2 or x1 == 0:
        return 0, 0

    b = (y1 * x2 - y2 * x1) / (x2 - x1)
    k = (y1 - b) / x1
    return k, b


def go_from_point(unit_position, dangerous_position, dist):  # not accurate

    k, b = create_straight(unit_position, dangerous_position)

    if k == b == 0:
        if unit_position[1] >= dangerous_position[1]:
            y = unit_position[1] + dist
        else:
            y = unit_position[1] - dist
        return sc2.position.Point2([unit_position[0], y])

    delta_x = sign(dist) * (dist ** 2 / (k ** 2 + 1)) ** 0.5

    if unit_position[0] > dangerous_position[0]:
        x = unit_position[0] + delta_x
    else:
        x = unit_position[0] - delta_x

    y = k * x + b
    return sc2.position.Point2([x, y])

def go_towards_point(unit_position, target_position, dist):
    return go_from_point(unit_position, target_position, -dist)

