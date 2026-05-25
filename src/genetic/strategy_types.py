from dataclasses import dataclass
from typing import List


@dataclass
class TerritoryScore:
    territory_id: int
    offensive_value: float
    defensive_value: float
    expansion_value: float
    threat_level: float


@dataclass
class ThreatAssessment:
    territory_id: int
    enemy_troops_adjacent: int
    friendly_neighbors: int
    is_border: bool
    threat_score: float