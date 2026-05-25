from dataclasses import dataclass
from typing import Optional, Tuple, Dict, List
from src.game.game_state import GameState, GamePhase
from src.game.board import MoveResult
from src.game.protocols import AgentProtocol


@dataclass
class UIState:
    selected_cell: Optional[Tuple[int, int]] = None
    highlighted_cells: List[Tuple[int, int]] = None
    troop_selection: int = 0

    flanking_mode: bool = False
    flanking_target: Optional[Tuple[int, int]] = None
    flanking_sources: Dict[Tuple[int, int], int] = None
    flanking_pending_source: Optional[Tuple[int, int]] = None
    flanking_pending_troops: int = 0

    conquered_this_turn: set = None
    immobile_troops: Dict[Tuple[int, int], int] = None

    status_message: str = ""

    def __post_init__(self):
        if self.highlighted_cells is None:
            self.highlighted_cells = []
        if self.flanking_sources is None:
            self.flanking_sources = {}
        if self.conquered_this_turn is None:
            self.conquered_this_turn = set()
        if self.immobile_troops is None:
            self.immobile_troops = {}

    def clear_selection(self) -> None:
        self.selected_cell = None
        self.highlighted_cells = []
        self.troop_selection = 0

    def clear_flanking(self) -> None:
        self.flanking_mode = False
        self.flanking_sources = {}
        self.flanking_target = None
        self.flanking_pending_source = None
        self.flanking_pending_troops = 0
        self.highlighted_cells = []

    def clear_turn_state(self) -> None:
        self.conquered_this_turn.clear()
        self.immobile_troops.clear()

    def get_mobile_troops(self, game_state: GameState, row: int, col: int) -> int:
        return game_state.get_mobile_troops(row, col, self.immobile_troops)

    def add_immobile_troops(self, row: int, col: int, count: int) -> None:
        pos = (row, col)
        self.immobile_troops[pos] = self.immobile_troops.get(pos, 0) + count


