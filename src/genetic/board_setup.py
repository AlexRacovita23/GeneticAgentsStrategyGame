from src.game.game_state import GameState
from src.game.player import GameConfig


# def setup_chokepoint_board(game_state: GameState, starting_troops: int = 15) -> None:
#     size = game_state.config.board_size
#     if size != 16:
#         raise ValueError(f"Chokepoint board requires board_size=16, got {size}")

#     for row in range(4, 12):
#         for col in (3, 12):
#             tile = game_state.board.grid[row][col]
#             tile.is_blocked = True
#             tile.owner = -1
#             tile.troops = 0

#     game_state.board.grid[0][0].set_owner(0, starting_troops)
#     game_state.board.grid[15][15].set_owner(1, starting_troops)

def setup_chokepoint_board(game_state: GameState, starting_troops: int = 15) -> None:
    size = game_state.config.board_size
    if size != 12:
        raise ValueError(f"Chokepoint board requires board_size=12, got {size}")

    for row in range(3, 9):
        for col in (2, 9):
            tile = game_state.board.grid[row][col]
            tile.is_blocked = True
            tile.owner = -1
            tile.troops = 0

    game_state.board.grid[0][0].set_owner(0, starting_troops)
    game_state.board.grid[11][11].set_owner(1, starting_troops)

def setup_chokepoint_board_small(game_state: GameState, starting_troops: int = 15) -> None:
    size = game_state.config.board_size
    if size != 8:
        raise ValueError(f"Chokepoint board requires board_size=8, got {size}")

    for row in range(2, 6):
        for col in (1, 6):
            tile = game_state.board.grid[row][col]
            tile.is_blocked = True
            tile.owner = -1
            tile.troops = 0

    game_state.board.grid[0][0].set_owner(0, starting_troops)
    game_state.board.grid[7][7].set_owner(1, starting_troops)

def create_chokepoint_game(
    starting_troops: int = 15,
    reinforcement_rate: float = 1.0,
    max_turns: int = 200,
) -> GameState:
    config = GameConfig(
        board_size=12,
        num_players=2,
        starting_troops=starting_troops,
        reinforcement_rate=reinforcement_rate,
        min_reinforcement=1,
        max_turns=max_turns,
    )

    game_state = GameState(config)
    game_state.setup_random_start(seed=None)

    setup_chokepoint_board(game_state, starting_troops)

    return game_state

def create_chokepoint_game_small(
    starting_troops: int = 15,
    reinforcement_rate: float = 1.0,
    max_turns: int = 200,
) -> GameState:
    config = GameConfig(
        board_size=8,
        num_players=2,
        starting_troops=starting_troops,
        reinforcement_rate=reinforcement_rate,
        min_reinforcement=1,
        max_turns=max_turns,
    )

    game_state = GameState(config)
    game_state.setup_random_start(seed=None)

    setup_chokepoint_board_small(game_state, starting_troops)

    return game_state
