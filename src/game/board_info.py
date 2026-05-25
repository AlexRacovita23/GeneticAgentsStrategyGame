from typing import List, Tuple

from src.game.board import Board


def get_valid_moves(
    board: Board,
    player_id: int,
) -> List[Tuple[Tuple[int, int], Tuple[int, int]]]:
    moves = []
    for pos in board.get_territories_for_player(player_id):
        territory = board.get(pos[0], pos[1])
        if territory.can_move_from():
            for neighbor in board.get_neighbors(pos[0], pos[1]):
                moves.append((pos, neighbor))
    return moves


def get_attack_targets(board: Board, player_id: int) -> List[Tuple[int, int]]:
    targets: set[Tuple[int, int]] = set()

    for pos in board.get_territories_for_player(player_id):
        territory = board.get(pos[0], pos[1])
        if territory.can_move_from():
            for neighbor in board.get_neighbors(pos[0], pos[1]):
                neighbor_territory = board.get(neighbor[0], neighbor[1])
                if neighbor_territory.owner != player_id:
                    targets.add(neighbor)

    return list(targets)


def get_flanking_options(
    board: Board,
    player_id: int,
    target: Tuple[int, int],
) -> List[Tuple[int, int]]:
    options = []
    target_row, target_col = target

    for neighbor in board.get_neighbors(target_row, target_col):
        territory = board.get(neighbor[0], neighbor[1])
        if territory.owner == player_id and territory.can_move_from():
            options.append(neighbor)

    return options


def count_enemy_troops_adjacent(board: Board, player_id: int, pos: Tuple[int, int]) -> int:
    total = 0
    for neighbor in board.get_neighbors(pos[0], pos[1]):
        territory = board.get(neighbor[0], neighbor[1])
        if territory.owner != player_id and territory.owner != -1:
            total += territory.troops
    return total


def count_friendly_neighbors(board: Board, player_id: int, pos: Tuple[int, int]) -> int:
    count = 0
    for neighbor in board.get_neighbors(pos[0], pos[1]):
        territory = board.get(neighbor[0], neighbor[1])
        if territory.owner == player_id:
            count += 1
    return count


def get_territory_connectivity(board: Board, player_id: int, pos: Tuple[int, int]) -> int:
    connectivity = 0
    for neighbor in board.get_neighbors(pos[0], pos[1]):
        territory = board.get(neighbor[0], neighbor[1])
        if territory.owner == player_id:
            connectivity += 1
            for second_neighbor in board.get_neighbors(neighbor[0], neighbor[1]):
                second_territory = board.get(second_neighbor[0], second_neighbor[1])
                if second_territory.owner == player_id:
                    connectivity += 0.5
    return int(connectivity)
