from typing import Dict, List, Tuple

from src.game.board import Board
from src.game.game_state import GameState
from src.genetic.genome import Genome
from src.genetic.territory_evaluator import TerritoryEvaluator


class ReinforcementStrategy:

    def __init__(self, genome: Genome):
        self.genome = genome

    def distribute_reinforcements(
        self,
        game_state: GameState,
        player_id: int,
        reinforcements: int,
    ) -> Dict[Tuple[int, int], int]:
        if reinforcements == 0:
            return {}

        territories = game_state.board.get_territories_for_player(player_id)
        if not territories:
            return {}

        border_focus = self.genome.get_trait("border_focus")
        reinforcement_spread = self.genome.get_trait("reinforcement_spread")
        concentration = self.genome.get_trait("concentration")
        defensive_posture = self.genome.get_trait("defensive_posture")

        border_territories = set(
            _get_border_territories(game_state.board, territories, player_id)
        )

        evaluator = TerritoryEvaluator(game_state.board, player_id)

        weights: Dict[Tuple[int, int], float] = {}
        for pos in territories:
            troops = game_state.board.get(pos[0], pos[1]).troops
            is_border = pos in border_territories

            base_weight = border_focus if is_border else (1.0 - border_focus)

            if troops > 0:
                strength_weight = (
                    troops * reinforcement_spread
                    + (1.0 / troops) * (1.0 - reinforcement_spread)
                )
            else:
                strength_weight = 1.0

            threat = evaluator.assess_threat(pos)
            defensive_multiplier = 1.0 + (threat.threat_score * defensive_posture)

            weights[pos] = base_weight * strength_weight * defensive_multiplier

        sharpness = 1.0 + concentration * 4.0
        sharpened = {pos: w ** sharpness for pos, w in weights.items()}

        total_weight = sum(sharpened.values())
        if total_weight == 0:
            distribution = {pos: 1.0 / len(territories) for pos in territories}
        else:
            distribution = {pos: w / total_weight for pos, w in sharpened.items()}

        allocated: Dict[Tuple[int, int], int] = {}
        remaining = reinforcements

        for pos, fraction in distribution.items():
            troops_to_place = round(reinforcements * fraction)
            if troops_to_place > 0 and remaining > 0:
                actual = min(troops_to_place, remaining)
                allocated[pos] = actual
                remaining -= actual

        if remaining > 0:
            best_pos = max(distribution, key=lambda p: distribution[p])
            allocated[best_pos] = allocated.get(best_pos, 0) + remaining

        return allocated

def _get_border_territories(
    board: Board,
    territories: List[Tuple[int, int]],
    player_id: int,
) -> List[Tuple[int, int]]:
    border = []
    for pos in territories:
        for neighbor in board.get_neighbors(pos[0], pos[1]):
            if board.get(neighbor[0], neighbor[1]).owner != player_id:
                border.append(pos)
                break
    return border
