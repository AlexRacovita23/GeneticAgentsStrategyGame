import random
from collections import deque
from typing import Dict, List, Optional, Tuple

from src.game import board_info
from src.game.board import MoveResult
from src.game.combat import minimum_troops_to_win
from src.game.game_state import GameState
from src.genetic.genome import Genome
from src.genetic.territory_evaluator import TerritoryEvaluator


def _bfs_next_step(
    game_state: GameState,
    src: Tuple[int, int],
    dst: Tuple[int, int],
    player_id: int,
) -> Optional[Tuple[int, int]]:
    if src == dst:
        return None

    board = game_state.board
    visited: Dict[Tuple[int, int], Optional[Tuple[int, int]]] = {src: None}
    queue: deque = deque([src])

    while queue:
        current = queue.popleft()

        for neighbor in board.get_neighbors(current[0], current[1]):
            if neighbor in visited:
                continue

            neighbor_tile = board.get(neighbor[0], neighbor[1])
            is_friendly = neighbor_tile.owner == player_id
            is_goal = neighbor == dst

            if not is_friendly and not is_goal:
                continue

            visited[neighbor] = current

            if is_goal:
                step = neighbor
                while visited[step] != src:
                    step = visited[step]  # type: ignore[assignment]
                return step

            queue.append(neighbor)

    return None


