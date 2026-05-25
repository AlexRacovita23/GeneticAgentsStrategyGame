from typing import Dict, List, Optional, Tuple

from src.game.action_manager import ActionManager
from src.game.board import Board, MoveOutcome, MoveResult
from src.game.board_initializer import BoardInitializer
from src.game.combat import (
    CombatResolver,
    FlankingOutcome,
)
from src.game.player import GameConfig, GamePhase, Player
from src.game.reinforcement_manager import ReinforcementManager
from src.game.territory import Territory
from src.game.turn_manager import TurnInfo, TurnManager
from src.game.win_condition import WinCondition, WinConditionChecker


class GameState:
    def __init__(
        self,
        config: GameConfig = None,
        combat_resolver: CombatResolver = None,
        win_checker: WinConditionChecker = None,
        board_initializer: BoardInitializer = None,
    ):
        self.config = config or GameConfig()

        self.board = Board(size=self.config.board_size)
        self.players: List[Player] = [
            Player(id=i) for i in range(self.config.num_players)
        ]
        self.winner: Optional[int] = None
        self.win_condition: Optional[WinCondition] = None

        self._combat_resolver = combat_resolver or CombatResolver(self.config.combat_config)
        self._win_checker = win_checker or WinConditionChecker(
            domination_threshold=self.config.domination_threshold,
            max_turns=self.config.max_turns,
        )
        self._board_initializer = board_initializer or BoardInitializer(
            board_size=self.config.board_size,
            num_players=self.config.num_players,
            starting_troops=self.config.starting_troops,
        )

        self._turn_manager = TurnManager(
            players=self.players,
            reinforcement_rate=self.config.reinforcement_rate,
            min_reinforcement=self.config.min_reinforcement,
        )
        self._reinforcement_manager = ReinforcementManager(
            board=self.board,
            turn_manager=self._turn_manager,
        )
        self._action_manager = ActionManager(
            board=self.board,
            turn_manager=self._turn_manager,
            combat_resolver=self._combat_resolver,
            combat_config=self.config.combat_config,
        )

    def setup_random_start(self, seed: int = None) -> None:
        player_ids = [p.id for p in self.players]
        self._board_initializer.setup_random_start(self.board, player_ids, seed)
        self._board_initializer.add_neutral_territories(self.board)

        self._turn_manager.turn_number = 1
        territory_count = len(self.board.get_territories_for_player(self.current_player.id))
        self._turn_manager.start_reinforcement_phase(territory_count)

    @property
    def current_player(self) -> Player:
        return self._turn_manager.current_player

    @property
    def is_game_over(self) -> bool:
        return self._turn_manager.is_game_over

    @property
    def turn_number(self) -> int:
        return self._turn_manager.turn_number

    @property
    def phase(self) -> GamePhase:
        return self._turn_manager.phase

    @property
    def reinforcements_available(self) -> int:
        return self._turn_manager.reinforcements_available

    def get_turn_info(self) -> TurnInfo:
        return self._turn_manager.get_turn_info()

    def get_player_stats(self, player_id: int) -> Dict:
        return {
            "player_id": player_id,
            "territories": len(self.board.get_territories_for_player(player_id)),
            "troops": self.board.count_troops_for_player(player_id),
            "is_alive": self.players[player_id].is_alive,
        }

    def get_all_stats(self) -> List[Dict]:
        return [self.get_player_stats(p.id) for p in self.players]

    def get_mobile_troops(
        self,
        row: int,
        col: int,
        immobile_troops: Dict[Tuple[int, int], int],
    ) -> int:
        territory = self.board.get(row, col)
        if territory is None:
            return 0
        return max(0, territory.available_troops - immobile_troops.get((row, col), 0))


    def place_reinforcements(self, position: Tuple[int, int], count: int) -> bool:
        return self._reinforcement_manager.place(position, count)

    def end_reinforcement_phase(self) -> bool:
        return self._turn_manager.end_reinforcement_phase()


    def move_troops(
        self,
        from_pos: Tuple[int, int],
        to_pos: Tuple[int, int],
        troop_count: int,
    ) -> MoveOutcome:
        result = self._action_manager.move_troops(from_pos, to_pos, troop_count)

        if result.result in (MoveResult.CONQUERED, MoveResult.REPELLED):
            self._check_eliminations()
            self._check_win_conditions()

        return result

    def coordinated_attack(
        self,
        attacks: List[Tuple[Tuple[int, int], int]],
        target: Tuple[int, int],
    ) -> FlankingOutcome:
        result = self._action_manager.coordinated_attack(attacks, target)

        self._check_eliminations()
        self._check_win_conditions()

        return result


    def end_turn(self) -> None:
        if self.is_game_over:
            return

        self._action_manager.reset_movement_counters()

        next_player_id = self._turn_manager.advance_turn()

        if next_player_id is None:
            self._check_win_conditions()
            return

        self._check_turn_limit()
        if self.is_game_over:
            return

        territory_count = len(self.board.get_territories_for_player(next_player_id))
        self._turn_manager.start_reinforcement_phase(territory_count)


    def _check_eliminations(self) -> None:
        for player in self.players:
            if player.is_alive and not self.board.get_territories_for_player(player.id):
                player.is_alive = False

    def _check_win_conditions(self) -> None:
        if self.is_game_over:
            return

        alive_ids = [p.id for p in self.players if p.is_alive]
        winner, condition = self._win_checker.check_all_conditions(
            self.board, alive_ids, self.turn_number
        )

        if winner is not None or condition is not None:
            self.winner = winner
            self.win_condition = condition
            self._turn_manager.set_game_over()

    def _check_turn_limit(self) -> None:
        if self.config.max_turns <= 0 or self.turn_number <= self.config.max_turns:
            return

        alive_ids = [p.id for p in self.players if p.is_alive]
        best_player = max(
            alive_ids,
            key=lambda pid: len(self.board.get_territories_for_player(pid)),
            default=None,
        )

        self.winner = best_player
        self.win_condition = WinCondition.TURN_LIMIT
        self._turn_manager.set_game_over()


    def copy(self) -> "GameState":
        new = GameState.__new__(GameState)
        new.config = self.config

        new.board = Board(size=self.config.board_size)
        for row in range(self.config.board_size):
            for col in range(self.config.board_size):
                orig = self.board.grid[row][col]
                new.board.grid[row][col] = Territory(
                    owner=orig.owner,
                    troops=orig.troops,
                    is_blocked=orig.is_blocked,
                    troops_moved_this_turn=orig.troops_moved_this_turn,
                )

        new.players = [
            Player(id=p.id, name=p.name, is_alive=p.is_alive, is_ai=p.is_ai)
            for p in self.players
        ]

        new.winner = self.winner
        new.win_condition = self.win_condition

        new._combat_resolver = self._combat_resolver
        new._win_checker = self._win_checker
        new._board_initializer = self._board_initializer

        new._turn_manager = TurnManager(
            players=new.players,
            reinforcement_rate=self.config.reinforcement_rate,
            min_reinforcement=self.config.min_reinforcement,
        )
        new._turn_manager.turn_number = self._turn_manager.turn_number
        new._turn_manager.current_player_index = self._turn_manager.current_player_index
        new._turn_manager.phase = self._turn_manager.phase
        new._turn_manager.reinforcements_available = self._turn_manager.reinforcements_available

        new._reinforcement_manager = ReinforcementManager(
            board=new.board,
            turn_manager=new._turn_manager,
        )
        new._action_manager = ActionManager(
            board=new.board,
            turn_manager=new._turn_manager,
            combat_resolver=new._combat_resolver,
            combat_config=new.config.combat_config,
        )

        return new


    def __repr__(self) -> str:
        lines = [
            f"Turn {self.turn_number} | Player {self.current_player.id}'s {self.phase.value}",
            f"Reinforcements: {self.reinforcements_available}",
            "",
            str(self.board),
            "",
        ]

        for stats in self.get_all_stats():
            status = "ALIVE" if stats["is_alive"] else "DEAD"
            lines.append(
                f"P{stats['player_id']}: {stats['territories']} territories, "
                f"{stats['troops']} troops [{status}]"
            )

        if self.winner is not None:
            lines.append(f"\nWINNER: Player {self.winner} by {self.win_condition.value}!")

        return "\n".join(lines)
