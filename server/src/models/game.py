from typing import Dict, List, Optional, Set, Tuple, Literal
from pydantic import BaseModel
from enum import Enum
import random
import logging
from collections import deque

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
    start_position: Optional[Position] = None
    owner_id: str
    current_hp: int = 10
    max_hp: int = 10
    damage: int = 5
    max_movement: int = 5
    movement_points: int = 5
    armor: int = 3
    abilities: List[Ability] = [PUNCH_ABILITY]

    def reset_movement(self):
        """Reset movement points at the start of turn"""
        self.movement_points = self.max_movement
        self.start_position = Position(x=self.position.x, y=self.position.y)

    def can_move_to(self, new_position: Position, game_state: 'GameState') -> bool:
        """Check if hero can move to new position based on remaining points and valid path"""
        if (new_position.x < 0 or new_position.x >= game_state.grid_size or
            new_position.y < 0 or new_position.y >= game_state.grid_size):
            return False

        target_pos_str = f"{new_position.x},{new_position.y}"
        if target_pos_str in game_state.obstacles:
            return False

        dx = abs(new_position.x - self.position.x)
        dy = abs(new_position.y - self.position.y)
        if dx > 0 and dy > 0:
            return False

        path = game_state.find_path(self.position, new_position, self.movement_points)
        if not path:
            return False

        path_length = len(path) - 1
        if path_length > self.movement_points:
            return False

        return True

    def move_to(self, new_position: Position, game_state: 'GameState') -> bool:
        """Move hero to new position and update movement points"""
        if not self.can_move_to(new_position, game_state):
            return False

        path = game_state.find_path(self.position, new_position, self.movement_points)
        if not path:
            return False

        movement_cost = len(path) - 1

        # Store start position if this is the first move
        if not self.start_position:
            self.start_position = Position(x=self.position.x, y=self.position.y)
        
        self.position = new_position
        self.movement_points -= movement_cost
        
        game_state.moved_hero_id = self.id
        
        return True

    def undo_move(self):
        """Undo movement and restore movement points"""
        if self.start_position:
            self.movement_points = self.max_movement
            self.position = self.start_position
            self.start_position = None

    def use_ability(self, ability_id: str, target: 'Hero', game_state: 'GameState') -> bool:
        """Use an ability on a target hero"""
        ability = next((a for a in self.abilities if a.id == ability_id), None)
        if not ability:
            return False

        distance = abs(self.position.x - target.position.x) + abs(self.position.y - target.position.y)
        if distance > ability.range:
            return False

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
    players: Dict[str, PlayerState] = {}
    current_turn: Optional[str] = None
    max_players: int = 2
    status: GameStatus = GameStatus.LOBBY
    grid_size: int = 20
    heroes_per_player: int = 4
    obstacles: Set[str] = set()
    moved_hero_id: Optional[str] = None

    def add_player(self, player_id: str) -> bool:
        """Add a player to the game if there's room. Returns True if successful."""
        if len(self.players) >= self.max_players:
            return False
        if player_id not in self.players:
            self.players[player_id] = PlayerState(player_id=player_id)
            if self.current_turn is None:
                self.current_turn = player_id
        return True

    def initialize_heroes(self) -> bool:
        """Initialize heroes for all players when game starts."""
        try:
            self.generate_obstacles()
            
            player_list = list(self.players.keys())
            
            for i, player_id in enumerate(player_list):
                player = self.players[player_id]
                player.heroes = []
                is_top_player = i == 0
                
                heroes_placed = 0
                max_attempts = 100
                attempts = 0
                
                while heroes_placed < self.heroes_per_player and attempts < max_attempts:
                    if is_top_player:
                        y = random.randint(0, 3)
                    else:
                        y = random.randint(self.grid_size - 4, self.grid_size - 1)
                    
                    x = random.randint(0, self.grid_size - 1)
                    pos_key = f"{x},{y}"
                    
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
        self.obstacles.clear()
        
        spawn_area = set()
        for y in range(4):  
            for x in range(self.grid_size):
                spawn_area.add(f"{x},{y}")
        for y in range(self.grid_size - 4, self.grid_size):  
            for x in range(self.grid_size):
                spawn_area.add(f"{x},{y}")
        
        available_cells = self.grid_size * (self.grid_size - 8)  
        num_obstacles = int(available_cells * 0.15)
        
        logger.info(f"Generating {num_obstacles} obstacles")
        
        obstacles_placed = 0
        max_attempts = num_obstacles * 3  
        attempts = 0
        
        while obstacles_placed < num_obstacles and attempts < max_attempts:
            x = random.randint(0, self.grid_size - 1)
            y = random.randint(4, self.grid_size - 5)  
            pos_key = f"{x},{y}"
            
            if pos_key not in spawn_area and pos_key not in self.obstacles:
                self.obstacles.add(pos_key)
                obstacles_placed += 1
            
            attempts += 1
        
        logger.info(f"Generated {len(self.obstacles)} obstacles: {sorted(self.obstacles)}")

    def is_position_occupied(self, x: int, y: int) -> bool:
        """Check if a position is occupied by any hero"""
        return any(
            hero.position.x == x and hero.position.y == y
            for player in self.players.values()
            for hero in player.heroes
        )

    def is_valid_position(self, x: int, y: int) -> bool:
        """Check if a position is within bounds and not an obstacle"""
        if x < 0 or x >= self.grid_size or y < 0 or y >= self.grid_size:
            return False
        pos_key = f"{x},{y}"
        return pos_key not in self.obstacles

    def find_path(self, start: Position, end: Position, max_distance: int) -> Optional[List[Position]]:
        """Find a valid path from start to end position within max_distance"""
        if not self.is_valid_position(end.x, end.y):
            return None

        if start.x == end.x and start.y == end.y:
            return [Position(x=start.x, y=start.y)]

        target_pos_str = f"{end.x},{end.y}"
        if target_pos_str in self.obstacles:
            return None

        queue = deque([(start.x, start.y, [Position(x=start.x, y=start.y)], 0)])
        visited = set()
        directions = [(0, 1), (1, 0), (0, -1), (-1, 0)]  

        while queue:
            x, y, path, distance = queue.popleft()
            pos_key = f"{x},{y}"

            if x == end.x and y == end.y:
                return path

            if pos_key in visited or distance >= max_distance:
                continue

            visited.add(pos_key)

            for dx, dy in directions:
                new_x, new_y = x + dx, y + dy
                new_key = f"{new_x},{new_y}"

                if (new_key not in visited and 
                    self.is_valid_position(new_x, new_y) and
                    new_key not in self.obstacles):
                    new_path = path + [Position(x=new_x, y=new_y)]
                    queue.append((new_x, new_y, new_path, distance + 1))

        return None

    def remove_player(self, player_id: str) -> None:
        """Remove a player from the game."""
        if player_id in self.players:
            del self.players[player_id]
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
            "status": self.status.value,  
            "grid_size": self.grid_size,
            "obstacles": list(self.obstacles)  
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
            
        self.moved_hero_id = None
        
        if self.current_turn:
            current_player = self.players[self.current_turn]
            for hero in current_player.heroes:
                hero.reset_movement()
