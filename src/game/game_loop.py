from typing import Optional, Callable
from src.game.game_state import GameState
from src.genetic.agent import GeneticAgent


class GameLoop:

    def __init__(self, game_state: GameState):
        self.game_state = game_state
        self.running = True
        self.iteration = 0

    def run_ai_vs_ai(
        self,
        agent1: GeneticAgent,
        agent2: GeneticAgent,
    ) -> GameState:
        self.iteration = 0

        while not self.game_state.is_game_over:
            if self.game_state.current_player.id == 0:
                agent1.take_turn(self.game_state)
            else:
                agent2.take_turn(self.game_state)
            self.iteration += 1

        return self.game_state

    def run_turn(
        self,
        ai_agent: Optional[GeneticAgent] = None,
        human_action: Optional[Callable[[GameState], None]] = None,
    ) -> bool:
        if self.game_state.is_game_over:
            self.running = False
            return False

        current_player = self.game_state.current_player

        if current_player.is_ai and ai_agent:
            ai_agent.take_turn(self.game_state)
        elif human_action:
            human_action(self.game_state)

        self.iteration += 1
        return not self.game_state.is_game_over
