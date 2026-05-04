from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Tuple, Optional, Dict
import sys

from src.game.game_state import GameState, GamePhase
from src.game.territory import Territory


@dataclass
class RenderConfig:
    cell_size: int = 80
    margin: int = 40
    font_size: int = 16
    show_coordinates: bool = True
    
    player_colors: Tuple[Tuple[int, int, int], ...] = (
        (65, 105, 225),
        (220, 20, 60),
        (34, 139, 34),
        (255, 165, 0),
        (148, 0, 211),
        (0, 206, 209),
    )
    neutral_color: Tuple[int, int, int] = (128, 128, 128)
    empty_color: Tuple[int, int, int] = (50, 50, 50)
    grid_color: Tuple[int, int, int] = (200, 200, 200)
    highlight_color: Tuple[int, int, int] = (255, 255, 0)
    text_color: Tuple[int, int, int] = (255, 255, 255)
    bg_color: Tuple[int, int, int] = (30, 30, 30)


class BaseRenderer(ABC):
    @abstractmethod
    def render(self, game: GameState) -> None:
        pass
    
    @abstractmethod
    def close(self) -> None:
        pass


class HeadlessRenderer(BaseRenderer):
    PLAYER_SYMBOLS = "0123456789ABCDEF"
    
    def __init__(self, config: RenderConfig = None):
        self.config = config or RenderConfig()
    
    def render(self, game: GameState) -> str:
        output = self._render_to_string(game)
        print(output)
        return output
    
    def _render_to_string(self, game: GameState) -> str:
        lines = []
        
        lines.append("=" * 60)
        lines.append(self._render_header(game))
        lines.append("=" * 60)
        lines.append("")
        
        lines.extend(self._render_board(game))
        lines.append("")
        
        lines.extend(self._render_stats(game))
        
        if game.winner is not None:
            lines.append("")
            lines.append(f"WINNER: Player {game.winner} by {game.win_condition.value}!")
        
        lines.append("")
        
        return "\n".join(lines)
    
    def _render_header(self, game: GameState) -> str:
        phase = game.phase.value.upper()
        player = game.current_player.id
        turn = game.turn_number
        
        header = f"Turn {turn} | Player {player}'s {phase}"
        
        if game.phase == GamePhase.REINFORCEMENT:
            header += f" | Reinforcements: {game.reinforcements_available}"
        
        return header
    
    def _render_board(self, game: GameState) -> List[str]:
        lines = []
        size = game.board.size
        
        if self.config.show_coordinates:
            col_header = "    " + "".join(f" {c:^5}" for c in range(size))
            lines.append(col_header)
            lines.append("    " + "-" * (size * 6 + 1))
        
        for row in range(size):
            row_str = f"{row:2} |" if self.config.show_coordinates else "|"
            
            for col in range(size):
                territory = game.board.get(row, col)
                cell = self._render_cell(territory)
                row_str += f" {cell} |"
            
            lines.append(row_str)
            
            if self.config.show_coordinates:
                lines.append("    " + "-" * (size * 6 + 1))
        
        return lines
    
    def _render_cell(self, territory: Territory) -> str:
        if territory.owner == -1:
            if territory.troops == 0:
                return "  . "
            else:
                return f" N{territory.troops:02d}"
        else:
            symbol = self.PLAYER_SYMBOLS[territory.owner % len(self.PLAYER_SYMBOLS)]
            return f"{symbol}:{territory.troops:02d}"
    
    def _render_stats(self, game: GameState) -> List[str]:
        lines = ["Player Stats:"]
        lines.append("-" * 40)
        
        for stats in game.get_all_stats():
            status = "Y" if stats["is_alive"] else "N"
            current = ">" if stats["player_id"] == game.current_player.id else " "
            
            line = (
                f"{current} P{stats['player_id']} [{status}]: "
                f"{stats['territories']:2d} territories, "
                f"{stats['troops']:3d} troops"
            )
            lines.append(line)
        
        return lines
    
    def render_compact(self, game: GameState) -> str:
        stats = []
        for s in game.get_all_stats():
            stats.append(f"P{s['player_id']}:{s['territories']}t/{s['troops']}u")
        
        return f"T{game.turn_number} | {' | '.join(stats)}"
    
    def close(self) -> None:
        pass


