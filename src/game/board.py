from dataclasses import dataclass
from typing import List, Tuple, Optional
from enum import Enum

from src.game.territory import Territory


class MoveResult(Enum):
    INVALID = "invalid"
    REINFORCED = "reinforced"
    CONQUERED = "conquered"
    REPELLED = "repelled"


@dataclass
class MoveOutcome:
    result: MoveResult
    troops_moved: int = 0
    troops_lost_attacker: int = 0
    troops_lost_defender: int = 0


class Board:
    def __init__(self, size: int = 5):
        self.size = size
        self.grid: List[List[Territory]] = [
            [Territory() for _ in range(size)]
            for _ in range(size)
        ]

    def get(self, row: int, col: int) -> Optional[Territory]:
        if 0 <= row < self.size and 0 <= col < self.size:
            return self.grid[row][col]
        return None

    def is_valid(self, row: int, col: int) -> bool:
        return 0 <= row < self.size and 0 <= col < self.size

    def get_neighbors(self, row: int, col: int) -> List[Tuple[int, int]]:
        directions = [(-1, 0), (1, 0), (0, -1), (0, 1)]
        neighbors = []

        for dr, dc in directions:
            new_row, new_col = row + dr, col + dc
            if self.is_valid(new_row, new_col):
                territory = self.grid[new_row][new_col]
                if not territory.is_blocked:
                    neighbors.append((new_row, new_col))

        return neighbors

    def are_adjacent(self, pos1: Tuple[int, int], pos2: Tuple[int, int]) -> bool:
        return pos2 in self.get_neighbors(pos1[0], pos1[1])

    def get_territories_for_player(self, player_id: int) -> List[Tuple[int, int]]:
        territories = []
        for row in range(self.size):
            for col in range(self.size):
                if self.grid[row][col].owner == player_id:
                    territories.append((row, col))
        return territories

    def count_troops_for_player(self, player_id: int) -> int:
        total = 0
        for row in range(self.size):
            for col in range(self.size):
                if self.grid[row][col].owner == player_id:
                    total += self.grid[row][col].troops
        return total

    def move_troops(
        self,
        from_pos: Tuple[int, int],
        to_pos: Tuple[int, int],
        troop_count: int,
        combat_resolver,
    ) -> MoveOutcome:
        from_row, from_col = from_pos
        to_row, to_col = to_pos

        if not self.is_valid(from_row, from_col) or not self.is_valid(to_row, to_col):
            return MoveOutcome(result=MoveResult.INVALID)

        if not self.are_adjacent(from_pos, to_pos):
            return MoveOutcome(result=MoveResult.INVALID)

        source = self.grid[from_row][from_col]
        dest = self.grid[to_row][to_col]

        if source.is_blocked or dest.is_blocked:
            return MoveOutcome(result=MoveResult.INVALID)

        if source.owner == -1:
            return MoveOutcome(result=MoveResult.INVALID)

        if not source.can_move_from():
            return MoveOutcome(result=MoveResult.INVALID)

        troops_moved = source.remove_troops(troop_count)

        if troops_moved == 0:
            return MoveOutcome(result=MoveResult.INVALID)

        if dest.owner == source.owner:
            dest.add_troops(troops_moved)
            dest.troops_moved_this_turn += troops_moved
            return MoveOutcome(
                result=MoveResult.REINFORCED,
                troops_moved=troops_moved,
            )
        else:
            return combat_resolver.resolve(source, dest, troops_moved)

    def __repr__(self) -> str:
        lines = []
        for row in self.grid:
            cells = []
            for t in row:
                if t.is_blocked:
                    cells.append("  WALL  ")
                else:
                    cells.append(f"{t.owner if t.owner != -1 else 'N'}:{t.troops:2d}")
            lines.append(" | ".join(cells))
        return "\n".join(lines)
