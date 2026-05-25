from dataclasses import dataclass
from typing import List, Optional

from src.game.player import GamePhase, Player


@dataclass
class TurnInfo:
    turn_number: int
    current_player_id: int
    phase: GamePhase
    reinforcements_available: int = 0


class TurnManager:

    def __init__(
        self,
        players: List[Player],
        reinforcement_rate: float = 1.0,
        min_reinforcement: int = 1,
    ):
        self.players = players
        self.reinforcement_rate = reinforcement_rate
        self.min_reinforcement = min_reinforcement

        self.turn_number: int = 0
        self.current_player_index: int = 0
        self.phase: GamePhase = GamePhase.REINFORCEMENT
        self.reinforcements_available: int = 0

    @property
    def current_player(self) -> Player:
        return self.players[self.current_player_index]

    @property
    def is_game_over(self) -> bool:
        return self.phase == GamePhase.GAME_OVER

    def get_turn_info(self) -> TurnInfo:
        return TurnInfo(
            turn_number=self.turn_number,
            current_player_id=self.current_player.id,
            phase=self.phase,
            reinforcements_available=self.reinforcements_available,
        )

    def calculate_reinforcements(self, territory_count: int) -> int:
        return max(
            self.min_reinforcement,
            int(territory_count * self.reinforcement_rate),
        )

    def start_reinforcement_phase(self, territory_count: int) -> None:
        self.phase = GamePhase.REINFORCEMENT
        self.reinforcements_available = self.calculate_reinforcements(territory_count)

    def spend_reinforcements(self, count: int) -> bool:
        if count <= 0 or count > self.reinforcements_available:
            return False
        self.reinforcements_available -= count
        return True

    def end_reinforcement_phase(self) -> bool:
        if self.phase != GamePhase.REINFORCEMENT:
            return False
        self.reinforcements_available = 0
        self.phase = GamePhase.ACTION
        return True

    def advance_turn(self) -> Optional[int]:
        start_index = self.current_player_index

        while True:
            self.current_player_index = (self.current_player_index + 1) % len(self.players)

            if self.current_player_index == 0:
                self.turn_number += 1

            if self.players[self.current_player_index].is_alive:
                return self.current_player.id

            if self.current_player_index == start_index:
                return None

    def set_game_over(self) -> None:
        self.phase = GamePhase.GAME_OVER
