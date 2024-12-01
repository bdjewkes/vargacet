from typing import Dict, List, Optional, Set, Tuple, Literal
from pydantic import BaseModel
from enum import Enum
import random
import logging

logger = logging.getLogger(__name__)

class GameStatus(Enum):
    LOBBY = "lobby"
    IN_PROGRESS = "in_progress"
    FINISHED = "finished"

class Position(BaseModel):
    x: int
    y: int

class EffectType(str, Enum):
    HEAL = "heal"
    DAMAGE = "damage"

class Effect(BaseModel):
    type: EffectType
    amount: int

class Ability(BaseModel):
    id: str
    name: str
    range: int
    effect: Effect

# Define standard abilities
PUNCH_ABILITY = Ability(
    id="punch",
    name="Punch",
    range=1,
    effect=Effect(type=EffectType.DAMAGE, amount=1)
)

BANDAGE_ABILITY = Ability(
    id="bandage",
    name="Bandage",
    range=1,
    effect=Effect(type=EffectType.HEAL, amount=2)
)

class Hero(BaseModel):
    id: str
    position: Position
    start_position: Optional[Position] = None  # Track starting position for undo
    owner_id: str
    current_hp: int = 10
    max_hp: int = 10
    damage: int = 5
    movement_points: int = 5
    armor: int = 3
    remaining_movement: int = 5  # Track remaining movement for the turn
    abilities: List[Ability] = [PUNCH_ABILITY]  # Default ability

    def reset_movement(self):
        """Reset movement points at the start of turn"""
        self.remaining_movement = self.movement_points
        self.start_position = Position(x=self.position.x, y=self.position.y)  # Store starting position

    def can_move_to(self, new_position: Position) -> bool:
        """Check if hero can move to new position based on remaining points"""
        distance = abs(new_position.x - self.position.x) + abs(new_position.y - self.position.y)
        return distance <= self.remaining_movement

    def move_to(self, new_position: Position) -> bool:
        """Move hero to new position and update remaining movement points"""
        if not self.can_move_to(new_position):
            return False
            
        if not self.start_position:  # Store starting position on first move of the turn
            self.start_position = Position(x=self.position.x, y=self.position.y)
            
        distance = abs(new_position.x - self.position.x) + abs(new_position.y - self.position.y)
        self.remaining_movement -= distance
        self.position = new_position
        return True

    def undo_move(self) -> bool:
        """Undo movement and restore movement points"""
        if not self.start_position:
            return False
        
        self.position = Position(x=self.start_position.x, y=self.start_position.y)
        self.remaining_movement = self.movement_points
        return True

    def use_ability(self, ability_id: str, target: 'Hero') -> bool:
        """Use an ability on a target hero"""
        # Find the ability
        ability = next((a for a in self.abilities if a.id == ability_id), None)
        if not ability:
            return False

        # Check range
        distance = abs(self.position.x - target.position.x) + abs(self.position.y - target.position.y)
        if distance > ability.range:
            return False

        # Apply effect
        if ability.effect.type == EffectType.DAMAGE:
            target.current_hp = max(0, target.current_hp - ability.effect.amount)
        elif ability.effect.type == EffectType.HEAL:
            target.current_hp = min(target.max_hp, target.current_hp + ability.effect.amount)

        return True

class PlayerState(BaseModel):
    player_id: str
    name: Optional[str] = None
    connected: bool = False
    heroes: List[Hero] = []

