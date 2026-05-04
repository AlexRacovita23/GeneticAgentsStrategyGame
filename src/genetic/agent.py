from typing import List, Tuple, Optional
import random

from src.game.game_state import GameState, GamePhase
from src.game.board import MoveResult
from src.game.combat import calculate_win_probability, minimum_troops_to_win
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
        
        if reinforcement_spread > 0.7:
            self._spread_reinforcements(game_state, territories, border_territories, 
                                       border_focus, reinforcements)
        elif concentration > 0.6:
            self._concentrate_reinforcements(game_state, border_territories, 
                                            reinforcements)
        else:
            self._balanced_reinforcements(game_state, territories, border_territories,
                                         border_focus, reinforcements)
    
    def _spread_reinforcements(self, game_state: GameState, territories: List[Tuple[int, int]],
                               border_territories: List[Tuple[int, int]], border_focus: float,
                               reinforcements: int) -> None:
        targets = border_territories if border_focus > 0.5 else territories
        
        if not targets:
            targets = territories
        
        per_territory = max(1, reinforcements // len(targets))
        
        for pos in targets:
            if reinforcements <= 0:
                break
            amount = min(per_territory, reinforcements)
            game_state.place_reinforcements(pos, amount)
            reinforcements -= amount
    
    def _concentrate_reinforcements(self, game_state: GameState,
                                    border_territories: List[Tuple[int, int]],
                                    reinforcements: int) -> None:
        if not border_territories:
            territories = game_state.board.get_territories_for_player(self.player_id)
            if not territories:
                return
            target = random.choice(territories)
        else:
            target = max(border_territories, 
                        key=lambda pos: game_state.board.get(pos[0], pos[1]).troops)
        
        game_state.place_reinforcements(target, reinforcements)
    
    def _balanced_reinforcements(self, game_state: GameState, 
                                 territories: List[Tuple[int, int]],
                                 border_territories: List[Tuple[int, int]],
                                 border_focus: float,
                                 reinforcements: int) -> None:
        border_amount = int(reinforcements * border_focus)
        interior_amount = reinforcements - border_amount
        
        if border_territories and border_amount > 0:
            weakest_border = min(border_territories,
                               key=lambda pos: game_state.board.get(pos[0], pos[1]).troops)
            game_state.place_reinforcements(weakest_border, border_amount)
        
        if interior_amount > 0:
            interior = [t for t in territories if t not in border_territories]
            if interior:
                target = random.choice(interior)
                game_state.place_reinforcements(target, interior_amount)
            elif border_territories:
                target = random.choice(border_territories)
                game_state.place_reinforcements(target, interior_amount)
    
    def _handle_action(self, game_state: GameState) -> None:
        max_actions = 10
        actions_taken = 0
        
        flanking_preference = self.genome.get_trait('flanking_preference')
        
        while actions_taken < max_actions:
            if flanking_preference > 0.6 and random.random() < 0.4:
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
        
        if neutral_priority > 0.6 and neutral_targets:
            target_pool = neutral_targets
        elif neutral_priority < 0.4 and enemy_targets:
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
                
                if force_ratio >= (1.0 + attack_threshold):
                    troops_to_send = int(available * (0.7 + risk_tolerance * 0.3))
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