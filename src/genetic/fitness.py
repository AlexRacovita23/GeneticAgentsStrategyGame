from dataclasses import dataclass
from typing import List, Tuple

from src.game.game_state import GameState


@dataclass
class FitnessResult:
    score: float
    wins: int
    losses: int
    draws: int
    avg_territories: float
    avg_troops: float
    avg_turns_survived: float

    def __repr__(self) -> str:
        return (
            f"FitnessResult(score={self.score:.2f}, "
            f"W/L/D={self.wins}/{self.losses}/{self.draws}, "
            f"territories={self.avg_territories:.1f}, "
            f"troops={self.avg_troops:.1f}, "
            f"turns={self.avg_turns_survived:.1f})"
        )


class FitnessEvaluator:
    def __init__(
        self,
        win_weight: float = 100.0,
        territory_weight: float = 2.0,
        troop_weight: float = 0.5,
        turn_weight: float = 1.0,
    ):
        self.win_weight = win_weight
        self.territory_weight = territory_weight
        self.troop_weight = troop_weight
        self.turn_weight = turn_weight

    def evaluate_game(self, game_state: GameState, player_id: int) -> float:
        score = 0.0

        if game_state.winner == player_id:
            score += self.win_weight

        stats = game_state.get_player_stats(player_id)
        score += stats["territories"] * self.territory_weight
        score += stats["troops"] * self.troop_weight
        score += game_state.turn_number * self.turn_weight

        return score

    def evaluate_games(
        self, game_results: List[Tuple[GameState, int]]
    ) -> FitnessResult:
        if not game_results:
            return FitnessResult(
                score=0.0,
                wins=0,
                losses=0,
                draws=0,
                avg_territories=0.0,
                avg_troops=0.0,
                avg_turns_survived=0.0,
            )

        total_score = 0.0
        wins = losses = draws = 0
        total_territories = total_troops = total_turns = 0

        for game_state, player_id in game_results:
            total_score += self.evaluate_game(game_state, player_id)

            if game_state.winner == player_id:
                wins += 1
            elif game_state.winner is not None:
                losses += 1
            else:
                draws += 1

            stats = game_state.get_player_stats(player_id)
            total_territories += stats["territories"]
            total_troops += stats["troops"]
            total_turns += game_state.turn_number

        n = len(game_results)
        return FitnessResult(
            score=total_score / n,
            wins=wins,
            losses=losses,
            draws=draws,
            avg_territories=total_territories / n,
            avg_troops=total_troops / n,
            avg_turns_survived=total_turns / n,
        )

    def compare_fitness(
        self, fitness1: FitnessResult, fitness2: FitnessResult
    ) -> int:
        if fitness1.score > fitness2.score:
            return 1
        if fitness1.score < fitness2.score:
            return -1
        return 0