class PygameRenderer(BaseRenderer):
    def __init__(self, game: GameState, config: RenderConfig = None):
        self.config = config or RenderConfig()
        self.game = game
        
        try:
            import pygame
            self.pygame = pygame
        except ImportError:
            raise ImportError(
                "Pygame is required for visual rendering. "
                "Install with: pip install pygame"
            )
        
        self.pygame.init()
        
        self.min_width = 600
        self.min_height = 400
        self.info_panel_width = 200
        self.help_bar_height = 60
        
        board_size = game.board.size
        initial_cell_size = self.config.cell_size
        initial_board_pixels = board_size * initial_cell_size
        self.width = initial_board_pixels + 2 * self.config.margin + self.info_panel_width
        self.height = initial_board_pixels + 2 * self.config.margin + self.help_bar_height
        
        self.screen = self.pygame.display.set_mode(
            (self.width, self.height), 
            self.pygame.RESIZABLE
        )
        self.pygame.display.set_caption("Genetic Civilizations")
        
        self._recalculate_dimensions()
        self._create_fonts()
        
        self.selected_cell: Optional[Tuple[int, int]] = None
        self.highlighted_cells: List[Tuple[int, int]] = []
        self.troop_selection: int = 0
        
        self.flanking_mode: bool = False
        self.flanking_target: Optional[Tuple[int, int]] = None
        self.flanking_sources: Dict[Tuple[int, int], int] = {}
        self.flanking_pending_source: Optional[Tuple[int, int]] = None
        self.flanking_pending_troops: int = 0
        
        self.conquered_this_turn: set = set()
        self.immobile_troops: Dict[Tuple[int, int], int] = {}
        
        self.clock = self.pygame.time.Clock()
        self.status_message: str = ""
    
    def _recalculate_dimensions(self) -> None:
        board_size = self.game.board.size
        
        available_width = self.width - self.info_panel_width - 60
        available_height = self.height - self.help_bar_height - 60
        
        cell_size_from_width = available_width // board_size
        cell_size_from_height = available_height // board_size
        
        self.cell_size = max(30, min(cell_size_from_width, cell_size_from_height))
        self.board_pixels = board_size * self.cell_size
        
        self.margin_x = (available_width - self.board_pixels) // 2 + 30
        self.margin_y = (available_height - self.board_pixels) // 2 + 30
        
        self.font_size = max(12, min(20, self.cell_size // 4))
        self.font_size_large = self.font_size + 6
        self.font_size_small = max(10, self.font_size - 4)
    
    def _create_fonts(self) -> None:
        self.font = self.pygame.font.Font(None, self.font_size + 2)
        self.font_large = self.pygame.font.Font(None, self.font_size_large + 4)
        self.font_small = self.pygame.font.Font(None, self.font_size_small + 2)
    
    def _handle_resize(self, new_width: int, new_height: int) -> None:
        self.width = max(self.min_width, new_width)
        self.height = max(self.min_height, new_height)
        
        self.screen = self.pygame.display.set_mode(
            (self.width, self.height),
            self.pygame.RESIZABLE
        )
        
        self._recalculate_dimensions()
        self._create_fonts()

    def render(self, game: GameState = None) -> None:
        if game is not None:
            self.game = game
        
        self.screen.fill(self.config.bg_color)
        
        self._draw_board()
        self._draw_grid_lines()
        self._draw_highlights()
        self._draw_info_panel()
        self._draw_help_bar()
        
        self.pygame.display.flip()
    
    def _get_cell_rect(self, row: int, col: int) -> 'pygame.Rect':
        x = self.margin_x + col * self.cell_size
        y = self.margin_y + row * self.cell_size
        return self.pygame.Rect(x, y, self.cell_size, self.cell_size)
    
    def _get_player_color(self, owner: int) -> Tuple[int, int, int]:
        if owner == -1:
            return self.config.neutral_color
        
        colors = self.config.player_colors
        return colors[owner % len(colors)]
    
    def _draw_board(self) -> None:
        for row in range(self.game.board.size):
            for col in range(self.game.board.size):
                self._draw_cell(row, col)
    
    def _draw_cell(self, row: int, col: int) -> None:
        territory = self.game.board.get(row, col)
        rect = self._get_cell_rect(row, col)
        
        if territory.owner == -1 and territory.troops == 0:
            color = self.config.empty_color
        else:
            color = self._get_player_color(territory.owner)
        
        if (row, col) in self.conquered_this_turn:
            color = tuple(max(0, c - 60) for c in color)
        
        self.pygame.draw.rect(self.screen, color, rect)
        
        if territory.troops > 0:
            text = self.font_large.render(str(territory.troops), True, self.config.text_color)
            text_rect = text.get_rect(center=rect.center)
            self.screen.blit(text, text_rect)
        
        if territory.owner >= 0:
            owner_text = self.font_small.render(f"P{territory.owner}", True, (200, 200, 200))
            owner_rect = owner_text.get_rect(topleft=(rect.left + 3, rect.top + 3))
            self.screen.blit(owner_text, owner_rect)
        
        pos = (row, col)
        
        if territory.owner == self.game.current_player.id and self.game.phase == GamePhase.ACTION:
            mobile = self.get_mobile_troops(row, col)
            avail_text = self.font.render(f"{mobile} available", True, (100, 255, 100))
            avail_rect = avail_text.get_rect(bottomleft=(rect.left + 3, rect.bottom - 3))
            self.screen.blit(avail_text, avail_rect)
        
        if (row, col) in self.conquered_this_turn:
            new_text = self.font_small.render("NEW", True, (255, 255, 100))
            new_rect = new_text.get_rect(topright=(rect.right - 3, rect.top + 3))
            self.screen.blit(new_text, new_rect)
        
        if pos in self.flanking_sources:
            troops = self.flanking_sources[pos]
            indicator = self.font.render(f">{troops}", True, (255, 100, 100))
            ind_rect = indicator.get_rect(bottomright=(rect.right - 3, rect.bottom - 3))
            self.screen.blit(indicator, ind_rect)
        
        elif self.flanking_pending_source == pos:
            indicator = self.font.render(f"?{self.flanking_pending_troops}", True, (100, 255, 100))
            ind_rect = indicator.get_rect(bottomright=(rect.right - 3, rect.bottom - 3))
            self.screen.blit(indicator, ind_rect)
    
    def _draw_grid_lines(self) -> None:
        size = self.game.board.size
        
        for i in range(size + 1):
            y = self.margin_y + i * self.cell_size
            start = (self.margin_x, y)
            end = (self.margin_x + self.board_pixels, y)
            self.pygame.draw.line(self.screen, self.config.grid_color, start, end, 1)
            
            x = self.margin_x + i * self.cell_size
            start = (x, self.margin_y)
            end = (x, self.margin_y + self.board_pixels)
            self.pygame.draw.line(self.screen, self.config.grid_color, start, end, 1)
        
        if self.config.show_coordinates:
            for i in range(size):
                text = self.font_small.render(str(i), True, self.config.text_color)
                x = self.margin_x + i * self.cell_size + self.cell_size // 2
                self.screen.blit(text, (x - 4, self.margin_y - 18))
                
                y = self.margin_y + i * self.cell_size + self.cell_size // 2
                self.screen.blit(text, (self.margin_x - 18, y - 6))

    def _draw_highlights(self) -> None:
        for row, col in self.highlighted_cells:
            rect = self._get_cell_rect(row, col)
            self.pygame.draw.rect(self.screen, self.config.highlight_color, rect, 3)
        
        if self.selected_cell:
            row, col = self.selected_cell
            rect = self._get_cell_rect(row, col)
            self.pygame.draw.rect(self.screen, (255, 255, 255), rect, 4)
        
        if self.flanking_target:
            row, col = self.flanking_target
            rect = self._get_cell_rect(row, col)
            self.pygame.draw.rect(self.screen, (255, 0, 0), rect, 5)
        
        for pos in self.flanking_sources:
            row, col = pos
            rect = self._get_cell_rect(row, col)
            self.pygame.draw.rect(self.screen, (255, 165, 0), rect, 4)
        
        if self.flanking_pending_source:
            row, col = self.flanking_pending_source
            rect = self._get_cell_rect(row, col)
            self.pygame.draw.rect(self.screen, (0, 255, 0), rect, 4)
    
    def _draw_info_panel(self) -> None:
        panel_x = self.margin_x + self.board_pixels + 20
        y = self.margin_y
        
        turn_text = f"Turn {self.game.turn_number}"
        text = self.font_large.render(turn_text, True, self.config.text_color)
        self.screen.blit(text, (panel_x, y))
        y += 30
        
        player = self.game.current_player
        player_color = self._get_player_color(player.id)
        player_text = f"Player {player.id}'s Turn"
        text = self.font.render(player_text, True, player_color)
        self.screen.blit(text, (panel_x, y))
        y += 25
        
        phase_text = f"Phase: {self.game.phase.value}"
        text = self.font.render(phase_text, True, self.config.text_color)
        self.screen.blit(text, (panel_x, y))
        y += 25
        
        if self.flanking_mode:
            mode_text = "MODE: FLANKING"
            text = self.font.render(mode_text, True, (255, 165, 0))
            self.screen.blit(text, (panel_x, y))
            y += 20
            
            if self.flanking_target:
                target_text = f"Target: {self.flanking_target}"
                text = self.font_small.render(target_text, True, (255, 100, 100))
                self.screen.blit(text, (panel_x, y))
                y += 18
            
            if self.flanking_sources:
                total = sum(self.flanking_sources.values())
                queue_text = f"Sources: {len(self.flanking_sources)} ({total} troops)"
                text = self.font_small.render(queue_text, True, (255, 165, 0))
                self.screen.blit(text, (panel_x, y))
                y += 18
            
            if self.flanking_pending_source:
                pending_text = f"Pending: {self.flanking_pending_source}"
                text = self.font_small.render(pending_text, True, (100, 255, 100))
                self.screen.blit(text, (panel_x, y))
                y += 18
        
        y += 10
        
        if self.game.phase == GamePhase.REINFORCEMENT:
            reinf_text = f"Reinforcements: {self.game.reinforcements_available}"
            text = self.font.render(reinf_text, True, (100, 255, 100))
            self.screen.blit(text, (panel_x, y))
            y += 20
            
            if self.selected_cell:
                sel_text = f"Placing: {self.troop_selection}"
                text = self.font.render(sel_text, True, (100, 255, 100))
                self.screen.blit(text, (panel_x, y))
        
        elif self.selected_cell and not self.flanking_mode:
            mobile = self.get_mobile_troops(*self.selected_cell)
            sel_text = f"Moving: {self.troop_selection}/{mobile}"
            text = self.font.render(sel_text, True, (100, 200, 255))
            self.screen.blit(text, (panel_x, y))
        
        y += 40
        
        text = self.font.render("--- Stats ---", True, self.config.text_color)
        self.screen.blit(text, (panel_x, y))
        y += 25
        
        for stats in self.game.get_all_stats():
            color = self._get_player_color(stats["player_id"])
            if not stats["is_alive"]:
                color = (100, 100, 100)
            
            stat_text = f"P{stats['player_id']}: {stats['territories']}T / {stats['troops']}U"
            text = self.font.render(stat_text, True, color)
            self.screen.blit(text, (panel_x, y))
            y += 22
        
        if self.game.winner is not None:
            y += 20
            winner_text = f"WINNER: P{self.game.winner}!"
            text = self.font_large.render(winner_text, True, (255, 215, 0))
            self.screen.blit(text, (panel_x, y))
        
        if self.status_message:
            y += 30
            max_chars = max(15, (self.width - panel_x - 10) // 8)
            words = self.status_message.split()
            lines = []
            current_line = ""
            for word in words:
                test_line = current_line + " " + word if current_line else word
                if len(test_line) <= max_chars:
                    current_line = test_line
                else:
                    if current_line:
                        lines.append(current_line)
                    current_line = word
            if current_line:
                lines.append(current_line)
            
            for line in lines:
                text = self.font.render(line, True, (255, 200, 100))
                self.screen.blit(text, (panel_x, y))
                y += 18
    
    def _draw_help_bar(self) -> None:
        y = self.height - 45
        x = self.margin_x
        
        if self.game.phase == GamePhase.REINFORCEMENT:
            help_text = "Click: Select | Scroll: Adjust | Click same: Place | R: Reset | Space: End"
        elif self.flanking_mode:
            if not self.flanking_target:
                help_text = "Click enemy tile to set target | Esc: Cancel"
            elif self.flanking_pending_source:
                help_text = "Scroll: Adjust troops | Click: Confirm source | Esc: Cancel"
            else:
                help_text = "Click own adjacent: Add source | F: Execute attack | Esc: Cancel"
        else:
            help_text = "Click: Select/Move | Scroll: Troops | F: Flank mode | Space: End Turn"
        
        text = self.font_small.render(help_text, True, (180, 180, 180))
        self.screen.blit(text, (x, y))
        
        y += 18
        help_text2 = "Right-click: Clear | Q: Quit | Drag window edges to resize"
        text2 = self.font_small.render(help_text2, True, (140, 140, 140))
        self.screen.blit(text2, (x, y))

    def get_cell_at_pixel(self, x: int, y: int) -> Optional[Tuple[int, int]]:
        col = (x - self.margin_x) // self.cell_size
        row = (y - self.margin_y) // self.cell_size
        
        if 0 <= row < self.game.board.size and 0 <= col < self.game.board.size:
            return (int(row), int(col))
        return None
    
    def select_cell(self, row: int, col: int) -> None:
        self.selected_cell = (row, col)
        self.highlighted_cells = []
        
        territory = self.game.board.get(row, col)
        
        if territory.owner == self.game.current_player.id:
            if self.game.phase == GamePhase.REINFORCEMENT:
                self.troop_selection = min(1, self.game.reinforcements_available)
            else:
                mobile = self.get_mobile_troops(row, col)
                self.troop_selection = mobile
                
                if mobile > 0:
                    for neighbor in self.game.board.get_neighbors(row, col):
                        self.highlighted_cells.append(neighbor)
    
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

    def get_mobile_troops(self, row: int, col: int) -> int:
        territory = self.game.board.get(row, col)
        if territory.owner == -1:
            return 0
        
        immobile = self.immobile_troops.get((row, col), 0)
        mobile = territory.troops - immobile - 1
        return max(0, mobile)
    
    def add_immobile_troops(self, row: int, col: int, count: int) -> None:
        pos = (row, col)
        self.immobile_troops[pos] = self.immobile_troops.get(pos, 0) + count
    
    def clear_turn_state(self) -> None:
        self.conquered_this_turn.clear()
        self.immobile_troops.clear()
    
    def adjust_troops(self, delta: int) -> None:
        if self.game.phase == GamePhase.REINFORCEMENT:
            max_troops = self.game.reinforcements_available
            self.troop_selection = max(1, min(max_troops, self.troop_selection + delta))
        elif self.flanking_pending_source:
            mobile = self.get_mobile_troops(*self.flanking_pending_source)
            self.flanking_pending_troops = max(1, min(mobile, self.flanking_pending_troops + delta))
        elif self.selected_cell:
            mobile = self.get_mobile_troops(*self.selected_cell)
            self.troop_selection = max(1, min(mobile, self.troop_selection + delta))

    def handle_events(self) -> List:
        events = []
        
        for event in self.pygame.event.get():
            if event.type == self.pygame.QUIT:
                events.append(("quit", None))
            
            elif event.type == self.pygame.VIDEORESIZE:
                self._handle_resize(event.w, event.h)
            
            elif event.type == self.pygame.MOUSEBUTTONDOWN:
                if event.button == 1:
                    cell = self.get_cell_at_pixel(*event.pos)
                    if cell:
                        events.append(("click", cell))
                elif event.button == 3:
                    events.append(("right_click", None))
                elif event.button == 4:
                    events.append(("scroll_up", None))
                elif event.button == 5:
                    events.append(("scroll_down", None))
            
            elif event.type == self.pygame.KEYDOWN:
                if event.key == self.pygame.K_ESCAPE:
                    events.append(("escape", None))
                elif event.key == self.pygame.K_SPACE:
                    events.append(("space", None))
                elif event.key == self.pygame.K_RETURN:
                    events.append(("enter", None))
                elif event.key == self.pygame.K_UP:
                    events.append(("up", None))
                elif event.key == self.pygame.K_DOWN:
                    events.append(("down", None))
                elif event.key == self.pygame.K_f:
                    events.append(("f_key", None))
                elif event.key == self.pygame.K_r:
                    events.append(("r_key", None))
                elif event.key == self.pygame.K_q:
                    events.append(("quit", None))
        
        return events

    def wait_for_click(self) -> Optional[Tuple[int, int]]:
        while True:
            for event in self.pygame.event.get():
                if event.type == self.pygame.QUIT:
                    return None
                
                if event.type == self.pygame.MOUSEBUTTONDOWN:
                    if event.button == 1:
                        cell = self.get_cell_at_pixel(*event.pos)
                        if cell:
                            return cell
            
            self.clock.tick(30)
    
    def delay(self, ms: int) -> None:
        self.pygame.time.delay(ms)
    
    def tick(self, fps: int = 60) -> None:
        self.clock.tick(fps)
    
    def close(self) -> None:
        self.pygame.quit()


def create_renderer(
    game: GameState,
    headless: bool = False,
    config: RenderConfig = None,
) -> BaseRenderer:
    if headless:
        return HeadlessRenderer(config)
    else:
        return PygameRenderer(game, config)

def run_interactive_demo():
    from src.game.game_state import GameState, GameConfig
    from src.game.board import MoveResult
    
    config = GameConfig(board_size=6, num_players=2)
    game = GameState(config)
    game.setup_random_start(seed=42)
    
    renderer = PygameRenderer(game)
    
    reinforcement_snapshot = {}
    initial_reinforcements = 0
    
    def save_reinforcement_snapshot():
        nonlocal reinforcement_snapshot, initial_reinforcements
        reinforcement_snapshot = {}
        player_id = game.current_player.id
        for row in range(game.board.size):
            for col in range(game.board.size):
                territory = game.board.get(row, col)
                if territory.owner == player_id:
                    reinforcement_snapshot[(row, col)] = territory.troops
        initial_reinforcements = game.reinforcements_available
    
    def restore_reinforcement_snapshot():
        player_id = game.current_player.id
        for (row, col), troops in reinforcement_snapshot.items():
            territory = game.board.get(row, col)
            if territory.owner == player_id:
                territory.troops = troops
        game.reinforcements_available = initial_reinforcements
    
    save_reinforcement_snapshot()
    
    print("\nREINFORCEMENT PHASE:")
    print("  Click      - Select province")
    print("  Scroll     - Adjust troops")
    print("  Click same - Place reinforcements")
    print("  R          - Reset all placements")
    print("  Space      - End phase")
    print("\nACTION PHASE:")
    print("  Click      - Select source then destination")
    print("  Scroll     - Adjust troops")
    print("  F          - Toggle flanking mode")
    print("  Space      - End turn")
    print("\nNOTE: Each troop can only move once per turn!")
    print("      Green number shows mobile troops remaining.")
    print("=" * 50)
    
    running = True
    
    while running:
        events = renderer.handle_events()
        
        for event_type, data in events:
            if event_type == "quit":
                running = False
            
            elif event_type == "escape":
                if renderer.flanking_mode:
                    renderer.clear_flanking()
                    renderer.status_message = "Flanking cancelled"
                else:
                    renderer.clear_selection()
            
            elif event_type == "right_click":
                renderer.clear_selection()
                if renderer.flanking_mode:
                    renderer.clear_flanking()
            
            elif event_type in ("up", "scroll_up"):
                renderer.adjust_troops(1)
            
            elif event_type in ("down", "scroll_down"):
                renderer.adjust_troops(-1)
            
            elif event_type == "r_key":
                if game.phase == GamePhase.REINFORCEMENT:
                    restore_reinforcement_snapshot()
                    renderer.clear_selection()
                    renderer.status_message = "Reinforcements reset"
            
            elif event_type == "f_key":
                if game.phase == GamePhase.ACTION:
                    if not renderer.flanking_mode:
                        renderer.flanking_mode = True
                        renderer.clear_selection()
                        renderer.status_message = "Select target tile"
                    else:
                        if renderer.flanking_target and renderer.flanking_sources:
                            if renderer.flanking_pending_source:
                                pos = renderer.flanking_pending_source
                                renderer.flanking_sources[pos] = renderer.flanking_pending_troops
                                renderer.flanking_pending_source = None
                                renderer.flanking_pending_troops = 0
                            
                            attacks = [
                                (pos, troops) 
                                for pos, troops in renderer.flanking_sources.items()
                                if game.board.are_adjacent(pos, renderer.flanking_target)
                            ]
                            
                            if attacks:
                                result = game.coordinated_attack(attacks, renderer.flanking_target)
                                
                                if result.attacker_wins:
                                    renderer.status_message = (
                                        f"Flanking SUCCESS! {result.flanking_directions} dirs, "
                                        f"{result.flanking_bonus:.0%} bonus, {result.remaining_troops} survive"
                                    )
                                    renderer.conquered_this_turn.add(renderer.flanking_target)
                                    renderer.add_immobile_troops(
                                        renderer.flanking_target[0],
                                        renderer.flanking_target[1],
                                        result.remaining_troops
                                    )
                                else:
                                    renderer.status_message = (
                                        f"Flanking FAILED! Lost {result.troops_lost_attacker} troops"
                                    )
                                
                                renderer.clear_flanking()
                            else:
                                renderer.status_message = "No adjacent sources!"
                        elif not renderer.flanking_target:
                            renderer.status_message = "Select a target first!"
                        else:
                            renderer.status_message = "Add at least one source!"
            
            elif event_type == "click":
                row, col = data
                territory = game.board.get(row, col)
                player_id = game.current_player.id
                
                if game.phase == GamePhase.REINFORCEMENT:
                    if territory.owner == player_id:
                        if renderer.selected_cell == (row, col):
                            if renderer.troop_selection > 0:
                                success = game.place_reinforcements(
                                    (row, col), 
                                    renderer.troop_selection
                                )
                                if success:
                                    renderer.status_message = f"Placed {renderer.troop_selection} troops"
                                    renderer.clear_selection()
                        else:
                            renderer.select_cell(row, col)
                            renderer.status_message = f"Selected ({row},{col})"
                    else:
                        renderer.status_message = "Select your own territory"
                
                elif game.phase == GamePhase.ACTION and renderer.flanking_mode:
                    pos = (row, col)
                    
                    if renderer.flanking_target is None:
                        if territory.owner != player_id:
                            has_adjacent = False
                            for neighbor in game.board.get_neighbors(row, col):
                                n_terr = game.board.get(*neighbor)
                                mobile = renderer.get_mobile_troops(*neighbor)
                                if n_terr.owner == player_id and mobile > 0:
                                    has_adjacent = True
                                    break
                            
                            if has_adjacent:
                                renderer.flanking_target = pos
                                renderer.highlighted_cells = []
                                for neighbor in game.board.get_neighbors(row, col):
                                    n_terr = game.board.get(*neighbor)
                                    mobile = renderer.get_mobile_troops(*neighbor)
                                    if n_terr.owner == player_id and mobile > 0:
                                        renderer.highlighted_cells.append(neighbor)
                                renderer.status_message = f"Target: ({row},{col}) - select sources"
                            else:
                                renderer.status_message = "No adjacent mobile troops!"
                        else:
                            renderer.status_message = "Select an enemy tile as target"
                    
                    elif renderer.flanking_pending_source is not None:
                        pending_pos = renderer.flanking_pending_source
                        renderer.flanking_sources[pending_pos] = renderer.flanking_pending_troops
                        renderer.flanking_pending_source = None
                        renderer.flanking_pending_troops = 0
                        
                        total = sum(renderer.flanking_sources.values())
                        renderer.status_message = f"Confirmed! {len(renderer.flanking_sources)} sources, {total} troops. F to attack"
                        
                        if pos in renderer.highlighted_cells and pos != pending_pos:
                            mobile = renderer.get_mobile_troops(*pos)
                            if mobile > 0:
                                renderer.flanking_pending_source = pos
                                if pos in renderer.flanking_sources:
                                    renderer.flanking_pending_troops = renderer.flanking_sources[pos]
                                else:
                                    renderer.flanking_pending_troops = mobile
                                renderer.status_message = f"Adjusting {pos}: {renderer.flanking_pending_troops} troops"
                    
                    elif pos in renderer.highlighted_cells:
                        mobile = renderer.get_mobile_troops(*pos)
                        if mobile > 0:
                            renderer.flanking_pending_source = pos
                            if pos in renderer.flanking_sources:
                                renderer.flanking_pending_troops = renderer.flanking_sources[pos]
                            else:
                                renderer.flanking_pending_troops = mobile
                            renderer.status_message = f"Source {pos}: scroll to adjust, click to confirm"
                        else:
                            renderer.status_message = "No mobile troops here!"
                    
                    elif pos == renderer.flanking_target:
                        total = sum(renderer.flanking_sources.values())
                        renderer.status_message = f"Target selected. {len(renderer.flanking_sources)} sources, {total} troops. F to attack"
                    
                    else:
                        renderer.status_message = "Click highlighted tiles to add sources"
                
                elif game.phase == GamePhase.ACTION:
                    if renderer.selected_cell is None:
                        if territory.owner == player_id:
                            mobile = renderer.get_mobile_troops(row, col)
                            if mobile > 0:
                                renderer.select_cell(row, col)
                                renderer.status_message = f"Selected ({row},{col}) - {mobile} mobile"
                            else:
                                renderer.status_message = "No mobile troops here"
                        else:
                            renderer.status_message = "Select your own territory"
                    else:
                        if (row, col) == renderer.selected_cell:
                            renderer.clear_selection()
                        elif (row, col) in renderer.highlighted_cells:
                            if renderer.troop_selection > 0:
                                result = game.move_troops(
                                    renderer.selected_cell,
                                    (row, col),
                                    renderer.troop_selection
                                )
                                
                                troops_that_moved = renderer.troop_selection
                                
                                if result.result == MoveResult.REINFORCED:
                                    renderer.status_message = f"Moved {troops_that_moved} troops"
                                    renderer.add_immobile_troops(row, col, troops_that_moved)
                                    
                                elif result.result == MoveResult.CONQUERED:
                                    renderer.status_message = f"Conquered! Lost {result.troops_lost_attacker}"
                                    renderer.conquered_this_turn.add((row, col))
                                    survivors = troops_that_moved - result.troops_lost_attacker
                                    renderer.add_immobile_troops(row, col, survivors)
                                    
                                elif result.result == MoveResult.REPELLED:
                                    renderer.status_message = f"Repelled! Lost {troops_that_moved}"
                                
                                renderer.clear_selection()
                        else:
                            if territory.owner == player_id:
                                mobile = renderer.get_mobile_troops(row, col)
                                if mobile > 0:
                                    renderer.select_cell(row, col)
                                    renderer.status_message = f"Selected ({row},{col}) - {mobile} mobile"
                                else:
                                    renderer.status_message = "No mobile troops here"
                            else:
                                renderer.clear_selection()
            
            elif event_type == "space":
                if game.phase == GamePhase.REINFORCEMENT:
                    game.end_reinforcement_phase()
                    renderer.clear_selection()
                    renderer.status_message = "Action phase"
                
                elif game.phase == GamePhase.ACTION:
                    game.end_turn()
                    renderer.clear_selection()
                    renderer.clear_flanking()
                    renderer.clear_turn_state()
                    save_reinforcement_snapshot()
                    renderer.status_message = f"Turn {game.turn_number}, Player {game.current_player.id}"
        
        renderer.render(game)
        renderer.tick(60)
        
        if game.is_game_over:
            print(f"\nGame Over! Winner: Player {game.winner}")
            renderer.status_message = f"GAME OVER - Player {game.winner} wins!"
            renderer.render(game)
            renderer.delay(5000)
            running = False
    
    renderer.close()

if __name__ == "__main__":
    import sys
    
    if "--headless" in sys.argv:
        from src.game.game_state import GameState, GameConfig
        
        config = GameConfig(board_size=6, num_players=2)
        game = GameState(config)
        game.setup_random_start(seed=42)
        
        renderer = HeadlessRenderer()
        renderer.render(game)
    else:
        run_interactive_demo()
