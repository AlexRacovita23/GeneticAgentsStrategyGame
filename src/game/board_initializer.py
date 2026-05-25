import random
from typing import Tuple, List

from src.game.board import Board


class BoardInitializer:

    def __init__(self, board_size: int, num_players: int, starting_troops: int = 10):
        self.board_size = board_size
        self.num_players = num_players
        self.starting_troops = starting_troops

    def setup_random_start(self, board: Board, player_ids: List[int], seed: int = None) -> None:
        if seed is not None:
            random.seed(seed)

        start_positions = self._get_corner_positions()

        for i, player_id in enumerate(player_ids):
            if i < len(start_positions):
                row, col = start_positions[i]
                territory = board.get(row, col)
                if territory:
                    territory.set_owner(player_id, self.starting_troops)

    def _get_corner_positions(self) -> List[Tuple[int, int]]:
        size = self.board_size
        return [
            (0, 0),
            (size - 1, size - 1),
            (0, size - 1),
            (size - 1, 0),
            (0, size // 2),
            (size - 1, size // 2),
            (size // 2, 0),
            (size // 2, size - 1),
        ]

    def add_neutral_territories(self, board: Board, count: int = None) -> None:
        if count is None:
            count = (self.board_size * self.board_size) // 4

        available_positions = [
            (r, c)
            for r in range(self.board_size)
            for c in range(self.board_size)
            if board.get(r, c) and board.get(r, c).owner == -1 and not board.get(r, c).is_blocked
        ]

        random.shuffle(available_positions)

        for i, (row, col) in enumerate(available_positions[:count]):
            territory = board.get(row, col)
            if territory:
                neutral_troops = random.randint(1, 5)
                territory.troops = neutral_troops