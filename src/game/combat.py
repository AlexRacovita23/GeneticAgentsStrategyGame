import math
from dataclasses import dataclass, field
from typing import Callable, List, Tuple, Optional

from src.game.territory import Territory
from src.game.board import MoveOutcome, MoveResult


@dataclass
class CombatConfig:
    defender_bonus: float = 1.2
    min_survivors: int = 1
    flanking_bonuses: Tuple[float, ...] = (1.0, 1.15, 1.30, 1.50)


@dataclass
class AttackSource:
    position: Tuple[int, int]
    troops: int


@dataclass 
class FlankingOutcome:
    result: MoveResult
    attacker_wins: bool
    total_attackers: int
    total_defenders: int
    flanking_directions: int
    flanking_bonus: float
    remaining_troops: int
    troops_lost_attacker: int
    troops_lost_defender: int
    losses_per_source: List[int] = field(default_factory=list)


def get_flanking_bonus(num_directions: int, config: CombatConfig = None) -> float:
    if config is None:
        config = CombatConfig()
    
    index = max(0, min(num_directions - 1, len(config.flanking_bonuses) - 1))
    return config.flanking_bonuses[index]


def resolve_combat_lanchester(
    source: Territory,
    dest: Territory,
    attackers: int,
    config: CombatConfig = None,
    flanking_directions: int = 1,
) -> MoveOutcome:
    if config is None:
        config = CombatConfig()
    
    defenders = dest.troops
    
    if attackers <= 0:
        return MoveOutcome(result=MoveResult.INVALID)
    
    if defenders <= 0:
        dest.set_owner(source.owner, attackers)
        dest.troops_moved_this_turn = attackers
        return MoveOutcome(
            result=MoveResult.CONQUERED,
            troops_moved=attackers,
            troops_lost_attacker=0,
            troops_lost_defender=0,
        )
    
    flanking_bonus = get_flanking_bonus(flanking_directions, config)
    
    atk_power = (attackers ** 2) * flanking_bonus
    def_power = (defenders ** 2) * config.defender_bonus
    
    if atk_power > def_power:
        power_diff = atk_power - def_power
        remaining = math.sqrt(power_diff / flanking_bonus)
        remaining = max(config.min_survivors, int(remaining))
        
        troops_lost_attacker = attackers - remaining
        
        dest.set_owner(source.owner, remaining)
        dest.troops_moved_this_turn = remaining
        
        return MoveOutcome(
            result=MoveResult.CONQUERED,
            troops_moved=attackers,
            troops_lost_attacker=troops_lost_attacker,
            troops_lost_defender=defenders,
        )
    else:
        power_diff = def_power - atk_power
        remaining = math.sqrt(power_diff / config.defender_bonus)
        remaining = max(config.min_survivors, int(remaining))
        
        troops_lost_defender = defenders - remaining
        
        dest.troops = remaining
        
        return MoveOutcome(
            result=MoveResult.REPELLED,
            troops_moved=attackers,
            troops_lost_attacker=attackers,
            troops_lost_defender=troops_lost_defender,
        )


def resolve_flanked_combat(
    attacks: List[AttackSource],
    dest: Territory,
    attacker_owner: int,
    config: CombatConfig = None,
) -> FlankingOutcome:
    if config is None:
        config = CombatConfig()
    
    if not attacks:
        return FlankingOutcome(
            result=MoveResult.INVALID,
            attacker_wins=False,
            total_attackers=0,
            total_defenders=dest.troops,
            flanking_directions=0,
            flanking_bonus=1.0,
            remaining_troops=dest.troops,
            troops_lost_attacker=0,
            troops_lost_defender=0,
        )
    
    total_attackers = sum(a.troops for a in attacks)
    num_directions = len(attacks)
    defenders = dest.troops
    
    if total_attackers <= 0:
        return FlankingOutcome(
            result=MoveResult.INVALID,
            attacker_wins=False,
            total_attackers=0,
            total_defenders=defenders,
            flanking_directions=num_directions,
            flanking_bonus=1.0,
            remaining_troops=defenders,
            troops_lost_attacker=0,
            troops_lost_defender=0,
        )
    
    if defenders <= 0:
        dest.set_owner(attacker_owner, total_attackers)
        dest.troops_moved_this_turn = total_attackers
        return FlankingOutcome(
            result=MoveResult.CONQUERED,
            attacker_wins=True,
            total_attackers=total_attackers,
            total_defenders=0,
            flanking_directions=num_directions,
            flanking_bonus=get_flanking_bonus(num_directions, config),
            remaining_troops=total_attackers,
            troops_lost_attacker=0,
            troops_lost_defender=0,
            losses_per_source=[0] * num_directions,
        )
    
    flanking_bonus = get_flanking_bonus(num_directions, config)
    
    atk_power = (total_attackers ** 2) * flanking_bonus
    def_power = (defenders ** 2) * config.defender_bonus
    
    if atk_power > def_power:
        power_diff = atk_power - def_power
        remaining = math.sqrt(power_diff / flanking_bonus)
        remaining = max(config.min_survivors, int(remaining))
        
        troops_lost = total_attackers - remaining
        
        losses_per_source = _distribute_losses(attacks, troops_lost)
        
        dest.set_owner(attacker_owner, remaining)
        dest.troops_moved_this_turn = remaining
        
        return FlankingOutcome(
            result=MoveResult.CONQUERED,
            attacker_wins=True,
            total_attackers=total_attackers,
            total_defenders=defenders,
            flanking_directions=num_directions,
            flanking_bonus=flanking_bonus,
            remaining_troops=remaining,
            troops_lost_attacker=troops_lost,
            troops_lost_defender=defenders,
            losses_per_source=losses_per_source,
        )
    else:
        power_diff = def_power - atk_power
        remaining = math.sqrt(power_diff / config.defender_bonus)
        remaining = max(config.min_survivors, int(remaining))
        
        troops_lost_defender = defenders - remaining
        
        losses_per_source = [a.troops for a in attacks]
        
        dest.troops = remaining
        
        return FlankingOutcome(
            result=MoveResult.REPELLED,
            attacker_wins=False,
            total_attackers=total_attackers,
            total_defenders=defenders,
            flanking_directions=num_directions,
            flanking_bonus=flanking_bonus,
            remaining_troops=remaining,
            troops_lost_attacker=total_attackers,
            troops_lost_defender=troops_lost_defender,
            losses_per_source=losses_per_source,
        )