class GameState(BaseModel):
    game_id: str
    players: Dict[str, PlayerState] = {}  # player_id -> PlayerState
    current_turn: Optional[str] = None  # player_id of current turn
    max_players: int = 2
    status: GameStatus = GameStatus.LOBBY
    grid_size: int = 20
    heroes_per_player: int = 4
    obstacles: Set[str] = set()  # Store obstacles as "x,y" strings
    moved_hero_id: Optional[str] = None  # Track which hero has moved this turn

    def add_player(self, player_id: str) -> bool:
        """Add a player to the game if there's room. Returns True if successful."""
        if len(self.players) >= self.max_players:
            return False
        if player_id not in self.players:
            self.players[player_id] = PlayerState(player_id=player_id)
            # Set first player's turn if this is the first player
            if self.current_turn is None:
                self.current_turn = player_id
        return True

    def initialize_heroes(self) -> bool:
        """Initialize heroes for all players when game starts."""
        try:
            # First, generate obstacles (avoiding the hero spawn areas)
            self.generate_obstacles()
            
            # Then initialize heroes
            player_list = list(self.players.keys())
            
            for i, player_id in enumerate(player_list):
                player = self.players[player_id]
                player.heroes = []
                is_top_player = i == 0
                
                # Try to place heroes for each player
                heroes_placed = 0
                max_attempts = 100  # Prevent infinite loops
                attempts = 0
                
                while heroes_placed < self.heroes_per_player and attempts < max_attempts:
                    # Top player heroes start in top 4 rows, bottom player in bottom 4 rows
                    if is_top_player:
                        y = random.randint(0, 3)
                    else:
                        y = random.randint(self.grid_size - 4, self.grid_size - 1)
                    
                    x = random.randint(0, self.grid_size - 1)
                    pos_key = f"{x},{y}"
                    
                    # Check if position is free (no obstacles or other heroes)
                    if pos_key not in self.obstacles and not self.is_position_occupied(x, y):
                        hero = Hero(
                            id=f"{player_id}_hero_{heroes_placed}",
                            position=Position(x=x, y=y),
                            owner_id=player_id
                        )
                        player.heroes.append(hero)
                        heroes_placed += 1
                    
                    attempts += 1
                
                if heroes_placed < self.heroes_per_player:
                    logger.error(f"Could not place all heroes for player {player_id} - too many obstacles or collisions")
                    return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error initializing heroes: {e}")
            return False

    def generate_obstacles(self) -> None:
        """Generate random obstacles, avoiding spawn areas."""
        # Clear existing obstacles
        self.obstacles.clear()
        
        # Calculate spawn areas to avoid
        spawn_area = set()
        for y in range(4):  # Top spawn area
            for x in range(self.grid_size):
                spawn_area.add(f"{x},{y}")
        for y in range(self.grid_size - 4, self.grid_size):  # Bottom spawn area
            for x in range(self.grid_size):
                spawn_area.add(f"{x},{y}")
        
        # Generate random obstacles (about 15% of non-spawn area)
        available_cells = self.grid_size * (self.grid_size - 8)  # Total cells minus spawn areas
        num_obstacles = int(available_cells * 0.15)
        
        logger.info(f"Generating {num_obstacles} obstacles")
        
        obstacles_placed = 0
        max_attempts = num_obstacles * 3  # Prevent infinite loops
        attempts = 0
        
        while obstacles_placed < num_obstacles and attempts < max_attempts:
            x = random.randint(0, self.grid_size - 1)
            y = random.randint(4, self.grid_size - 5)  # Avoid spawn areas
            pos_key = f"{x},{y}"
            
            if pos_key not in spawn_area and pos_key not in self.obstacles:
                self.obstacles.add(pos_key)
                obstacles_placed += 1
            
            attempts += 1
        
        logger.info(f"Generated {len(self.obstacles)} obstacles: {sorted(self.obstacles)}")

    def is_position_occupied(self, x: int, y: int) -> bool:
        """Check if any hero is at this position."""
        for player in self.players.values():
            for hero in player.heroes:
                if hero.position.x == x and hero.position.y == y:
                    return True
        return False

    def remove_player(self, player_id: str) -> None:
        """Remove a player from the game."""
        if player_id in self.players:
            del self.players[player_id]
            # Update current turn if needed
            if self.current_turn == player_id:
                remaining_players = list(self.players.keys())
                self.current_turn = remaining_players[0] if remaining_players else None

    def update_player_name(self, player_id: str, name: str) -> bool:
        """Update a player's name. Returns True if successful."""
        if player_id in self.players:
            self.players[player_id].name = name
            return True
        return False

    def update_player_connection(self, player_id: str, connected: bool) -> None:
        """Update a player's connection status."""
        if player_id in self.players:
            self.players[player_id].connected = connected

    def set_player_connected(self, player_id: str, connected: bool = True) -> bool:
        """Alias for update_player_connection for backward compatibility."""
        self.update_player_connection(player_id, connected)
        return True

    def is_full(self) -> bool:
        """Check if the game is full."""
        return len(self.players) >= self.max_players

    def get_game_status(self) -> dict:
        """Get the current game status."""
        status_dict = {
            "game_id": self.game_id,
            "players": {
                player_id: {
                    "player_id": player.player_id,
                    "name": player.name,
                    "connected": player.connected,
                    "heroes": [hero.dict() for hero in player.heroes]
                }
                for player_id, player in self.players.items()
            },
            "current_turn": self.current_turn,
            "is_full": self.is_full(),
            "status": self.status.value,  # Convert enum to string
            "grid_size": self.grid_size,
            "obstacles": list(self.obstacles)  # Convert set to list for JSON
        }
        logger.info(f"Game status - current_turn: {self.current_turn}, players: {list(self.players.keys())}")
        return status_dict

    def set_next_turn(self) -> None:
        """Set the turn to the next player."""
        player_ids = list(self.players.keys())
        if not player_ids:
            self.current_turn = None
            return

        if self.current_turn is None:
            self.current_turn = player_ids[0]
        else:
            current_index = player_ids.index(self.current_turn)
            next_index = (current_index + 1) % len(player_ids)
            self.current_turn = player_ids[next_index]
            
        # Reset moved hero when turn changes
        self.moved_hero_id = None
        
        # Reset movement points for all heroes of the new current player
        if self.current_turn:
            current_player = self.players[self.current_turn]
            for hero in current_player.heroes:
                hero.reset_movement()
