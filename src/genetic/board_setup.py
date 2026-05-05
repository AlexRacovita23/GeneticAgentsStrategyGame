from src.game.game_state import GameState, GameConfig

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