def _distribute_losses(attacks: List[AttackSource], total_losses: int) -> List[int]:
    total_troops = sum(a.troops for a in attacks)
    if total_troops == 0:
        return [0] * len(attacks)
    
    losses = []
    remaining_losses = total_losses
    
    for i, attack in enumerate(attacks):
        if i == len(attacks) - 1:
            losses.append(remaining_losses)
        else:
            proportion = attack.troops / total_troops
            this_loss = min(int(total_losses * proportion), attack.troops)
            this_loss = min(this_loss, remaining_losses)
            losses.append(this_loss)
            remaining_losses -= this_loss
    
    return losses


def create_combat_resolver(config: CombatConfig = None) -> Callable:
    if config is None:
        config = CombatConfig()
    
    def resolver(source: Territory, dest: Territory, attackers: int) -> MoveOutcome:
        return resolve_combat_lanchester(source, dest, attackers, config)
    
    return resolver


default_combat_resolver = create_combat_resolver()
aggressive_combat_resolver = create_combat_resolver(CombatConfig(defender_bonus=1.0))
defensive_combat_resolver = create_combat_resolver(CombatConfig(defender_bonus=1.5))


def calculate_win_probability(
    attackers: int, 
    defenders: int, 
    defender_bonus: float = 1.2,
    flanking_directions: int = 1,
) -> float:
    if defenders <= 0:
        return 1.0
    if attackers <= 0:
        return 0.0
    
    config = CombatConfig(defender_bonus=defender_bonus)
    flanking_bonus = get_flanking_bonus(flanking_directions, config)
    
    atk_power = (attackers ** 2) * flanking_bonus
    def_power = (defenders ** 2) * defender_bonus
    
    return 1.0 if atk_power > def_power else 0.0


def calculate_remaining_troops(
    attackers: int, 
    defenders: int, 
    defender_bonus: float = 1.2,
    flanking_directions: int = 1,
) -> Tuple[bool, int]:
    if defenders <= 0:
        return True, attackers
    if attackers <= 0:
        return False, defenders
    
    config = CombatConfig(defender_bonus=defender_bonus)
    flanking_bonus = get_flanking_bonus(flanking_directions, config)
    
    atk_power = (attackers ** 2) * flanking_bonus
    def_power = (defenders ** 2) * defender_bonus
    
    if atk_power > def_power:
        remaining = max(1, int(math.sqrt((atk_power - def_power) / flanking_bonus)))
        return True, remaining
    else:
        remaining = max(1, int(math.sqrt((def_power - atk_power) / defender_bonus)))
        return False, remaining


def minimum_troops_to_win(
    defenders: int, 
    defender_bonus: float = 1.2,
    flanking_directions: int = 1,
) -> int:
    if defenders <= 0:
        return 1
    
    config = CombatConfig(defender_bonus=defender_bonus)
    flanking_bonus = get_flanking_bonus(flanking_directions, config)
    
    effective_ratio = defender_bonus / flanking_bonus
    min_attackers = defenders * math.sqrt(effective_ratio)
    return int(math.ceil(min_attackers)) + 1


def print_combat_table(max_troops: int = 20, defender_bonus: float = 1.2) -> None:
    print(f"\nLanchester Combat Table (defender bonus: {defender_bonus}x)")
    print("=" * 70)
    
    print("\n1. SINGLE DIRECTION ATTACK (no flanking bonus)")
    print("-" * 70)
    print(f"{'Attackers':>10} vs {'Defenders':>10} -> {'Winner':>10} {'Remaining':>10}")
    print("-" * 70)
    
    test_cases = [(10, 10), (12, 10), (15, 10), (20, 15)]
    for atk, def_ in test_cases:
        wins, remaining = calculate_remaining_troops(atk, def_, defender_bonus, flanking_directions=1)
        winner = "Attacker" if wins else "Defender"
        print(f"{atk:>10} vs {def_:>10} -> {winner:>10} {remaining:>10}")
    
    print("\n2. FLANKING COMPARISON (15 attackers vs 12 defenders)")
    print("-" * 70)
    print(f"{'Directions':>10} {'Bonus':>10} -> {'Winner':>10} {'Remaining':>10}")
    print("-" * 70)
    
    config = CombatConfig(defender_bonus=defender_bonus)
    for dirs in [1, 2, 3, 4]:
        bonus = get_flanking_bonus(dirs, config)
        wins, remaining = calculate_remaining_troops(15, 12, defender_bonus, flanking_directions=dirs)
        winner = "Attacker" if wins else "Defender"
        print(f"{dirs:>10} {bonus:>10.2f}x -> {winner:>10} {remaining:>10}")
    
    print("\n3. MINIMUM TROOPS TO WIN vs 10 DEFENDERS")
    print("-" * 70)
    for dirs in [1, 2, 3, 4]:
        min_troops = minimum_troops_to_win(10, defender_bonus, flanking_directions=dirs)
        bonus = get_flanking_bonus(dirs, config)
        print(f"   {dirs} direction(s) ({bonus:.2f}x bonus): need {min_troops} attackers")
    
    print()
