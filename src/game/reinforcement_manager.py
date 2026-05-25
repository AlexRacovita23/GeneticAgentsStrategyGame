from typing import Tuple

from src.game.board import Board
from src.game.player import GamePhase
from src.game.turn_manager import TurnManager


class ReinforcementManager:
    def __init__(self, board: Board, turn_manager: TurnManager):
        self._board = board
        self._turn_manager = turn_manager

    def place(self, position: Tuple[int, int], count: int) -> bool:
        if self._turn_manager.phase != GamePhase.REINFORCEMENT:
            return False

        row, col = position
        territory = self._board.get(row, col)

        if territory is None or territory.owner != self._turn_manager.current_player.id:
            return False

        if not self._turn_manager.spend_reinforcements(count):
            return False

        territory.add_troops(count)
        return True

    def reset(self) -> None:
        territory_count = len(
            self._board.get_territories_for_player(self._turn_manager.current_player.id)
        )
        self._turn_manager.start_reinforcement_phase(territory_count)
