from dataclasses import dataclass


@dataclass
class Territory:
    owner: int = -1
    troops: int = 0
    
    @property
    def is_neutral(self) -> bool:
        return self.owner == -1
    
    @property
    def available_troops(self) -> int:
        return max(0, self.troops - 1)
    
    def can_move_from(self) -> bool:
        return self.owner != -1 and self.available_troops > 0
    
    def remove_troops(self, count: int) -> int:
        to_remove = min(count, self.available_troops)
        self.troops -= to_remove
        return to_remove
    
    def add_troops(self, count: int) -> None:
        self.troops += count
    
    def set_owner(self, new_owner: int, troops: int) -> None:
        self.owner = new_owner
        self.troops = troops
    
    def __repr__(self) -> str:
        owner_str = "N" if self.is_neutral else str(self.owner)
        return f"Territory({owner_str}:{self.troops})"