class GameController:

    def __init__(
        self,
        game_state: GameState,
        renderer,
        input_handler,
        ai_agents: Optional[Dict[int, AgentProtocol]] = None,
        ai_move_delay: int = 800
    ):
        self.game = game_state
        self.renderer = renderer
        self.input_handler = input_handler
        self.ui_state = UIState()
        self.running = True

        self.ai_agents = ai_agents or {}
        self.ai_move_delay = ai_move_delay

        self._reinforcement_snapshot = {}
        self._initial_reinforcements = 0

    def run(self) -> Optional[int]:
        self._save_reinforcement_snapshot()

        while self.running and not self.game.is_game_over:
            if self._is_ai_turn():
                self._execute_ai_turn()
            else:
                events = self.input_handler.process_events(
                    self.renderer.pygame.event.get(),
                    self.game.board.size
                )

                self._process_events(events)

            self.renderer.render(self.game, self.ui_state)
            self.renderer.tick(60)

        if self.game.is_game_over:
            self.ui_state.status_message = f"GAME OVER - Player {self.game.winner} wins!"
            self.renderer.render(self.game, self.ui_state)
            self.renderer.delay(5000)
            return self.game.winner

        return None

    def _is_ai_turn(self) -> bool:
        return self.game.current_player.id in self.ai_agents

    def _execute_ai_turn(self) -> None:
        current_player_id = self.game.current_player.id
        ai_agent = self.ai_agents[current_player_id]

        self.renderer.render(self.game, self.ui_state)
        self.renderer.delay(self.ai_move_delay)

        ai_agent.take_turn(self.game)

        self.ui_state.clear_turn_state()
        self._save_reinforcement_snapshot()

        self.renderer.render(self.game, self.ui_state)
        self.renderer.delay(self.ai_move_delay)

    def _process_events(self, events) -> None:
        from src.game.input_handler import InputAction

        for event in events:
            if event.action == InputAction.QUIT:
                self.running = False

            elif event.action == InputAction.ESCAPE:
                if self.ui_state.flanking_mode:
                    self.ui_state.clear_flanking()
                    self.ui_state.status_message = "Flanking cancelled"
                else:
                    self.ui_state.clear_selection()

            elif event.action == InputAction.END_TURN:
                self._handle_end_turn()

            elif event.action == InputAction.TOGGLE_FLANKING:
                self._handle_toggle_flanking()

            elif event.action == InputAction.RESET_REINFORCEMENTS:
                self._handle_reset_reinforcements()

            elif event.action == InputAction.SCROLL_UP:
                self._handle_scroll(1)

            elif event.action == InputAction.SCROLL_DOWN:
                self._handle_scroll(-1)

            elif event.action == InputAction.CELL_CLICKED and event.cell_pos:
                self._handle_cell_click(event.cell_pos)

            elif event.action == InputAction.WINDOW_RESIZE and event.window_size:
                self.renderer._handle_resize(*event.window_size)

    def _handle_cell_click(self, cell_pos: Tuple[int, int]) -> None:
        row, col = cell_pos
        territory = self.game.board.get(row, col)
        player_id = self.game.current_player.id

        if self.game.phase == GamePhase.REINFORCEMENT:
            self._handle_reinforcement_click(row, col, territory, player_id)
        elif self.game.phase == GamePhase.ACTION:
            if self.ui_state.flanking_mode:
                self._handle_flanking_click(row, col, territory, player_id)
            else:
                self._handle_action_click(row, col, territory, player_id)

    def _handle_reinforcement_click(self, row: int, col: int, territory, player_id: int) -> None:
        if territory.owner == player_id:
            if self.ui_state.selected_cell == (row, col):
                if self.ui_state.troop_selection > 0:
                    success = self.game.place_reinforcements(
                        (row, col),
                        self.ui_state.troop_selection
                    )
                    if success:
                        self.ui_state.status_message = f"Placed {self.ui_state.troop_selection} troops"
                        self.ui_state.clear_selection()
            else:
                self.ui_state.selected_cell = (row, col)
                self.ui_state.troop_selection = min(1, self.game.reinforcements_available)
                self.ui_state.status_message = f"Selected ({row},{col})"
        else:
            self.ui_state.status_message = "Select your own territory"

    def _handle_action_click(self, row: int, col: int, territory, player_id: int) -> None:
        if self.ui_state.selected_cell is None:
            if territory.owner == player_id:
                mobile = self.ui_state.get_mobile_troops(self.game, row, col)
                if mobile > 0:
                    self.ui_state.selected_cell = (row, col)
                    self.ui_state.troop_selection = mobile
                    self.ui_state.highlighted_cells = list(
                        self.game.board.get_neighbors(row, col)
                    )
                    self.ui_state.status_message = f"Selected ({row},{col}) - {mobile} mobile"
                else:
                    self.ui_state.status_message = "No mobile troops here"
            else:
                self.ui_state.status_message = "Select your own territory"
        else:
            if (row, col) == self.ui_state.selected_cell:
                self.ui_state.clear_selection()
            elif (row, col) in self.ui_state.highlighted_cells:
                if self.ui_state.troop_selection > 0:
                    result = self.game.move_troops(
                        self.ui_state.selected_cell,
                        (row, col),
                        self.ui_state.troop_selection
                    )

                    troops_that_moved = self.ui_state.troop_selection

                    if result.result == MoveResult.REINFORCED:
                        self.ui_state.status_message = f"Moved {troops_that_moved} troops"
                        self.ui_state.add_immobile_troops(row, col, troops_that_moved)
                    elif result.result == MoveResult.CONQUERED:
                        self.ui_state.status_message = f"Conquered! Lost {result.troops_lost_attacker}"
                        self.ui_state.conquered_this_turn.add((row, col))
                        survivors = troops_that_moved - result.troops_lost_attacker
                        self.ui_state.add_immobile_troops(row, col, survivors)
                    elif result.result == MoveResult.REPELLED:
                        self.ui_state.status_message = f"Repelled! Lost {troops_that_moved}"

                    self.ui_state.clear_selection()
            else:
                if territory.owner == player_id:
                    mobile = self.ui_state.get_mobile_troops(self.game, row, col)
                    if mobile > 0:
                        self.ui_state.selected_cell = (row, col)
                        self.ui_state.troop_selection = mobile
                        self.ui_state.highlighted_cells = list(
                            self.game.board.get_neighbors(row, col)
                        )
                        self.ui_state.status_message = f"Selected ({row},{col}) - {mobile} mobile"
                    else:
                        self.ui_state.status_message = "No mobile troops here"
                else:
                    self.ui_state.clear_selection()

    def _handle_flanking_click(self, row: int, col: int, territory, player_id: int) -> None:
        pos = (row, col)

        if self.ui_state.flanking_target is None:
            if territory.owner != player_id:
                has_adjacent = any(
                    self.game.board.get(*neighbor).owner == player_id and
                    self.ui_state.get_mobile_troops(self.game, *neighbor) > 0
                    for neighbor in self.game.board.get_neighbors(row, col)
                )

                if has_adjacent:
                    self.ui_state.flanking_target = pos
                    self.ui_state.highlighted_cells = [
                        neighbor for neighbor in self.game.board.get_neighbors(row, col)
                        if self.game.board.get(*neighbor).owner == player_id and
                        self.ui_state.get_mobile_troops(self.game, *neighbor) > 0
                    ]
                    self.ui_state.status_message = f"Target: ({row},{col}) - select sources"
                else:
                    self.ui_state.status_message = "No adjacent mobile troops!"
            else:
                self.ui_state.status_message = "Select an enemy tile as target"

        elif pos in self.ui_state.highlighted_cells:
            mobile = self.ui_state.get_mobile_troops(self.game, *pos)
            if mobile > 0:
                if self.ui_state.flanking_pending_source == pos:
                    self.ui_state.flanking_sources[pos] = self.ui_state.flanking_pending_troops
                    self.ui_state.status_message = f"Added source {pos} with {self.ui_state.flanking_pending_troops} troops"
                    self.ui_state.flanking_pending_source = None
                    self.ui_state.flanking_pending_troops = 0
                else:
                    self.ui_state.flanking_pending_source = pos
                    self.ui_state.flanking_pending_troops = mobile
                    self.ui_state.status_message = f"Selected source {pos} - {mobile} troops (scroll to adjust, click again to confirm)"

    def _save_reinforcement_snapshot(self) -> None:
        self._reinforcement_snapshot = {}
        player_id = self.game.current_player.id
        for row in range(self.game.board.size):
            for col in range(self.game.board.size):
                territory = self.game.board.get(row, col)
                if territory.owner == player_id:
                    self._reinforcement_snapshot[(row, col)] = territory.troops
        self._initial_reinforcements = self.game.reinforcements_available

    def _restore_reinforcement_snapshot(self) -> None:
        player_id = self.game.current_player.id
        for (row, col), troops in self._reinforcement_snapshot.items():
            territory = self.game.board.get(row, col)
            if territory.owner == player_id:
                territory.troops = troops
        self.game.reinforcements_available = self._initial_reinforcements

    def _handle_end_turn(self) -> None:
        if self.game.phase == GamePhase.REINFORCEMENT:
            self.game.end_reinforcement_phase()
            self.ui_state.clear_selection()
            self.ui_state.status_message = "Action phase"
        elif self.game.phase == GamePhase.ACTION:
            self.game.end_turn()
            self.ui_state.clear_selection()
            self.ui_state.clear_flanking()
            self.ui_state.clear_turn_state()
            self._save_reinforcement_snapshot()
            self.ui_state.status_message = f"Turn {self.game.turn_number}, Player {self.game.current_player.id}"

    def _handle_toggle_flanking(self) -> None:
        if self.game.phase == GamePhase.ACTION:
            if not self.ui_state.flanking_mode:
                self.ui_state.flanking_mode = True
                self.ui_state.clear_selection()
                self.ui_state.status_message = "Select target tile"
            else:
                if self.ui_state.flanking_target and self.ui_state.flanking_sources:
                    attacks = [
                        (pos, troops)
                        for pos, troops in self.ui_state.flanking_sources.items()
                        if self.game.board.are_adjacent(pos, self.ui_state.flanking_target)
                    ]

                    if attacks:
                        result = self.game.coordinated_attack(attacks, self.ui_state.flanking_target)

                        if result.attacker_wins:
                            self.ui_state.status_message = (
                                f"Flanking SUCCESS! {result.flanking_directions} dirs, "
                                f"{result.flanking_bonus:.0%} bonus, {result.remaining_troops} survive"
                            )
                            self.ui_state.conquered_this_turn.add(self.ui_state.flanking_target)
                            self.ui_state.add_immobile_troops(
                                self.ui_state.flanking_target[0],
                                self.ui_state.flanking_target[1],
                                result.remaining_troops
                            )
                        else:
                            self.ui_state.status_message = (
                                f"Flanking FAILED! Lost {result.troops_lost_attacker} troops"
                            )

                        self.ui_state.clear_flanking()
                    else:
                        self.ui_state.status_message = "No adjacent sources!"
                elif not self.ui_state.flanking_target:
                    self.ui_state.status_message = "Select a target first!"
                else:
                    self.ui_state.status_message = "Add at least one source!"

    def _handle_reset_reinforcements(self) -> None:
        if self.game.phase == GamePhase.REINFORCEMENT:
            self._restore_reinforcement_snapshot()
            self.ui_state.clear_selection()
            self.ui_state.status_message = "Reinforcements reset"

    def _handle_scroll(self, direction: int) -> None:
        if self.game.phase == GamePhase.REINFORCEMENT:
            if self.ui_state.selected_cell is None:
                return
            max_troops = self.game.reinforcements_available
            self.ui_state.troop_selection = max(1, min(max_troops, self.ui_state.troop_selection + direction))
            self.ui_state.status_message = f"Troops: {self.ui_state.troop_selection}/{max_troops}"

        elif self.game.phase == GamePhase.ACTION and self.ui_state.flanking_mode:
            if self.ui_state.flanking_pending_source:
                row, col = self.ui_state.flanking_pending_source
                max_troops = self.ui_state.get_mobile_troops(self.game, row, col)
                self.ui_state.flanking_pending_troops = max(1, min(max_troops, self.ui_state.flanking_pending_troops + direction))
                self.ui_state.status_message = f"Flanking troops: {self.ui_state.flanking_pending_troops}/{max_troops}"

        elif self.game.phase == GamePhase.ACTION and not self.ui_state.flanking_mode:
            if self.ui_state.selected_cell is None:
                return
            row, col = self.ui_state.selected_cell
            max_troops = self.ui_state.get_mobile_troops(self.game, row, col)
            self.ui_state.troop_selection = max(1, min(max_troops, self.ui_state.troop_selection + direction))
            self.ui_state.status_message = f"Troops: {self.ui_state.troop_selection}/{max_troops}"
