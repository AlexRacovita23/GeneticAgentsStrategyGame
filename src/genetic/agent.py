from typing import List, Tuple
import random

from src.game.game_state import GameState, GamePhase
from src.game.board import MoveResult
from src.game.combat import minimum_troops_to_win
from src.genetic.genome import Genome


class GeneticAgent:
    
    def __init__(self, genome: Genome, player_id: int):
        self.genome = genome
        self.player_id = player_id
    
    def take_turn(self, game_state: GameState) -> None:
        if game_state.current_player.id != self.player_id:
            return
        
        if game_state.phase == GamePhase.REINFORCEMENT:
            self._handle_reinforcement(game_state)
            game_state.end_reinforcement_phase()
        
        if game_state.phase == GamePhase.ACTION:
            self._handle_action(game_state)
            game_state.end_turn()
    
    def _handle_reinforcement(self, game_state: GameState) -> None:
        reinforcements = game_state.reinforcements_available
        if reinforcements == 0:
            return
        
        territories = game_state.board.get_territories_for_player(self.player_id)
        if not territories:
            return
        
        border_focus = self.genome.get_trait('border_focus')
        reinforcement_spread = self.genome.get_trait('reinforcement_spread')
        concentration = self.genome.get_trait('concentration')
        
        border_territories = self._get_border_territories(game_state, territories)
        
        weights = {}
        for pos in territories:
            is_border = pos in border_territories
            troops = game_state.board.get(pos[0], pos[1]).troops

            base_weight = border_focus if is_border else (1.0 - border_focus)

            if troops > 0:
                strength_weight = (troops * reinforcement_spread +
                                 (1.0 / troops) * (1.0 - reinforcement_spread))
            else:
                strength_weight = 1.0

            weights[pos] = base_weight * strength_weight
        
        sharpness = 1.0 + concentration * 4.0
        sharpened = {pos: w ** sharpness for pos, w in weights.items()}

        total_weight = sum(sharpened.values())
        if total_weight == 0:
            distribution = {pos: 1.0 / len(territories) for pos in territories}
        else:
            distribution = {pos: w / total_weight for pos, w in sharpened.items()}
        
        allocated = {}
        remaining = reinforcements
        
        for pos, fraction in distribution.items():
            troops_to_place = round(reinforcements * fraction)
            if troops_to_place > 0 and remaining > 0:
                actual = min(troops_to_place, remaining)
                allocated[pos] = actual
                remaining -= actual

        if remaining > 0:
            best_pos = max(distribution.keys(), key=lambda p: distribution[p])
            allocated[best_pos] = allocated.get(best_pos, 0) + remaining
        
        for pos, troops in allocated.items():
            if troops > 0:
                game_state.place_reinforcements(pos, troops)
    
    def _handle_action(self, game_state: GameState) -> None:
        max_actions = 10
        actions_taken = 0
        
        flanking_preference = self.genome.get_trait('flanking_preference')
        
        while actions_taken < max_actions:
            if random.random() < flanking_preference:
                if self._attempt_flanking_attack(game_state):
                    actions_taken += 1
                    continue
            
            if self._attempt_single_attack(game_state):
                actions_taken += 1
            else:
                break
    
    def _attempt_single_attack(self, game_state: GameState) -> bool:
        attack_threshold = self.genome.get_trait('attack_threshold')
        risk_tolerance = self.genome.get_trait('risk_tolerance')
        neutral_priority = self.genome.get_trait('neutral_priority')
        
        targets = game_state.get_attack_targets(self.player_id)
        if not targets:
            return False
        
        neutral_targets = [t for t in targets if game_state.board.get(t[0], t[1]).is_neutral]
        enemy_targets = [t for t in targets if not game_state.board.get(t[0], t[1]).is_neutral]
        
        target_pool = []
        if neutral_targets and enemy_targets:
            if random.random() < neutral_priority:
                target_pool = neutral_targets
            else:
                target_pool = enemy_targets
        elif neutral_targets:
            target_pool = neutral_targets
        elif enemy_targets:
            target_pool = enemy_targets
        else:
            target_pool = targets
        
        random.shuffle(target_pool)
        
        for target in target_pool:
            target_territory = game_state.board.get(target[0], target[1])
            attackers_list = game_state.get_flanking_options(self.player_id, target)
            
            for attacker_pos in attackers_list:
                attacker_territory = game_state.board.get(attacker_pos[0], attacker_pos[1])
                available = attacker_territory.available_troops
                
                if available == 0:
                    continue
                
                force_ratio = available / max(1, target_territory.troops)
                
                min_ratio = 1.0 + attack_threshold * 2.0

                if force_ratio >= min_ratio:
                    attack_probability = 1.0
                elif force_ratio >= 1.0:
                    attack_probability = (force_ratio - 1.0) / (min_ratio - 1.0)
                else:
                    attack_probability = 0.0

                if random.random() < attack_probability:
                    troops_to_send = int(available * (0.5 + risk_tolerance * 0.5))
                    troops_to_send = max(1, min(troops_to_send, available))
                    
                    result = game_state.move_troops(attacker_pos, target, troops_to_send)
                    if result.result in [MoveResult.CONQUERED, MoveResult.REPELLED]:
                        return True
        
        return False
    
    def _attempt_flanking_attack(self, game_state: GameState) -> bool:
        targets = game_state.get_attack_targets(self.player_id)
        if not targets:
            return False
        
        random.shuffle(targets)
        
        for target in targets:
            attackers = game_state.get_flanking_options(self.player_id, target)
            
            if len(attackers) < 2:
                continue
            
            target_territory = game_state.board.get(target[0], target[1])
            total_available = sum(
                game_state.board.get(pos[0], pos[1]).available_troops 
                for pos in attackers
            )
            
            min_needed = minimum_troops_to_win(
                target_territory.troops,
                flanking_directions=len(attackers)
            )
            
            if total_available >= min_needed:
                attacks = []
                for pos in attackers:
                    territory = game_state.board.get(pos[0], pos[1])
                    troops = territory.available_troops
                    if troops > 0:
                        attacks.append((pos, troops))
                
                if len(attacks) >= 2:
                    result = game_state.coordinated_attack(attacks, target)
                    if result.result in [MoveResult.CONQUERED, MoveResult.REPELLED]:
                        return True
        
        return False
    
    def _get_border_territories(self, game_state: GameState, 
                               territories: List[Tuple[int, int]]) -> List[Tuple[int, int]]:
        border = []
        
        for pos in territories:
            neighbors = game_state.board.get_neighbors(pos[0], pos[1])
            for neighbor in neighbors:
                neighbor_territory = game_state.board.get(neighbor[0], neighbor[1])
                if neighbor_territory.owner != self.player_id:
                    border.append(pos)
                    break
        
        return border