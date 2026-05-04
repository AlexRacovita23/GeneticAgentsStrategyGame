from dataclasses import dataclass
from typing import List, Tuple, Optional
import random

from src.genetic.genome import Genome
from src.genetic.fitness import FitnessResult, FitnessEvaluator
from src.genetic.agent import GeneticAgent
from src.genetic.board_setup import create_chokepoint_game
from src.game.game_state import GameState


@dataclass
class Individual:
    genome: Genome
    fitness: Optional[FitnessResult] = None
    
    def __repr__(self) -> str:
        fit_str = f"{self.fitness.score:.1f}" if self.fitness else "N/A"
        return f"Individual(Gen={self.genome.generation}, Fitness={fit_str})"


class Population:
    
    def __init__(self,
                 population_size: int = 50,
                 games_per_eval: int = 5,
                 tournament_size: int = 3,
                 mutation_rate: float = 0.1,
                 crossover_rate: float = 0.7,
                 elitism: int = 2):
        self.population_size = population_size
        self.games_per_eval = games_per_eval
        self.tournament_size = tournament_size
        self.mutation_rate = mutation_rate
        self.crossover_rate = crossover_rate
        self.elitism = elitism
        
        self.population: List[Individual] = []
        self.generation = 0
        self.evaluator = FitnessEvaluator()
        self.best_individual: Optional[Individual] = None
    
    def initialize_random(self) -> None:
        self.population = [
            Individual(genome=Genome.random())
            for _ in range(self.population_size)
        ]
        self.generation = 0
    
    def evaluate_population(self, verbose: bool = True) -> None:
        if verbose:
            print(f"\nEvaluating Generation {self.generation}...")
        
        for i, individual in enumerate(self.population):
            if verbose and (i + 1) % 10 == 0:
                print(f"  Evaluated {i + 1}/{self.population_size} individuals")
            
            game_results = []
            
            opponents = random.sample(
                [ind for ind in self.population if ind != individual],
                min(self.games_per_eval, len(self.population) - 1)
            )
            
            for opponent in opponents:
                game_state = self._play_game(individual.genome, opponent.genome)
                game_results.append((game_state, 0))  # Individual is always player 0
            
            individual.fitness = self.evaluator.evaluate_games(game_results)
        
        # Sort by fitness
        self.population.sort(key=lambda ind: ind.fitness.score, reverse=True)
        
        # Update best individual
        if self.best_individual is None or \
           self.population[0].fitness.score > self.best_individual.fitness.score:
            self.best_individual = Individual(
                genome=self.population[0].genome.copy(),
                fitness=self.population[0].fitness
            )
        
        if verbose:
            print(f"\n  Best: {self.population[0].fitness}")
            print(f"  Worst: {self.population[-1].fitness}")
            print(f"  Average: {sum(ind.fitness.score for ind in self.population) / len(self.population):.2f}")
    
    def _play_game(self, genome1: Genome, genome2: Genome) -> GameState:
        game_state = create_chokepoint_game()
        
        agent1 = GeneticAgent(genome1, player_id=0)
        agent2 = GeneticAgent(genome2, player_id=1)
        
        max_iterations = 1000
        iteration = 0
        
        while not game_state.is_game_over and iteration < max_iterations:
            if game_state.current_player.id == 0:
                agent1.take_turn(game_state)
            else:
                agent2.take_turn(game_state)
            iteration += 1
        
        return game_state
    
    def evolve_generation(self) -> None:
        new_population: List[Individual] = []
        
        for i in range(min(self.elitism, len(self.population))):
            new_population.append(Individual(genome=self.population[i].genome.copy()))
        
        while len(new_population) < self.population_size:
            parent1 = self._tournament_selection()
            parent2 = self._tournament_selection()
            
            if random.random() < self.crossover_rate:
                child = parent1.genome.crossover(parent2.genome)
            else:
                child = parent1.genome.copy()
            
            if random.random() < self.mutation_rate:
                child.mutate()
            
            new_population.append(Individual(genome=child))
        
        self.population = new_population
        self.generation += 1
    
    def _tournament_selection(self) -> Individual:
        tournament = random.sample(self.population, self.tournament_size)
        return max(tournament, key=lambda ind: ind.fitness.score if ind.fitness else 0)
    
    def get_statistics(self) -> dict:
        if not self.population or not self.population[0].fitness:
            return {}
        
        scores = [ind.fitness.score for ind in self.population if ind.fitness]
        wins = [ind.fitness.wins for ind in self.population if ind.fitness]
        
        return {
            'generation': self.generation,
            'population_size': len(self.population),
            'best_score': max(scores) if scores else 0,
            'worst_score': min(scores) if scores else 0,
            'avg_score': sum(scores) / len(scores) if scores else 0,
            'total_wins': sum(wins) if wins else 0,
            'best_individual': self.best_individual,
        }
    
    def save_best(self, filepath: str) -> None:
        import json
        
        if self.best_individual is None:
            raise ValueError("No best individual to save")
        
        data = {
            'genome': self.best_individual.genome.to_dict(),
            'fitness': {
                'score': self.best_individual.fitness.score,
                'wins': self.best_individual.fitness.wins,
                'losses': self.best_individual.fitness.losses,
                'draws': self.best_individual.fitness.draws,
            } if self.best_individual.fitness else None,
            'generation': self.generation,
        }
        
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
    
    @staticmethod
    def load_genome(filepath: str) -> Genome:
        import json
        
        with open(filepath, 'r') as f:
            data = json.load(f)
        
        return Genome.from_dict(data['genome'])