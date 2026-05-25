from dataclasses import dataclass, field
from enum import Enum

from src.game.combat import CombatConfig


class GamePhase(Enum):
    REINFORCEMENT = "reinforcement"
    ACTION = "action"
    GAME_OVER = "game_over"


@dataclass
class Player:
    id: int
    name: str = ""
    is_alive: bool = True
    is_ai: bool = False

    def __post_init__(self):
        if not self.name:
            self.name = f"Player {self.id}"


@dataclass
class GameConfig:
    board_size: int = 8
    num_players: int = 2
    starting_troops: int = 10
    reinforcement_rate: float = 1.0
    min_reinforcement: int = 1
    domination_threshold: float = 0.75
    max_turns: int = 100
    combat_config: CombatConfig = field(default_factory=CombatConfig)
