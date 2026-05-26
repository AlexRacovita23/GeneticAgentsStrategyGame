from src.game.game_state import GameState
from src.game.player import GamePhase
from src.genetic.action_strategy import ActionStrategy
from src.genetic.genome import Genome
from src.genetic.reinforcement_strategy import ReinforcementStrategy


class GeneticAgent:

    def __init__(self, genome: Genome, player_id: int):
        self.genome = genome
        self.player_id = player_id
        self.reinforcement_strategy = ReinforcementStrategy(genome)
        self.action_strategy = ActionStrategy(genome)

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
        allocated = self.reinforcement_strategy.distribute_reinforcements(
            game_state, self.player_id, game_state.reinforcements_available
        )
        for pos, troops in allocated.items():
            if troops > 0:
                game_state.place_reinforcements(pos, troops)

    def _handle_action(self, game_state: GameState) -> None:
        self.action_strategy.redistribute_troops(game_state, self.player_id)
        self.action_strategy.execute_actions(game_state, self.player_id)
