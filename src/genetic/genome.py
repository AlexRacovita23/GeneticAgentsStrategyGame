from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List
import random


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
                new_value = self.traits[trait_name] + adjustment
                self.traits[trait_name] = max(0.0, min(1.0, new_value))
    
    def mutate_individual(self, mutation_rate: float, mutation_strength: float = 0.05) -> None:
        for trait_name in self.traits:
            if random.random() < mutation_rate:
                adjustment = random.uniform(-mutation_strength, mutation_strength)
                new_value = self.traits[trait_name] + adjustment
                self.traits[trait_name] = max(0.0, min(1.0, new_value))
    
    def copy(self) -> 'TraitGroup':
        return TraitGroup(
            group_type=self.group_type,
            traits=self.traits.copy()
        )


@dataclass
class Genome:
    trait_groups: Dict[TraitGroupType, TraitGroup] = field(default_factory=dict)
    generation: int = 0
    
    @staticmethod
    def random() -> 'Genome':
        genome = Genome()
        
        genome.trait_groups[TraitGroupType.COMBAT_AGGRESSION] = TraitGroup(
            group_type=TraitGroupType.COMBAT_AGGRESSION,
            traits={
                'attack_threshold': random.uniform(0.3, 0.7),
                'risk_tolerance': random.uniform(0.3, 0.7),
                'defensive_posture': random.uniform(0.3, 0.7),
            }
        )
        
        genome.trait_groups[TraitGroupType.EXPANSION_STRATEGY] = TraitGroup(
            group_type=TraitGroupType.EXPANSION_STRATEGY,
            traits={
                'expansion_speed': random.uniform(0.3, 0.7),
                'neutral_priority': random.uniform(0.3, 0.7),
                'border_focus': random.uniform(0.3, 0.7),
            }
        )
        
        genome.trait_groups[TraitGroupType.ARMY_DISTRIBUTION] = TraitGroup(
            group_type=TraitGroupType.ARMY_DISTRIBUTION,
            traits={
                'concentration': random.uniform(0.3, 0.7),
                'flanking_preference': random.uniform(0.3, 0.7),
                'reinforcement_spread': random.uniform(0.3, 0.7),
                'retreat_threshold': random.uniform(0.3, 0.7),
            }
        )
        
        return genome
    
    def get_trait(self, trait_name: str) -> float:
        for group in self.trait_groups.values():
            if trait_name in group.traits:
                return group.traits[trait_name]
        raise KeyError(f"Trait '{trait_name}' not found in genome")
    
    def mutate(self, group_mutation_rate: float = 0.1, 
               individual_mutation_rate: float = 0.05,
               mutation_strength: float = 0.1) -> None:
        for group in self.trait_groups.values():
            group.mutate(group_mutation_rate, mutation_strength)
            group.mutate_individual(individual_mutation_rate, mutation_strength / 2)
        
        self.generation += 1
    
    def crossover(self, other: 'Genome') -> 'Genome':
        child = Genome()
        child.generation = max(self.generation, other.generation) + 1
        
        for group_type in TraitGroupType:
            if random.random() < 0.5:
                child.trait_groups[group_type] = self.trait_groups[group_type].copy()
            else:
                child.trait_groups[group_type] = other.trait_groups[group_type].copy()
        
        return child
    
    def copy(self) -> 'Genome':
        new_genome = Genome()
        new_genome.generation = self.generation
        for group_type, group in self.trait_groups.items():
            new_genome.trait_groups[group_type] = group.copy()
        return new_genome
    
    def to_dict(self) -> Dict:
        return {
            'generation': self.generation,
            'trait_groups': {
                group_type.value: {
                    'traits': group.traits
                }
                for group_type, group in self.trait_groups.items()
            }
        }
    
    @staticmethod
    def from_dict(data: Dict) -> 'Genome':
        genome = Genome()
        genome.generation = data.get('generation', 0)
        
        for group_type_str, group_data in data['trait_groups'].items():
            group_type = TraitGroupType(group_type_str)
            genome.trait_groups[group_type] = TraitGroup(
                group_type=group_type,
                traits=group_data['traits'].copy()
            )
        
        return genome
    
    def __repr__(self) -> str:
        lines = [f"Genome (Gen {self.generation}):"]
        for group_type, group in self.trait_groups.items():
            lines.append(f"  {group_type.value}:")
            for trait_name, value in group.traits.items():
                lines.append(f"    {trait_name}: {value:.3f}")
        return "\n".join(lines)