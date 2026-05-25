from typing import List, Optional, Tuple
from enum import Enum

from src.game.board import Board


class WinCondition(Enum):
    ELIMINATION = "elimination"
    DOMINATION = "domination"
    TURN_LIMIT = "turn_limit"


class WinConditionChecker:

    def __init__(self, domination_threshold: float = 0.75, max_turns: int = 100):
        self.domination_threshold = domination_threshold
        self.max_turns = max_turns

    def check_elimination(self, alive_players: List[int]) -> Optional[int]:
        if len(alive_players) == 1:
            return alive_players[0]
        return None

    def check_domination(self, board: Board, alive_players: List[int]) -> Optional[int]:
        total_territories = board.size ** 2
        threshold = int(total_territories * self.domination_threshold)

        for player_id in alive_players:
            territories = len(board.get_territories_for_player(player_id))
            if territories >= threshold:
                return player_id

        return None

    def check_turn_limit(self, board: Board, alive_players: List[int], current_turn: int) -> Optional[int]:
        if self.max_turns <= 0:
            return None

        if current_turn <= self.max_turns:
            return None

        best_player = None
        best_count = -1

        for player_id in alive_players:
            count = len(board.get_territories_for_player(player_id))
            if count > best_count:
                best_count = count
                best_player = player_id

        return best_player

    def check_all_conditions(
        self,
        board: Board,
        alive_players: List[int],
        current_turn: int
    ) -> Tuple[Optional[int], Optional[WinCondition]]:
        winner = self.check_elimination(alive_players)
        if winner is not None:
            return winner, WinCondition.ELIMINATION

        if len(alive_players) == 0:
            return None, WinCondition.ELIMINATION

        winner = self.check_domination(board, alive_players)
        if winner is not None:
            return winner, WinCondition.DOMINATION

        winner = self.check_turn_limit(board, alive_players, current_turn)
        if winner is not None:
            return winner, WinCondition.TURN_LIMIT

        return None, None