#!/usr/bin/env python3
import argparse
from pathlib import Path

from src.genetic.population import Population
from src.genetic.agent import GeneticAgent
from src.genetic.board_setup import create_chokepoint_game
from src.game.renderer import PygameRenderer
from src.game.game_state import GamePhase
from src.game.board import MoveResult


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


def run_vs_ai(genome_path: str, human_player: int = 0):
    genome = Population.load_genome(genome_path)
    
    print(f"Loaded genome from: {genome_path}")
    print(f"You are Player {human_player}")
    print(f"AI is Player {1 - human_player}")
    print(f"\nAI Genome Traits:")
    print(genome)
    
    game = create_chokepoint_game(starting_troops=15, max_turns=300)
    
    ai_player = 1 - human_player
    ai_agent = GeneticAgent(genome, ai_player)
    
    renderer = PygameRenderer(game)
    
    running = True
    
    reinforcement_snapshot = {}
    initial_reinforcements = 0
    
    def save_reinforcement_snapshot():
        nonlocal initial_reinforcements
        reinforcement_snapshot.clear()
        player_id = game.current_player.id
        for row in range(game.config.board_size):
            for col in range(game.config.board_size):
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
    print("Click      - Select province")
    print("Scroll     - Adjust troops")
    print("Click same - Place reinforcements")
    print("R          - Reset all placements")
    print("Space      - End phase")
    print("\nACTION PHASE:")
    print("Click      - Select source then destination")
    print("Scroll     - Adjust troops")
    print("F          - Toggle flanking mode")
    print("Space      - End turn")
    print("\nNOTE: Each troop can only move once per turn!")
    print("Green number shows mobile troops remaining.")
    
    renderer.render(game)
    
    ai_move_delay = 800
    
    while running and not game.is_game_over:
        current_player = game.current_player.id
        
        if current_player == ai_player:
            renderer.render(game)
            renderer.delay(ai_move_delay)
            
            ai_agent.take_turn(game)
            
            renderer.clear_turn_state()
            save_reinforcement_snapshot()
            
            renderer.render(game)
            renderer.delay(ai_move_delay)
        
        else:
            events = renderer.handle_events()
            
            for event_type, event_data in events:
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
                    row, col = event_data
                    if row < 0 or row >= game.config.board_size or col < 0 or col >= game.config.board_size:
                        continue
                    
                    territory = game.board.get(row, col)
                    pos = (row, col)
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
            renderer.render(game)
            renderer.delay(5000)
            running = False
    
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
    
    args = parser.parse_args()
    
    if args.list:
        list_trained_genomes()
        return
    
    genome_path = args.genome
    if not Path(genome_path).exists():
        print(f"Error: Genome file '{genome_path}' not found")
        print("\nUse --list to see available trained genomes")
        return
    
    run_vs_ai(genome_path, args.player)


if __name__ == '__main__':
    main()
