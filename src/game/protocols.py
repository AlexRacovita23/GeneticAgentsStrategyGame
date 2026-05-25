from typing import Protocol, Tuple, List, Optional, TYPE_CHECKING


if TYPE_CHECKING:
    from src.game.win_condition import WinCondition
    from src.game.territory import Territory
    from src.game.board import Board

from src.game.board import MoveOutcome


class CombatResolverProtocol(Protocol):

    def resolve(self, source: "Territory", dest: "Territory", attackers: int) -> MoveOutcome:
        ...


class AgentProtocol(Protocol):

    player_id: int

    def take_turn(self, game_state) -> None:
        ...


class WinConditionCheckerProtocol(Protocol):

    def check_all_conditions(
        self,
        board: "Board",
        alive_players: List[int],
        turn: int
    ) -> Tuple[Optional[int], Optional["WinCondition"]]:
        ...


class BoardInitializerProtocol(Protocol):

    def setup_random_start(self, board: "Board", player_ids: List[int], seed: int = None) -> None:
        ...

    def add_neutral_territories(self, board: "Board") -> None:
        ...
