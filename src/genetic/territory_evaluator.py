from typing import List, Tuple
from src.game.board import Board
from src.genetic.strategy_types import TerritoryScore, ThreatAssessment
from src.game.board_info import (
    count_enemy_troops_adjacent,
    count_friendly_neighbors,
    get_territory_connectivity,
)


class TerritoryEvaluator:

    def __init__(self, board: Board, player_id: int):
        self.board = board
        self.player_id = player_id

    def assess_threat(self, pos: Tuple[int, int]) -> ThreatAssessment:
        enemy_troops = count_enemy_troops_adjacent(self.board, self.player_id, pos)
        friendly_neighbors = count_friendly_neighbors(self.board, self.player_id, pos)

        territory = self.board.get(pos[0], pos[1])
        is_border = False
        for neighbor in self.board.get_neighbors(pos[0], pos[1]):
            neighbor_territory = self.board.get(neighbor[0], neighbor[1])
            if neighbor_territory.owner != self.player_id:
                is_border = True
                break

        threat_score = enemy_troops / max(1, territory.troops)
        threat_score *= (1.0 / max(1, friendly_neighbors))

        return ThreatAssessment(
            territory_id=pos[0] * self.board.size + pos[1],
            enemy_troops_adjacent=enemy_troops,
            friendly_neighbors=friendly_neighbors,
            is_border=is_border,
            threat_score=threat_score
        )

    def score_territory(self, pos: Tuple[int, int], expansion_speed: float) -> TerritoryScore:
        territory = self.board.get(pos[0], pos[1])
        threat = self.assess_threat(pos)
        connectivity = get_territory_connectivity(self.board, self.player_id, pos)

        offensive_value = 0.0
        if territory.owner == self.player_id:
            offensive_value = territory.troops * 0.1
            if threat.is_border:
                offensive_value += 0.3

        defensive_value = threat.friendly_neighbors * 0.2 + connectivity * 0.1

        expansion_value = 0.0
        neutral_neighbors = 0
        enemy_neighbors = 0

        for neighbor in self.board.get_neighbors(pos[0], pos[1]):
            neighbor_territory = self.board.get(neighbor[0], neighbor[1])
            if neighbor_territory.owner == -1:
                neutral_neighbors += 1
            elif neighbor_territory.owner != self.player_id:
                enemy_neighbors += 1

        expansion_value = neutral_neighbors * expansion_speed + enemy_neighbors * (1.0 - expansion_speed)

        return TerritoryScore(
            territory_id=pos[0] * self.board.size + pos[1],
            offensive_value=offensive_value,
            defensive_value=defensive_value,
            expansion_value=expansion_value,
            threat_level=threat.threat_score
        )

    def get_threatened_territories(self, retreat_threshold: float) -> List[Tuple[int, int]]:
        threatened = []

        for pos in self.board.get_territories_for_player(self.player_id):
            threat = self.assess_threat(pos)
            if threat.threat_score > retreat_threshold:
                threatened.append(pos)

        return threatened

    def score_attack_target(
        self,
        target: Tuple[int, int],
        expansion_speed: float,
        risk_tolerance: float
    ) -> float:
        target_territory = self.board.get(target[0], target[1])

        # flat base score so free/neutral tiles are never buried near zero
        if target_territory.troops == 0:
            base_score = 2.0
        elif target_territory.owner == -1:
            base_score = 1.0
        else:
            base_score = 0.0

        score = self.score_territory(target, expansion_speed)
        strategic_score = base_score + score.expansion_value

        if target_territory.owner == -1:
            strategic_score *= 1.2
        else:
            strategic_score *= (0.8 + risk_tolerance * 0.4)

        troop_modifier = 1.0 / max(1, target_territory.troops * 0.5)
        strategic_score *= (1.0 + troop_modifier)

        # bonus for tiles already adjacent to your territory (reachable and useful)
        friendly_adjacent = sum(
            1 for n in self.board.get_neighbors(target[0], target[1])
            if self.board.get(n[0], n[1]).owner == self.player_id
        )
        strategic_score += friendly_adjacent * 0.5

        connectivity = get_territory_connectivity(self.board, self.player_id, target)
        strategic_score += connectivity * 0.1

        return strategic_score