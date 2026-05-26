import json
import random
import multiprocessing as mp
from dataclasses import dataclass
from typing import Callable, List, Optional, Tuple

from src.game.game_loop import GameLoop
from src.game.game_state import GameState
from src.genetic.agent import GeneticAgent
from src.genetic.board_setup import create_chokepoint_game, create_chokepoint_game_small
from src.genetic.fitness import FitnessEvaluator, FitnessResult
from src.genetic.genome import Genome

def _eval_worker(args: Tuple) -> Tuple[int, "FitnessResult"]:
    (
        idx,
        ind_genome_dict,
        opp_genome_dicts,
        evaluator_weights,
        game_factory_name,
    ) = args

    individual_genome = Genome.from_dict(ind_genome_dict)
    opponent_genomes  = [Genome.from_dict(d) for d in opp_genome_dicts]

    evaluator = FitnessEvaluator(**evaluator_weights)
    game_factory = _resolve_factory(game_factory_name)

    game_results = []
    for opp_genome in opponent_genomes:
        gs = _play_game(individual_genome, opp_genome, game_factory)
        game_results.append((gs, 0))

    fitness = evaluator.evaluate_games(game_results)
    return idx, fitness


def _play_game(genome1: Genome, genome2: Genome, game_factory: Callable) -> GameState:
    game_state = game_factory()
    agent1 = GeneticAgent(genome1, player_id=0)
    agent2 = GeneticAgent(genome2, player_id=1)
    loop = GameLoop(game_state)
    return loop.run_ai_vs_ai(agent1, agent2)


def _resolve_factory(name: str) -> Callable:
    if name == "chokepoint":
        return create_chokepoint_game
    if name == "chokepoint_small":
        return create_chokepoint_game_small
    raise ValueError(f"Unknown game factory: {name!r}")

@dataclass
class Individual:
    genome: Genome
    fitness: Optional[FitnessResult] = None

    def __repr__(self) -> str:
        fit_str = f"{self.fitness.score:.1f}" if self.fitness else "N/A"
        return f"Individual(Gen={self.genome.generation}, Fitness={fit_str})"


