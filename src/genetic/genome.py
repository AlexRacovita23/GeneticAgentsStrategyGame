from __future__ import annotations

import random
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict


class TraitGroupType(Enum):
    COMBAT_AGGRESSION = "combat_aggression"
    EXPANSION_STRATEGY = "expansion_strategy"
    ARMY_DISTRIBUTION = "army_distribution"


@dataclass
class TraitGroup:
    group_type: TraitGroupType
    traits: Dict[str, float] = field(default_factory=dict)

    def mutate(self, mutation_rate: float, mutation_strength: float = 0.1) -> None:
        if random.random() < mutation_rate:
            direction = random.choice([-1, 1])
            adjustment = direction * random.uniform(0, mutation_strength)
            for trait_name in self.traits:
                self.traits[trait_name] = max(
                    0.0, min(1.0, self.traits[trait_name] + adjustment)
                )

    def mutate_individual(
        self, mutation_rate: float, mutation_strength: float = 0.05
    ) -> None:
        for trait_name in self.traits:
            if random.random() < mutation_rate:
                adjustment = random.uniform(-mutation_strength, mutation_strength)
                self.traits[trait_name] = max(
                    0.0, min(1.0, self.traits[trait_name] + adjustment)
                )

    def copy(self) -> TraitGroup:
        return TraitGroup(group_type=self.group_type, traits=self.traits.copy())


@dataclass
class Genome:
    trait_groups: Dict[TraitGroupType, TraitGroup] = field(default_factory=dict)
    generation: int = 0

    def __post_init__(self) -> None:
        self._all_traits: Dict[str, float] = {}
        self._rebuild_trait_cache()

    @staticmethod
    def random() -> Genome:
        genome = Genome()

        genome.trait_groups[TraitGroupType.COMBAT_AGGRESSION] = TraitGroup(
            group_type=TraitGroupType.COMBAT_AGGRESSION,
            traits={
                "attack_threshold": random.uniform(0.1, 0.5),
                "risk_tolerance": random.uniform(0.3, 0.7),
                "defensive_posture": random.uniform(0.3, 0.7),
            },
        )
        genome.trait_groups[TraitGroupType.EXPANSION_STRATEGY] = TraitGroup(
            group_type=TraitGroupType.EXPANSION_STRATEGY,
            traits={
                "expansion_speed": random.uniform(0.3, 0.7),
                "neutral_priority": random.uniform(0.3, 0.7),
                "border_focus": random.uniform(0.3, 0.7),
            },
        )
        genome.trait_groups[TraitGroupType.ARMY_DISTRIBUTION] = TraitGroup(
            group_type=TraitGroupType.ARMY_DISTRIBUTION,
            traits={
                "concentration": random.uniform(0.3, 0.7),
                "flanking_preference": random.uniform(0.3, 0.7),
                "reinforcement_spread": random.uniform(0.3, 0.7),
                "retreat_threshold": random.uniform(0.3, 0.7),
            },
        )

        genome._rebuild_trait_cache()
        return genome

    @staticmethod
    def from_dict(data: Dict) -> Genome:
        genome = Genome()
        genome.generation = data.get("generation", 0)

        for group_type_str, group_data in data["trait_groups"].items():
            group_type = TraitGroupType(group_type_str)
            loaded_traits = group_data["traits"].copy()

            default_traits = Genome._get_default_traits_for_group(group_type)
            for trait_name, default_value in default_traits.items():
                if trait_name not in loaded_traits:
                    loaded_traits[trait_name] = default_value

            genome.trait_groups[group_type] = TraitGroup(
                group_type=group_type,
                traits=loaded_traits,
            )

        genome._rebuild_trait_cache()
        return genome

    @staticmethod
    def _get_default_traits_for_group(group_type: TraitGroupType) -> Dict[str, float]:
        if group_type == TraitGroupType.COMBAT_AGGRESSION:
            return {
                "attack_threshold": 0.3,
                "risk_tolerance": 0.5,
                "defensive_posture": 0.5,
            }
        elif group_type == TraitGroupType.EXPANSION_STRATEGY:
            return {
                "expansion_speed": 0.3,
                "neutral_priority": 0.5,
                "border_focus": 0.5,
            }
        elif group_type == TraitGroupType.ARMY_DISTRIBUTION:
            return {
                "concentration": 0.5,
                "flanking_preference": 0.3,
                "reinforcement_spread": 0.5,
                "retreat_threshold": 0.5,
            }
        return {}

    def _rebuild_trait_cache(self) -> None:
        self._all_traits = {}
        for group in self.trait_groups.values():
            self._all_traits.update(group.traits)

    def get_trait(self, trait_name: str) -> float:
        if trait_name in self._all_traits:
            return self._all_traits[trait_name]
        raise KeyError(f"Trait '{trait_name}' not found in genome")

    def mutate(
        self,
        group_mutation_rate: float = 0.1,
        individual_mutation_rate: float = 0.05,
        mutation_strength: float = 0.1,
    ) -> None:
        for group in self.trait_groups.values():
            group.mutate(group_mutation_rate, mutation_strength)
            group.mutate_individual(individual_mutation_rate, mutation_strength / 2)

        self.generation += 1
        self._rebuild_trait_cache()

    def crossover(self, other: Genome) -> Genome:
        child = Genome()
        child.generation = max(self.generation, other.generation) + 1

        for group_type in TraitGroupType:
            parent1_group = self.trait_groups[group_type]
            parent2_group = other.trait_groups[group_type]

            child_traits = {}

            for trait_name in parent1_group.traits:
                parent1_value = parent1_group.traits[trait_name]
                parent2_value = parent2_group.traits.get(trait_name, parent1_value)

                alpha = random.betavariate(2, 2)

                if random.random() < 0.2:
                    alpha = random.choice([0.0, 1.0])

                child_value = alpha * parent1_value + (1 - alpha) * parent2_value
                child_traits[trait_name] = child_value

            child.trait_groups[group_type] = TraitGroup(
                group_type=group_type,
                traits=child_traits
            )

        child._rebuild_trait_cache()
        return child

    def copy(self) -> Genome:
        new_genome = Genome()
        new_genome.generation = self.generation
        for group_type, group in self.trait_groups.items():
            new_genome.trait_groups[group_type] = group.copy()
        new_genome._rebuild_trait_cache()
        return new_genome

    def to_dict(self) -> Dict:
        return {
            "generation": self.generation,
            "trait_groups": {
                group_type.value: {"traits": group.traits}
                for group_type, group in self.trait_groups.items()
            },
        }

    def __repr__(self) -> str:
        lines = [f"Genome (Gen {self.generation}):"]
        for group_type, group in self.trait_groups.items():
            lines.append(f"  {group_type.value}:")
            for trait_name, value in group.traits.items():
                lines.append(f"    {trait_name}: {value:.3f}")
        return "\n".join(lines)