class ActionStrategy:

    def __init__(self, genome: Genome):
        self.genome = genome

    def redistribute_troops(self, game_state: GameState, player_id: int) -> int:
        concentration        = self.genome.get_trait("concentration")
        border_focus         = self.genome.get_trait("border_focus")
        reinforcement_spread = self.genome.get_trait("reinforcement_spread")

        territories = game_state.board.get_territories_for_player(player_id)
        if len(territories) < 2:
            return 0

        border_set = set(_get_border_territories(game_state.board, territories, player_id))

        weights: Dict[Tuple[int, int], float] = {}
        for pos in territories:
            troops    = game_state.board.get(pos[0], pos[1]).troops
            is_border = pos in border_set

            base_weight = border_focus if is_border else (1.0 - border_focus)

            if troops > 0:
                strength_weight = (
                    troops * reinforcement_spread
                    + (1.0 / troops) * (1.0 - reinforcement_spread)
                )
            else:
                strength_weight = 1.0

            weights[pos] = base_weight * strength_weight

        sharpness = 1.0 + concentration * 4.0
        sharpened = {pos: w ** sharpness for pos, w in weights.items()}

        total_weight = sum(sharpened.values())
        if total_weight == 0:
            return 0

        target_fractions: Dict[Tuple[int, int], float] = {
            pos: w / total_weight for pos, w in sharpened.items()
        }

        total_moveable = sum(
            game_state.board.get(r, c).troops
            for r, c in territories
        )

        target_troops: Dict[Tuple[int, int], float] = {
            pos: target_fractions[pos] * total_moveable
            for pos in territories
        }

        available_now: Dict[Tuple[int, int], int] = {
            pos: game_state.board.get(pos[0], pos[1]).available_troops
            for pos in territories
        }

        surplus: List[Tuple[Tuple[int, int], int]] = []
        deficit: List[Tuple[Tuple[int, int], float]] = []

        for pos in territories:
            if weights.get(pos, 0.0) == 0.0:
                continue
            avail = available_now[pos]
            want  = target_troops[pos]
            diff  = avail - want
            if diff > 1:
                surplus.append((pos, int(diff)))
            elif diff < -1:
                deficit.append((pos, -diff))

        if not surplus or not deficit:
            return 0

        surplus.sort(key=lambda x: x[1], reverse=True)
        deficit.sort(key=lambda x: x[1], reverse=True)

        moves_made = 0

        for def_pos, def_want in deficit:
            if not surplus:
                break

            remaining_need = int(def_want)
            consumed: List[int] = []

            for s_idx, (src_pos, src_available) in enumerate(surplus):
                if remaining_need <= 0:
                    break
                if src_available <= 0:
                    consumed.append(s_idx)
                    continue

                next_step = _bfs_next_step(game_state, src_pos, def_pos, player_id)
                if next_step is None:
                    continue

                to_move = min(remaining_need, src_available)
                if to_move <= 0:
                    continue

                outcome = game_state.move_troops(src_pos, next_step, to_move)

                if outcome.result == MoveResult.REINFORCED:
                    moves_made += 1
                    remaining_need -= to_move

                    available_now[src_pos] -= to_move
                    new_surplus = available_now[src_pos] - int(target_troops.get(src_pos, 0))

                    if new_surplus > 1:
                        surplus[s_idx] = (src_pos, new_surplus)
                    else:
                        consumed.append(s_idx)

                    available_now[next_step] = available_now.get(next_step, 0) + to_move

            for i in sorted(set(consumed), reverse=True):
                surplus.pop(i)

        return moves_made

    def execute_actions(
        self, game_state: GameState, player_id: int, max_actions: int = 0
    ) -> int:
        actions_taken = 0
        flanking_preference = self.genome.get_trait("flanking_preference")
        retreat_threshold   = self.genome.get_trait("retreat_threshold")
        forward_aggression  = self.genome.get_trait("forward_aggression")

        if game_state.turn_number > 10:
            self._execute_retreats(game_state, player_id, retreat_threshold)

        if game_state.turn_number > 5:
            self._forward_deploy(game_state, player_id)

        while True:
            did_something = False

            if random.random() < flanking_preference:
                if self.attempt_flanking_attack(game_state, player_id):
                    actions_taken += 1
                    did_something = True
                    continue

            if self.attempt_single_attack(game_state, player_id):
                actions_taken += 1
                did_something = True

            if not did_something:
                if random.random() < forward_aggression * 0.3:
                    if self._attempt_breakout_attack(game_state, player_id):
                        actions_taken += 1
                        did_something = True

                if not did_something:
                    break

        return actions_taken

    def attempt_single_attack(self, game_state: GameState, player_id: int) -> bool:
        attack_threshold = self.genome.get_trait("attack_threshold")
        risk_tolerance   = self.genome.get_trait("risk_tolerance")
        neutral_priority = self.genome.get_trait("neutral_priority")
        expansion_speed  = self.genome.get_trait("expansion_speed")

        targets = board_info.get_attack_targets(game_state.board, player_id)
        if not targets:
            return False

        target_pool = self._pick_strategic_targets(
            game_state, player_id, targets, neutral_priority, expansion_speed, risk_tolerance
        )

        for target in target_pool:
            target_territory   = game_state.board.get(target[0], target[1])
            attacker_positions = board_info.get_flanking_options(
                game_state.board, player_id, target
            )

            for attacker_pos in attacker_positions:
                attacker_territory = game_state.board.get(attacker_pos[0], attacker_pos[1])
                available = attacker_territory.available_troops

                if available == 0:
                    continue

                attack_probability = self._attack_probability(
                    available, target_territory.troops, attack_threshold
                )

                if random.random() < attack_probability:
                    troops_to_send = max(
                        1,
                        min(
                            int(available * (0.5 + risk_tolerance * 0.5)),
                            available,
                        ),
                    )
                    result = game_state.move_troops(attacker_pos, target, troops_to_send)
                    if result.result in (MoveResult.CONQUERED, MoveResult.REPELLED):
                        return True

        return False

    def attempt_flanking_attack(self, game_state: GameState, player_id: int) -> bool:
        targets = board_info.get_attack_targets(game_state.board, player_id)
        if not targets:
            return False

        random.shuffle(targets)

        for target in targets:
            attackers = board_info.get_flanking_options(game_state.board, player_id, target)
            if len(attackers) < 2:
                continue

            target_territory = game_state.board.get(target[0], target[1])
            total_available  = sum(
                game_state.board.get(pos[0], pos[1]).available_troops
                for pos in attackers
            )
            min_needed = minimum_troops_to_win(
                target_territory.troops,
                flanking_directions=len(attackers),
            )

            if total_available < min_needed:
                continue

            attacks: List[Tuple[Tuple[int, int], int]] = [
                (pos, game_state.board.get(pos[0], pos[1]).available_troops)
                for pos in attackers
                if game_state.board.get(pos[0], pos[1]).available_troops > 0
            ]

            if len(attacks) >= 2:
                result = game_state.coordinated_attack(attacks, target)
                if result.result in (MoveResult.CONQUERED, MoveResult.REPELLED):
                    return True

        return False

    def _pick_strategic_targets(
        self,
        game_state: GameState,
        player_id: int,
        targets: List[Tuple[int, int]],
        neutral_priority: float,
        expansion_speed: float,
        risk_tolerance: float,
    ) -> List[Tuple[int, int]]:
        evaluator = TerritoryEvaluator(game_state.board, player_id)

        scored_targets = [
            (target, evaluator.score_attack_target(target, expansion_speed, risk_tolerance))
            for target in targets
        ]

        for i, (target, score) in enumerate(scored_targets):
            if game_state.board.get(target[0], target[1]).is_neutral:
                scored_targets[i] = (target, score * (1.0 + neutral_priority))

        scored_targets.sort(key=lambda x: x[1], reverse=True)

        top_count = max(3, len(scored_targets) // 3)
        strategic_targets = [target for target, _ in scored_targets[:top_count]]

        free_targets = [
            t for t in targets
            if game_state.board.get(t[0], t[1]).troops == 0
            and t not in strategic_targets
        ]

        return free_targets + strategic_targets

    def _execute_retreats(
        self,
        game_state: GameState,
        player_id: int,
        retreat_threshold: float,
    ) -> int:
        evaluator = TerritoryEvaluator(game_state.board, player_id)
        threatened = evaluator.get_threatened_territories(retreat_threshold)

        retreats_made = 0
        for pos in threatened:
            territory = game_state.board.get(pos[0], pos[1])
            available = territory.available_troops

            if available == 0:
                continue

            neighbors = game_state.board.get_neighbors(pos[0], pos[1])
            safe_neighbors = []

            for neighbor in neighbors:
                neighbor_territory = game_state.board.get(neighbor[0], neighbor[1])
                if neighbor_territory.owner == player_id:
                    threat = evaluator.assess_threat(neighbor)
                    safe_neighbors.append((neighbor, threat.threat_score))

            if safe_neighbors:
                safe_neighbors.sort(key=lambda x: x[1])
                safest = safe_neighbors[0][0]

                troops_to_move = max(1, int(available * 0.7))
                result = game_state.move_troops(pos, safest, troops_to_move)
                if result.result == MoveResult.REINFORCED:
                    retreats_made += 1

        return retreats_made

    def _forward_deploy(self, game_state: GameState, player_id: int) -> int:
        forward_aggression = self.genome.get_trait("forward_aggression")

        territories = game_state.board.get_territories_for_player(player_id)
        if len(territories) < 2:
            return 0

        frontier_positions = []
        interior_positions = []

        for pos in territories:
            neighbors = game_state.board.get_neighbors(pos[0], pos[1])
            has_enemy_neighbor = any(
                game_state.board.get(n[0], n[1]).owner != player_id
                for n in neighbors
            )

            if has_enemy_neighbor:
                frontier_positions.append(pos)
            else:
                interior_positions.append(pos)

        if not frontier_positions or not interior_positions:
            return 0

        interior_positions.sort(
            key=lambda p: game_state.board.get(p[0], p[1]).available_troops,
            reverse=True
        )

        moves_made = 0

        for interior_pos in interior_positions:
            interior_tile = game_state.board.get(interior_pos[0], interior_pos[1])
            available = interior_tile.available_troops

            if available < 2:
                continue

            if random.random() > forward_aggression:
                continue

            frontier_positions.sort(
                key=lambda p: game_state.board.get(p[0], p[1]).troops
            )

            for frontier_pos in frontier_positions:
                next_step = _bfs_next_step(game_state, interior_pos, frontier_pos, player_id)
                if next_step is None:
                    continue

                troops_to_move = max(1, int(available * forward_aggression))
                result = game_state.move_troops(interior_pos, next_step, troops_to_move)

                if result.result == MoveResult.REINFORCED:
                    moves_made += 1
                    break

        return moves_made

    def _attempt_breakout_attack(self, game_state: GameState, player_id: int) -> bool:
        attack_threshold = self.genome.get_trait("attack_threshold")
        forward_aggression = self.genome.get_trait("forward_aggression")

        territories = game_state.board.get_territories_for_player(player_id)

        stuck_territories = []
        for pos in territories:
            tile = game_state.board.get(pos[0], pos[1])
            if tile.available_troops < 5:
                continue

            neighbors = game_state.board.get_neighbors(pos[0], pos[1])
            has_friendly_exit = any(
                game_state.board.get(n[0], n[1]).owner == player_id and
                game_state.board.get(n[0], n[1]).available_troops < tile.available_troops * 0.5
                for n in neighbors
            )

            if not has_friendly_exit:
                stuck_territories.append(pos)

        if not stuck_territories:
            return False

        stuck_territories.sort(
            key=lambda p: game_state.board.get(p[0], p[1]).available_troops,
            reverse=True
        )

        for pos in stuck_territories:
            tile = game_state.board.get(pos[0], pos[1])
            neighbors = game_state.board.get_neighbors(pos[0], pos[1])

            enemy_neighbors = [
                n for n in neighbors
                if game_state.board.get(n[0], n[1]).owner != player_id
            ]

            if not enemy_neighbors:
                continue

            for target in enemy_neighbors:
                target_tile = game_state.board.get(target[0], target[1])
                force_ratio = tile.available_troops / max(1, target_tile.troops)

                breakout_threshold = 0.5 + attack_threshold * 0.3

                if force_ratio >= breakout_threshold and random.random() < forward_aggression:
                    troops_to_send = max(1, int(tile.available_troops * 0.8))
                    result = game_state.move_troops(pos, target, troops_to_send)

                    if result.result in (MoveResult.CONQUERED, MoveResult.REPELLED):
                        return True

        return False

    @staticmethod
    def _attack_probability(
        available: int, defenders: int, attack_threshold: float
    ) -> float:
        force_ratio = available / max(1, defenders)
        min_ratio   = 1.0 + attack_threshold * 2.0

        if force_ratio >= min_ratio:
            return 1.0
        if force_ratio >= 1.0:
            return (force_ratio - 1.0) / (min_ratio - 1.0)
        return 0.0

def _get_border_territories(board, territories, player_id):
    border = []
    for pos in territories:
        for neighbor in board.get_neighbors(pos[0], pos[1]):
            if board.get(neighbor[0], neighbor[1]).owner != player_id:
                border.append(pos)
                break
    return border