class Population:

    def __init__(
        self,
        population_size: int = 50,
        games_per_eval: int = 5,
        tournament_size: int = 3,
        mutation_rate: float = 0.1,
        crossover_rate: float = 0.7,
        elitism: int = 2,
        game_factory: Optional[Callable[[], GameState]] = None,
        game_factory_name: str = "chokepoint",
        evaluator: Optional[FitnessEvaluator] = None,
        num_workers: Optional[int] = None,
        use_premade_opponents: bool = False,
    ):
        self.population_size  = population_size
        self.games_per_eval   = games_per_eval
        self.tournament_size  = tournament_size
        self.mutation_rate    = mutation_rate
        self.crossover_rate   = crossover_rate
        self.elitism          = elitism
        self.use_premade_opponents = use_premade_opponents

        if use_premade_opponents:
            self.game_factory_name = "chokepoint_small"
            self.game_factory = create_chokepoint_game_small
            self.games_per_eval = 3
            self.premade_genome_dicts = self._load_premade_genomes()
        else:
            self.game_factory = game_factory or create_chokepoint_game
            self.game_factory_name = game_factory_name
            self.premade_genome_dicts = []

        self.evaluator        = evaluator or FitnessEvaluator()
        self.num_workers      = num_workers or min(mp.cpu_count(), population_size)

        self.population: List[Individual] = []
        self.generation = 0
        self.best_individual: Optional[Individual] = None

        self._evaluator_weights = {
            "win_weight":       self.evaluator.win_weight,
            "territory_weight": self.evaluator.territory_weight,
            "troop_weight":     self.evaluator.troop_weight,
            "turn_weight":      self.evaluator.turn_weight,
        }

    def _load_premade_genomes(self) -> List[dict]:
        from pathlib import Path
        premade_dir = Path("premade_genomes")
        genome_files = ["aggressive_rusher.json", "defensive_turtle.json", "neutral_hunter.json"]

        genomes = []
        for filename in genome_files:
            filepath = premade_dir / filename
            with open(filepath, "r") as f:
                data = json.load(f)
                genomes.append(data["genome"])

        return genomes

    def initialize_random(self) -> None:
        self.population = [
            Individual(genome=Genome.random()) for _ in range(self.population_size)
        ]
        self.generation = 0

    def evaluate_population(self, verbose: bool = True) -> None:
        work_items = self._build_work_items()

        if verbose:
            print(f"  Evaluating {len(work_items)} individuals "
                  f"across {self.num_workers} workers …")

        ctx = mp.get_context("spawn")
        with ctx.Pool(processes=self.num_workers) as pool:
            results = pool.map(_eval_worker, work_items)

        for idx, fitness in results:
            self.population[idx].fitness = fitness

        if verbose and (idx + 1) % 10 == 0:
            print(f"    … received result for individual {idx + 1}")

        self.population.sort(key=lambda ind: ind.fitness.score, reverse=True)

        if (
            self.best_individual is None
            or self.population[0].fitness.score > self.best_individual.fitness.score
        ):
            self.best_individual = Individual(
                genome=self.population[0].genome.copy(),
                fitness=self.population[0].fitness,
            )

        if verbose:
            scores = [ind.fitness.score for ind in self.population]
            print(f"\n  Best:    {self.population[0].fitness}")
            print(f"  Worst:   {self.population[-1].fitness}")
            print(f"  Average: {sum(scores) / len(scores):.2f}")

    def _build_work_items(self) -> List[Tuple]:
        items = []
        all_dicts = [ind.genome.to_dict() for ind in self.population]

        for i in range(len(self.population)):
            if self.use_premade_opponents:
                opp_dicts = self.premade_genome_dicts
            else:
                opponent_indices = random.sample(
                    [j for j in range(len(self.population)) if j != i],
                    min(self.games_per_eval, len(self.population) - 1),
                )
                opp_dicts = [all_dicts[j] for j in opponent_indices]

            items.append((
                i,
                all_dicts[i],
                opp_dicts,
                self._evaluator_weights,
                self.game_factory_name,
            ))

        return items

    def evolve_generation(self) -> None:
        new_population: List[Individual] = []

        for i in range(min(self.elitism, len(self.population))):
            new_population.append(Individual(genome=self.population[i].genome.copy()))

        while len(new_population) < self.population_size:
            parent1 = self._tournament_selection()
            parent2 = self._tournament_selection()

            child_genome = (
                parent1.genome.crossover(parent2.genome)
                if random.random() < self.crossover_rate
                else parent1.genome.copy()
            )

            if random.random() < self.mutation_rate:
                child_genome.mutate()

            new_population.append(Individual(genome=child_genome))

        self.population = new_population
        self.generation += 1

    def _tournament_selection(self) -> Individual:
        tournament = random.sample(self.population, self.tournament_size)
        return max(tournament, key=lambda ind: ind.fitness.score if ind.fitness else 0.0)

    def get_statistics(self) -> dict:
        if not self.population or not self.population[0].fitness:
            return {}

        scored = [ind for ind in self.population if ind.fitness]
        scores = [ind.fitness.score for ind in scored]
        wins   = [ind.fitness.wins  for ind in scored]

        return {
            "generation":      self.generation,
            "population_size": len(self.population),
            "best_score":      max(scores, default=0),
            "worst_score":     min(scores, default=0),
            "avg_score":       sum(scores) / len(scores) if scores else 0,
            "total_wins":      sum(wins),
            "best_individual": self.best_individual,
        }

    def save_best(self, filepath: str) -> None:
        if self.best_individual is None:
            raise ValueError("No best individual to save")

        data = {
            "genome": self.best_individual.genome.to_dict(),
            "fitness": (
                {
                    "score":  self.best_individual.fitness.score,
                    "wins":   self.best_individual.fitness.wins,
                    "losses": self.best_individual.fitness.losses,
                    "draws":  self.best_individual.fitness.draws,
                }
                if self.best_individual.fitness
                else None
            ),
            "generation": self.generation,
        }

        with open(filepath, "w") as f:
            json.dump(data, f, indent=2)

    @staticmethod
    def load_genome(filepath: str) -> Genome:
        with open(filepath, "r") as f:
            data = json.load(f)
        return Genome.from_dict(data["genome"])
