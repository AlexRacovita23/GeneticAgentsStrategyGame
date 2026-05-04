from typing import Tuple
from src.game.game_state import GameState, GameConfig
from src.game.territory import Territory


def setup_chokepoint_board(game_state: GameState, starting_troops: int = 15) -> None:
    size = game_state.config.board_size
    
    if size != 16:
        raise ValueError(f"Chokepoint board requires size 16, got {size}")
    
    # Place walls at columns 3 and 12, rows 4-11 (centered)
    for row in range(4, 12):
        game_state.board.grid[row][3].is_blocked = True
        game_state.board.grid[row][3].owner = -1
        game_state.board.grid[row][3].troops = 0
        
        game_state.board.grid[row][12].is_blocked = True
        game_state.board.grid[row][12].owner = -1
        game_state.board.grid[row][12].troops = 0
    
    game_state.board.grid[0][0].set_owner(0, starting_troops)
    game_state.board.grid[15][15].set_owner(1, starting_troops)
    
    game_state.turn_number = 1
    game_state.phase = game_state.phase.REINFORCEMENT
    game_state._calculate_reinforcements()


def create_chokepoint_game(starting_troops: int = 15, 
                           reinforcement_rate: float = 1.0,
                           max_turns: int = 200) -> GameState:
    config = GameConfig(
        board_size=16,
        num_players=2,
        starting_troops=starting_troops,
        reinforcement_rate=reinforcement_rate,
        min_reinforcement=1,
        max_turns=max_turns,
    )
    
    game_state = GameState(config)
    setup_chokepoint_board(game_state, starting_troops)
    
    return game_state


def visualize_chokepoint_board() -> str:
    lines = ["Chokepoint Board Layout (16x16):"]
    lines.append("=" * 80)
    lines.append("")
    lines.append("Columns: 0  1  2 | 3 | 4  5  6  7  8  9 10 11 | 12 | 13 14 15")
    lines.append("         LEFT    |W|        CENTER          |W |      RIGHT")
    lines.append("")
    lines.append("Rows 0-3:   Accessible (P0 starts at 0,0)")
    lines.append("Rows 4-11:  WALLS at columns 3 and 12")
    lines.append("Rows 12-15: Accessible (P1 starts at 15,15)")
    lines.append("")
    lines.append("Strategic points:")
    lines.append("  - Chokepoint entrances: rows 3, 12 at columns 3 and 12")
    lines.append("  - Left flank: columns 0-2")
    lines.append("  - Center: columns 4-11")
    lines.append("  - Right flank: columns 13-15")
    lines.append("=" * 80)
    
    return "\n".join(lines)