import argparse
from pathlib import Path

from src.genetic.population import Population
from src.genetic.agent import GeneticAgent
from src.genetic.board_setup import create_chokepoint_game, create_chokepoint_game_small
from src.game.renderer import PygameRenderer
from src.game.input_handler import InputHandler
from src.game.game_controller import GameController


def list_trained_genomes(directory: str = "trained_genomes"):
    path = Path(directory)
    if not path.exists():
        print(f"Directory '{directory}' not found")
        return

    genomes = sorted(path.glob("*.json"))
    if not genomes:
        print(f"No trained genomes found in '{directory}'")
        return

    print("\nAvailable trained genomes:")
    for genome_file in genomes:
        print(f"{genome_file}")


def run_vs_ai(genome_path: str, human_player: int = 0, use_small_map: bool = False):
    genome = Population.load_genome(genome_path)

    print(f"Loaded genome from: {genome_path}")
    print(f"You are Player {human_player}")
    print(f"AI is Player {1 - human_player}")
    print(f"Map Size: {'8x8 (Small)' if use_small_map else '12x12 (Standard)'}")
    print(f"\nAI Genome Traits:")
    print(genome)

    if use_small_map:
        game = create_chokepoint_game_small(starting_troops=15, max_turns=300)
    else:
        game = create_chokepoint_game(starting_troops=15, max_turns=300)

    ai_player = 1 - human_player
    ai_agent = GeneticAgent(genome, ai_player)

    renderer = PygameRenderer(game)
    input_handler = InputHandler(
        cell_size=renderer.cell_size,
        margin_x=renderer.margin_x,
        margin_y=renderer.margin_y
    )

    controller = GameController(
        game,
        renderer,
        input_handler,
        ai_agents={ai_player: ai_agent},
        ai_move_delay=800
    )

    print("\n" + "="*60)
    print("GENETIC CIVILIZATIONS - HUMAN VS AI")
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


def main():
    parser = argparse.ArgumentParser(
        description="Play against a trained AI agent",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  Play against best trained AI (you are player 0):
    python play_vs_ai.py

  Play as player 1 against AI:
    python play_vs_ai.py --player 1

  Play against specific genome:
    python play_vs_ai.py --genome trained_genomes/best_gen_100.json

  List available trained genomes:
    python play_vs_ai.py --list
        """
    )

    parser.add_argument(
        '--genome', '-g',
        type=str,
        default='trained_genomes/best_final.json',
        help='Path to trained genome file (default: trained_genomes/best_final.json)'
    )

    parser.add_argument(
        '--player', '-p',
        type=int,
        choices=[0, 1],
        default=0,
        help='Which player you control, 0 or 1 (default: 0)'
    )

    parser.add_argument(
        '--list', '-l',
        action='store_true',
        help='List available trained genomes and exit'
    )

    parser.add_argument(
        '--small-map',
        action='store_true',
        help='Use 8x8 chokepoint map instead of 12x12'
    )

    args = parser.parse_args()

    if args.list:
        list_trained_genomes()
        return

    genome_path = args.genome
    if not Path(genome_path).exists():
        print(f"Error: Genome file '{genome_path}' not found")
        print("\nUse --list to see available trained genomes")
        return

    run_vs_ai(genome_path, args.player, args.small_map)


if __name__ == '__main__':
    main()