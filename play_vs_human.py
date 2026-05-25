from src.game.game_state import GameState, GameConfig
from src.game.renderer import PygameRenderer
from src.game.input_handler import InputHandler
from src.game.game_controller import GameController


def main():
    config = GameConfig(
        board_size=6,
        num_players=2,
        starting_troops=10,
        reinforcement_rate=1.0,
        min_reinforcement=1,
    )

    game = GameState(config)
    game.setup_random_start(seed=None)

    renderer = PygameRenderer(game)
    input_handler = InputHandler(
        cell_size=renderer.cell_size,
        margin_x=renderer.margin_x,
        margin_y=renderer.margin_y
    )

    controller = GameController(game, renderer, input_handler)

    print("\n" + "="*60)
    print("GENETIC CIVILIZATIONS - LOCAL MULTIPLAYER")
    print("="*60)
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
    print("="*60 + "\n")

    try:
        winner = controller.run()

        if winner is not None:
            print(f"\n{'='*60}")
            print(f"GAME OVER - Player {winner} wins!")
            print(f"{'='*60}\n")
        else:
            print("\nGame quit by user.\n")

    finally:
        renderer.close()


if __name__ == "__main__":
    main()