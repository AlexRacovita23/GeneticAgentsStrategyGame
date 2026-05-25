import pygame

from dataclasses import dataclass
from enum import Enum
from typing import List, Optional, Tuple


class InputAction(Enum):
    QUIT = "quit"
    CELL_CLICKED = "cell_clicked"
    ESCAPE = "escape"
    WINDOW_RESIZE = "window_resize"
    END_TURN = "end_turn"
    TOGGLE_FLANKING = "toggle_flanking"
    RESET_REINFORCEMENTS = "reset_reinforcements"
    SCROLL_UP = "scroll_up"
    SCROLL_DOWN = "scroll_down"
    NONE = "none"


@dataclass
class InputEvent:
    action: InputAction
    cell_pos: Optional[Tuple[int, int]] = None
    mouse_pos: Optional[Tuple[int, int]] = None
    window_size: Optional[Tuple[int, int]] = None


class InputHandler:

    def __init__(self, cell_size: int, margin_x: int, margin_y: int):
        self.cell_size = cell_size
        self.margin_x = margin_x
        self.margin_y = margin_y

    def update_dimensions(self, cell_size: int, margin_x: int, margin_y: int) -> None:
        self.cell_size = cell_size
        self.margin_x = margin_x
        self.margin_y = margin_y

    def get_cell_from_mouse(
        self,
        mouse_x: int,
        mouse_y: int,
        board_size: int,
    ) -> Optional[Tuple[int, int]]:
        rel_x = mouse_x - self.margin_x
        rel_y = mouse_y - self.margin_y

        if rel_x < 0 or rel_y < 0:
            return None

        col = rel_x // self.cell_size
        row = rel_y // self.cell_size

        if 0 <= row < board_size and 0 <= col < board_size:
            return (row, col)
        return None

    def process_events(self, pygame_events: List, board_size: int) -> List[InputEvent]:
        events: List[InputEvent] = []

        for event in pygame_events:

            if event.type == pygame.QUIT:
                events.append(InputEvent(action=InputAction.QUIT))

            elif event.type == pygame.VIDEORESIZE:
                width = getattr(event, "w", getattr(event, "width", 800))
                height = getattr(event, "h", getattr(event, "height", 600))
                events.append(InputEvent(
                    action=InputAction.WINDOW_RESIZE,
                    window_size=(width, height),
                ))

            elif event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1:
                    cell_pos = self.get_cell_from_mouse(
                        event.pos[0], event.pos[1], board_size
                    )
                    events.append(InputEvent(
                        action=InputAction.CELL_CLICKED,
                        cell_pos=cell_pos,
                        mouse_pos=event.pos,
                    ))

            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    events.append(InputEvent(action=InputAction.ESCAPE))
                elif event.key == pygame.K_SPACE:
                    events.append(InputEvent(action=InputAction.END_TURN))
                elif event.key == pygame.K_f:
                    events.append(InputEvent(action=InputAction.TOGGLE_FLANKING))
                elif event.key == pygame.K_r:
                    events.append(InputEvent(action=InputAction.RESET_REINFORCEMENTS))

            elif event.type == pygame.MOUSEWHEEL:
                scroll_y = getattr(event, "y", 0)
                if scroll_y > 0:
                    events.append(InputEvent(action=InputAction.SCROLL_UP))
                elif scroll_y < 0:
                    events.append(InputEvent(action=InputAction.SCROLL_DOWN))

        return events
