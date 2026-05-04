from dataclasses import dataclass, field
from enum import Enum
from typing import List, Tuple, Optional, Dict, Callable

from src.game.board import Board, MoveOutcome, MoveResult
from src.game.territory import Territory
from src.game.combat import (
    CombatConfig,
    AttackSource,
    FlankingOutcome,
    resolve_combat_lanchester,
    resolve_flanked_combat,
    create_combat_resolver,
)


class GamePhase(Enum):
    REINFORCEMENT = "reinforcement"
    ACTION = "action"
    GAME_OVER = "game_over"


class WinCondition(Enum):
    ELIMINATION = "elimination"
    DOMINATION = "domination"
    TURN_LIMIT = "turn_limit"


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
    reinforcement_rate: float = 1
    min_reinforcement: int = 1
    domination_threshold: float = 0.75
    max_turns: int = 100
    combat_config: CombatConfig = field(default_factory=CombatConfig)


@dataclass
class TurnInfo:
    turn_number: int
    current_player_id: int
    phase: GamePhase
    reinforcements_available: int = 0
    actions_taken: int = 0


class GameState:
    def __init__(self, config: GameConfig = None):
        self.config = config or GameConfig()
        self.board = Board(size=self.config.board_size)
        self.players: List[Player] = []
        self.turn_number = 0
        self.current_player_index = 0
        self.phase = GamePhase.REINFORCEMENT
        self.reinforcements_available = 0
        self.winner: Optional[int] = None
        self.win_condition: Optional[WinCondition] = None
        
        self._combat_resolver = create_combat_resolver(self.config.combat_config)
        
        self._setup_players()
    
    def _setup_players(self) -> None:
        for i in range(self.config.num_players):
            self.players.append(Player(id=i))
    
    def setup_random_start(self, seed: int = None) -> None:
        import random
        if seed is not None:
            random.seed(seed)
        
        size = self.config.board_size
        
        start_positions = [
            (0, 0),
            (size - 1, size - 1),
            (0, size - 1),
            (size - 1, 0),
            (0, size // 2),
            (size - 1, size // 2),
            (size // 2, 0),
            (size // 2, size - 1),
        ]
        
        for i, player in enumerate(self.players):
            if i < len(start_positions):
                row, col = start_positions[i]
                territory = self.board.get(row, col)
                territory.set_owner(player.id, self.config.starting_troops)
        
        self._add_neutral_territories()
        
        self.turn_number = 1
        self.phase = GamePhase.REINFORCEMENT
        self._calculate_reinforcements()
    
    def _add_neutral_territories(self) -> None:
        import random
        
        size = self.config.board_size
        neutral_count = (size * size) // 4
        
        positions = [
            (r, c) 
            for r in range(size) 
            for c in range(size) 
            if self.board.get(r, c).owner == -1
        ]
        
        random.shuffle(positions)
        
        for i, (row, col) in enumerate(positions[:neutral_count]):
            troops = random.randint(1, 5)
            self.board.grid[row][col].troops = troops
    
    def _calculate_reinforcements(self) -> None:
        player_id = self.current_player.id
        territory_count = len(self.board.get_territories_for_player(player_id))
        
        reinforcements = int(territory_count * self.config.reinforcement_rate)
        reinforcements = max(self.config.min_reinforcement, reinforcements)
        
        self.reinforcements_available = reinforcements
    
    @property
    def current_player(self) -> Player:
        return self.players[self.current_player_index]
    
    @property
    def is_game_over(self) -> bool:
        return self.phase == GamePhase.GAME_OVER
    
    def get_turn_info(self) -> TurnInfo:
        return TurnInfo(
            turn_number=self.turn_number,
            current_player_id=self.current_player.id,
            phase=self.phase,
            reinforcements_available=self.reinforcements_available,
        )
    
    def place_reinforcements(self, position: Tuple[int, int], count: int) -> bool:
        if self.phase != GamePhase.REINFORCEMENT:
            return False
        
        if count <= 0 or count > self.reinforcements_available:
            return False
        
        row, col = position
        territory = self.board.get(row, col)
        
        if territory is None or territory.owner != self.current_player.id:
            return False
        
        territory.add_troops(count)
        self.reinforcements_available -= count
        
        return True
    
    def end_reinforcement_phase(self) -> bool:
        if self.phase != GamePhase.REINFORCEMENT:
            return False
        
        self.reinforcements_available = 0
        self.phase = GamePhase.ACTION
        return True
    
    def move_troops(
        self,
        from_pos: Tuple[int, int],
        to_pos: Tuple[int, int],
        troop_count: int,
    ) -> MoveOutcome:
        if self.phase != GamePhase.ACTION:
            return MoveOutcome(result=MoveResult.INVALID)
        
        source = self.board.get(from_pos[0], from_pos[1])
        if source is None or source.owner != self.current_player.id:
            return MoveOutcome(result=MoveResult.INVALID)
        
        result = self.board.move_troops(
            from_pos, 
            to_pos, 
            troop_count, 
            combat_resolver=self._combat_resolver
        )
        
        if result.result in [MoveResult.CONQUERED, MoveResult.REPELLED]:
            self._check_eliminations()
            self._check_win_conditions()
        
        return result
    
    def coordinated_attack(
        self,
        attacks: List[Tuple[Tuple[int, int], int]],
        target: Tuple[int, int],
    ) -> FlankingOutcome:
        if self.phase != GamePhase.ACTION:
            return FlankingOutcome(
                result=MoveResult.INVALID,
                attacker_wins=False,
                total_attackers=0,
                total_defenders=0,
                flanking_directions=0,
                flanking_bonus=1.0,
                remaining_troops=0,
                troops_lost_attacker=0,
                troops_lost_defender=0,
            )
        
        target_row, target_col = target
        dest = self.board.get(target_row, target_col)
        
        if dest is None:
            return FlankingOutcome(
                result=MoveResult.INVALID,
                attacker_wins=False,
                total_attackers=0,
                total_defenders=0,
                flanking_directions=0,
                flanking_bonus=1.0,
                remaining_troops=0,
                troops_lost_attacker=0,
                troops_lost_defender=0,
            )
        
        if dest.owner == self.current_player.id:
            return FlankingOutcome(
                result=MoveResult.INVALID,
                attacker_wins=False,
                total_attackers=0,
                total_defenders=dest.troops,
                flanking_directions=0,
                flanking_bonus=1.0,
                remaining_troops=dest.troops,
                troops_lost_attacker=0,
                troops_lost_defender=0,
            )
        
        attack_sources: List[AttackSource] = []
        troops_to_remove: List[Tuple[Territory, int]] = []
        
        for from_pos, troop_count in attacks:
            from_row, from_col = from_pos
            source = self.board.get(from_row, from_col)
            
            if source is None:
                continue
            if source.owner != self.current_player.id:
                continue
            if not self.board.are_adjacent(from_pos, target):
                continue
            if not source.can_move_from():
                continue
            
            actual_troops = min(troop_count, source.available_troops)
            if actual_troops <= 0:
                continue
            
            attack_sources.append(AttackSource(position=from_pos, troops=actual_troops))
            troops_to_remove.append((source, actual_troops))
        
        if not attack_sources:
            return FlankingOutcome(
                result=MoveResult.INVALID,
                attacker_wins=False,
                total_attackers=0,
                total_defenders=dest.troops,
                flanking_directions=0,
                flanking_bonus=1.0,
                remaining_troops=dest.troops,
                troops_lost_attacker=0,
                troops_lost_defender=0,
            )
        
        for source, count in troops_to_remove:
            source.remove_troops(count)
        
        result = resolve_flanked_combat(
            attacks=attack_sources,
            dest=dest,
            attacker_owner=self.current_player.id,
            config=self.config.combat_config,
        )
        
        self._check_eliminations()
        self._check_win_conditions()
        
        return result
    
    def end_turn(self) -> None:
        if self.phase == GamePhase.GAME_OVER:
            return
        
        start_index = self.current_player_index
        while True:
            self.current_player_index = (self.current_player_index + 1) % len(self.players)
            
            if self.current_player_index == 0:
                self.turn_number += 1
                self._check_turn_limit()
            
            if self.players[self.current_player_index].is_alive:
                break
            
            if self.current_player_index == start_index:
                self._check_win_conditions()
                return
        
        self.phase = GamePhase.REINFORCEMENT
        self._calculate_reinforcements()
    
    def _check_eliminations(self) -> None:
        for player in self.players:
            if player.is_alive:
                territories = self.board.get_territories_for_player(player.id)
                if len(territories) == 0:
                    player.is_alive = False
    
    def _check_win_conditions(self) -> None:
        if self.phase == GamePhase.GAME_OVER:
            return
        
        alive_players = [p for p in self.players if p.is_alive]
        
        if len(alive_players) == 1:
            self.winner = alive_players[0].id
            self.win_condition = WinCondition.ELIMINATION
            self.phase = GamePhase.GAME_OVER
            return
        
        if len(alive_players) == 0:
            self.phase = GamePhase.GAME_OVER
            return
        
        total_territories = self.config.board_size ** 2
        threshold = int(total_territories * self.config.domination_threshold)
        
        for player in alive_players:
            territories = len(self.board.get_territories_for_player(player.id))
            if territories >= threshold:
                self.winner = player.id
                self.win_condition = WinCondition.DOMINATION
                self.phase = GamePhase.GAME_OVER
                return
    
    def _check_turn_limit(self) -> None:
        if self.config.max_turns <= 0:
            return
        
        if self.turn_number > self.config.max_turns:
            best_player = None
            best_count = -1
            
            for player in self.players:
                if player.is_alive:
                    count = len(self.board.get_territories_for_player(player.id))
                    if count > best_count:
                        best_count = count
                        best_player = player.id
            
            self.winner = best_player
            self.win_condition = WinCondition.TURN_LIMIT
            self.phase = GamePhase.GAME_OVER
    
    def get_player_stats(self, player_id: int) -> Dict:
        territories = self.board.get_territories_for_player(player_id)
        troops = self.board.count_troops_for_player(player_id)
        
        return {
            "player_id": player_id,
            "territories": len(territories),
            "troops": troops,
            "is_alive": self.players[player_id].is_alive,
        }
    
    def get_all_stats(self) -> List[Dict]:
        return [self.get_player_stats(p.id) for p in self.players]
    
    def get_valid_moves(self, player_id: int) -> List[Tuple[Tuple[int, int], Tuple[int, int]]]:
        moves = []
        
        for pos in self.board.get_territories_for_player(player_id):
            territory = self.board.get(pos[0], pos[1])
            if territory.can_move_from():
                for neighbor in self.board.get_neighbors(pos[0], pos[1]):
                    moves.append((pos, neighbor))
        
        return moves
    
    def get_attack_targets(self, player_id: int) -> List[Tuple[int, int]]:
        targets = set()
        
        for pos in self.board.get_territories_for_player(player_id):
            territory = self.board.get(pos[0], pos[1])
            if territory.can_move_from():
                for neighbor in self.board.get_neighbors(pos[0], pos[1]):
                    neighbor_territory = self.board.get(neighbor[0], neighbor[1])
                    if neighbor_territory.owner != player_id:
                        targets.add(neighbor)
        
        return list(targets)
    
    def get_flanking_options(
        self, 
        player_id: int, 
        target: Tuple[int, int]
    ) -> List[Tuple[int, int]]:
        options = []
        target_row, target_col = target
        
        for neighbor in self.board.get_neighbors(target_row, target_col):
            territory = self.board.get(neighbor[0], neighbor[1])
            if territory.owner == player_id and territory.can_move_from():
                options.append(neighbor)
        
        return options
    
    def copy(self) -> 'GameState':
        import copy
        
        new_state = GameState.__new__(GameState)
        new_state.config = self.config
        new_state.board = Board(size=self.config.board_size)
        
        for row in range(self.config.board_size):
            for col in range(self.config.board_size):
                orig = self.board.grid[row][col]
                new_state.board.grid[row][col] = Territory(
                    owner=orig.owner,
                    troops=orig.troops,
                )
        
        new_state.players = [
            Player(id=p.id, name=p.name, is_alive=p.is_alive, is_ai=p.is_ai)
            for p in self.players
        ]
        
        new_state.turn_number = self.turn_number
        new_state.current_player_index = self.current_player_index
        new_state.phase = self.phase
        new_state.reinforcements_available = self.reinforcements_available
        new_state.winner = self.winner
        new_state.win_condition = self.win_condition
        new_state._combat_resolver = self._combat_resolver
        
        return new_state
    
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
