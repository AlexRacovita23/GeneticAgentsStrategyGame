from typing import List, Tuple

from src.game.board import Board, MoveOutcome, MoveResult
from src.game.combat import (
    CombatResolver,
    resolve_flanked_combat,
    FlankingOutcome,
    AttackSource,
    CombatConfig,
)
from src.game.player import GamePhase
from src.game.territory import Territory
from src.game.turn_manager import TurnManager

def _invalid_flanking(defender_troops: int = 0) -> FlankingOutcome:
    return FlankingOutcome(
        result=MoveResult.INVALID,
        attacker_wins=False,
        total_attackers=0,
        total_defenders=defender_troops,
        flanking_directions=0,
        flanking_bonus=1.0,
        remaining_troops=defender_troops,
        troops_lost_attacker=0,
        troops_lost_defender=0,
    )


class ActionManager:

    def __init__(
        self,
        board: Board,
        turn_manager: TurnManager,
        combat_resolver: CombatResolver,
        combat_config: CombatConfig,
    ):
        self._board = board
        self._turn_manager = turn_manager
        self._combat_resolver = combat_resolver
        self._combat_config = combat_config


    def move_troops(
        self,
        from_pos: Tuple[int, int],
        to_pos: Tuple[int, int],
        troop_count: int,
    ) -> MoveOutcome:
        if self._turn_manager.phase != GamePhase.ACTION:
            return MoveOutcome(result=MoveResult.INVALID)

        source = self._board.get(from_pos[0], from_pos[1])
        if source is None or source.owner != self._turn_manager.current_player.id:
            return MoveOutcome(result=MoveResult.INVALID)

        return self._board.move_troops(
            from_pos,
            to_pos,
            troop_count,
            combat_resolver=self._combat_resolver,
        )

    def coordinated_attack(
        self,
        attacks: List[Tuple[Tuple[int, int], int]],
        target: Tuple[int, int],
    ) -> FlankingOutcome:
        if self._turn_manager.phase != GamePhase.ACTION:
            return _invalid_flanking()

        target_row, target_col = target
        dest = self._board.get(target_row, target_col)

        if dest is None:
            return _invalid_flanking()

        if dest.owner == self._turn_manager.current_player.id:
            return _invalid_flanking(dest.troops)

        attack_sources: List[AttackSource] = []
        troops_to_remove: List[Tuple[Territory, int]] = []

        for from_pos, troop_count in attacks:
            source = self._board.get(from_pos[0], from_pos[1])

            if source is None:
                continue
            if source.owner != self._turn_manager.current_player.id:
                continue
            if not self._board.are_adjacent(from_pos, target):
                continue
            if not source.can_move_from():
                continue

            actual_troops = min(troop_count, source.available_troops)
            if actual_troops <= 0:
                continue

            attack_sources.append(AttackSource(position=from_pos, troops=actual_troops))
            troops_to_remove.append((source, actual_troops))

        if not attack_sources:
            return _invalid_flanking(dest.troops)

        for source, count in troops_to_remove:
            source.remove_troops(count)

        return resolve_flanked_combat(
            attacks=attack_sources,
            dest=dest,
            attacker_owner=self._turn_manager.current_player.id,
            config=self._combat_config,
        )

    def reset_movement_counters(self) -> None:
        for row in range(self._board.size):
            for col in range(self._board.size):
                self._board.grid[row][col].troops_moved_this_turn = 0
