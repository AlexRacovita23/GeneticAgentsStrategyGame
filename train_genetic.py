#!/usr/bin/env python3
import argparse
import time
from pathlib import Path

from src.genetic.population import Population
from src.genetic.board_setup import visualize_chokepoint_board


def train(generations: int = 100,
          population_size: int = 50,
          games_per_eval: int = 5,
          save_every: int = 10,
          output_dir: str = "trained_genomes",
          seed: int = None):
    if seed is not None:
        import random
        random.seed(seed)
    
    output_path = Path(output_dir)
    output_path.mkdir(exist_ok=True)
    
    print("=" * 80)
    print("GENETIC ALGORITHM TRAINING")
    print("=" * 80)
    print(f"\nConfiguration:")
    print(f"  Generations: {generations}")
    print(f"  Population Size: {population_size}")
    print(f"  Games per Evaluation: {games_per_eval}")
    print(f"  Save Every: {save_every} generations")
    print(f"  Output Directory: {output_dir}")
    if seed:
        print(f"  Random Seed: {seed}")
    
    print("\n" + visualize_chokepoint_board())
    
    # Initialize population
    print("\nInitializing population...")
    population = Population(
        population_size=population_size,
        games_per_eval=games_per_eval,
        tournament_size=3,
        mutation_rate=0.1,
        crossover_rate=0.7,
        elitism=2
    )
    population.initialize_random()
    
    # Training loop
    start_time = time.time()
    
    for gen in range(generations):
        gen_start = time.time()
        
        print(f"\n{'=' * 80}")
        print(f"GENERATION {gen + 1}/{generations}")
        print(f"{'=' * 80}")
        
        # Evaluate population
        population.evaluate_population(verbose=True)
        
        # Get statistics
        stats = population.get_statistics()
        
        # Print statistics
        print(f"\nStatistics:")
        print(f"  Best Score: {stats['best_score']:.2f}")
        print(f"  Average Score: {stats['avg_score']:.2f}")
        print(f"  Worst Score: {stats['worst_score']:.2f}")
        print(f"  Total Wins: {stats['total_wins']}")
        
        if population.best_individual:
            print(f"\nBest Individual:")
            print(population.best_individual.genome)
        
        # Save best genome periodically
        if (gen + 1) % save_every == 0:
            save_path = output_path / f"best_gen_{gen + 1}.json"
            population.save_best(str(save_path))
            print(f"\nSaved best genome to: {save_path}")
        
        # Evolve to next generation (except last)
        if gen < generations - 1:
            population.evolve_generation()
        
        gen_time = time.time() - gen_start
        print(f"\nGeneration time: {gen_time:.2f}s")
    
    # Final save
    final_path = output_path / "best_final.json"
    population.save_best(str(final_path))
    
    total_time = time.time() - start_time
    
    print("\n" + "=" * 80)
    print("TRAINING COMPLETE")
    print("=" * 80)
    print(f"\nTotal training time: {total_time:.2f}s ({total_time/60:.2f} minutes)")
    print(f"Final best score: {population.best_individual.fitness.score:.2f}")
    print(f"Final best genome saved to: {final_path}")
    print(f"\nBest genome traits:")
    print(population.best_individual.genome)


def main():
    parser = argparse.ArgumentParser(
        description="Train genetic agents for strategy game",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    
    parser.add_argument(
        '--generations', '-g',
        type=int,
        default=100,
        help='Number of generations to evolve'
    )
    
    parser.add_argument(
        '--population', '-p',
        type=int,
        default=50,
        help='Population size'
    )
    
    parser.add_argument(
        '--games', '-n',
        type=int,
        default=5,
        help='Games per fitness evaluation'
    )
    
    parser.add_argument(
        '--save-every', '-s',
        type=int,
        default=10,
        help='Save best genome every N generations'
    )
    
    parser.add_argument(
        '--output', '-o',
        type=str,
        default='trained_genomes',
        help='Output directory for saved genomes'
    )
    
    parser.add_argument(
        '--seed',
        type=int,
        default=None,
        help='Random seed for reproducibility'
    )
    
    args = parser.parse_args()
    
    train(
        generations=args.generations,
        population_size=args.population,
        games_per_eval=args.games,
        save_every=args.save_every,
        output_dir=args.output,
        seed=args.seed
    )


if __name__ == '__main__':
    main()