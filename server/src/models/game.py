from typing import Dict, List, Optional, Set, Tuple, Literal
from pydantic import BaseModel
from enum import Enum
import random
import logging
from collections import deque
import uuid

logger = logging.getLogger(__name__)

class GameStatus(Enum):
    LOBBY = "lobby"
    IN_PROGRESS = "in_progress"
    FINISHED = "finished"
    GAME_OVER = "game_over"

class Position(BaseModel):
    x: int
    y: int

class EffectType(str, Enum):
    HEAL = "heal"
    DAMAGE = "damage"

class Effect(BaseModel):
    type: EffectType
    amount: int
    area_of_effect: int = 0  # Default to 0 for single-target effects

class Ability(BaseModel):
    id: str
    name: str
    range: int
    effect: Effect
    action_cost: int = 1  # Default cost of 1 action point

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
    max_action_points: int = 2
    current_action_points: int = 2
    abilities: List[Ability] = [
        Ability(
            id="heal_1",
            name="Heal",
            range=3,
            effect=Effect(type=EffectType.HEAL, amount=5),
            action_cost=2
        ),
        Ability(
            id="damage_1",
            name="Punch",
            range=1,
            effect=Effect(type=EffectType.DAMAGE, amount=6),
            action_cost=1
        ),
        Ability(
            id="ranged_1",
            name="Shortbow",
            range=3,
            effect=Effect(type=EffectType.DAMAGE, amount=4),
            action_cost=1
        ),
        Ability(
            id="explosion_1",
            name="Explosion",
            range=4,
            effect=Effect(type=EffectType.DAMAGE, amount=3, area_of_effect=1),
            action_cost=2
        ),
    ]
    name: str  # Single letter A-Z

    def reset_movement(self):
        """Reset movement points at the start of turn"""
        self.movement_points = self.max_movement
        self.current_action_points = self.max_action_points

    def can_move_to(self, new_position: Position, game_state: 'GameState') -> bool:
        """Check if hero can move to new position based on remaining points and valid path"""
        if (new_position.x < 0 or new_position.x >= game_state.grid_size or
            new_position.y < 0 or new_position.y >= game_state.grid_size):
            return False

        target_pos_str = f"{new_position.x},{new_position.y}"
        if target_pos_str in game_state.obstacles:
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

class PlayerState(BaseModel):
    player_id: str
    name: Optional[str] = None
    connected: bool = False
    heroes: List[Hero] = []

class GameState(BaseModel):
    game_id: str
    players: Dict[str, PlayerState] = {}
    current_turn: Optional[str] = None
    status: GameStatus = GameStatus.LOBBY
    grid_size: int = 10
    heroes_per_player: int = 4
    obstacles: Set[str] = set()
    moved_hero_id: Optional[str] = None
    _hero_letter_counter: int = 0  # Internal counter for assigning hero letters
    start_of_turn_state: Optional[Dict] = None  # Store serialized game state at turn start

    def create_hero(self, owner_id: str, position: Position) -> Hero:
        """Create a new hero with a unique letter name"""
        hero_letter = chr(65 + self._hero_letter_counter)  # 65 is ASCII for 'A'
        self._hero_letter_counter = (self._hero_letter_counter + 1) % 26  # Wrap around at Z
        
        return Hero(
            id=f"{owner_id}_hero_{uuid.uuid4()}",
            position=position,
            owner_id=owner_id,
            name=hero_letter,
            abilities=[
                Ability(
                    id="heal_1",
                    name="Heal",
                    range=3,
                    effect=Effect(type=EffectType.HEAL, amount=5),
                    action_cost=2
                ),
                Ability(
                    id="damage_1",
                    name="Punch",
                    range=1,
                    effect=Effect(type=EffectType.DAMAGE, amount=6),
                    action_cost=1
                ),
                Ability(
                    id="ranged_1",
                    name="Shortbow",
                    range=3,
                    effect=Effect(type=EffectType.DAMAGE, amount=4),
                    action_cost=1
                ),
                Ability(
                    id="explosion_1",
                    name="Explosion",
                    range=4,
                    effect=Effect(type=EffectType.DAMAGE, amount=3, area_of_effect=1),
                    action_cost=2
                ),
            ]
        )

    def add_player(self, player_id: str) -> bool:
        """Add a player to the game if there's room. Returns True if successful."""
        if player_id in self.players:
            return True

        if len(self.players) >= 2:
            return False

        self.players[player_id] = PlayerState(
            player_id=player_id,
            heroes=[]
        )
            
        return True

    def initialize_heroes(self) -> bool:
        """Initialize heroes for all players when game starts."""
        try:
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
                        hero = self.create_hero(player_id, Position(x=x, y=y))
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
        """Generate a small number of random obstacles"""
        num_obstacles = int(self.grid_size * self.grid_size * 0.10)
        self.obstacles.clear()
        
        # Keep track of positions we want to keep clear for heroes
        reserved_positions = set()
        reserved_player_starting_height = 3
        for y in range(reserved_player_starting_height):
            for x in range(self.grid_size):
                reserved_positions.add(f"{x},{y}")
        for y in range(self.grid_size-reserved_player_starting_height, self.grid_size):
            for x in range(self.grid_size):
                reserved_positions.add(f"{x},{y}")

        attempts = 0
        max_attempts = 1000  # Prevent infinite loop
        while len(self.obstacles) < num_obstacles and attempts < max_attempts:
            x = random.randint(0, self.grid_size - 1)
            y = random.randint(0, self.grid_size - 1)
            pos_key = f"{x},{y}"
            
            if pos_key not in reserved_positions and pos_key not in self.obstacles:
                self.obstacles.add(pos_key)
            
            attempts += 1

        if len(self.obstacles) < num_obstacles:
            logger.warning(f"Could only place {len(self.obstacles)} obstacles out of {num_obstacles} desired")

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

    def find_path(self, start: Position, end: Position, max_distance: int, ignore_heroes: bool = False) -> Optional[List[Position]]:
        """Find a valid path from start to end position within max_distance.
        If ignore_heroes is True, heroes won't block the path (used for ability range checks)"""
        if not self.is_valid_position(end.x, end.y):
            return None

        if start.x == end.x and start.y == end.y:
            return [Position(x=start.x, y=start.y)]

        target_pos_str = f"{end.x},{end.y}"
        if target_pos_str in self.obstacles:
            return None

        # Priority queue: [manhattan_distance, x_distance, y_distance, x, y, path, distance]
        queue = [(abs(end.x - start.x) + abs(end.y - start.y), abs(end.x - start.x), abs(end.y - start.y),
                 start.x, start.y, [Position(x=start.x, y=start.y)], 0)]
        visited = set()
        directions = [(0, 1), (1, 0), (0, -1), (-1, 0)]  # All orthogonal directions
        
        while queue:
            _, _, _, x, y, path, distance = queue.pop(0)
            pos_key = f"{x},{y}"

            if x == end.x and y == end.y:
                return path

            if pos_key in visited or distance >= max_distance:
                continue

            visited.add(pos_key)

            # Try all orthogonal directions
            for dx, dy in directions:
                new_x, new_y = x + dx, y + dy
                new_key = f"{new_x},{new_y}"

                if (new_key not in visited and 
                    self.is_valid_position(new_x, new_y) and
                    new_key not in self.obstacles and
                    (ignore_heroes or not self.is_position_occupied(new_x, new_y))):
                    new_path = path + [Position(x=new_x, y=new_y)]
                    manhattan_dist = abs(end.x - new_x) + abs(end.y - new_y)
                    x_dist = abs(end.x - new_x)
                    y_dist = abs(end.y - new_y)
                    priority = (manhattan_dist, x_dist, y_dist)
                    
                    # Insert maintaining priority order
                    i = 0
                    while i < len(queue) and queue[i][0:3] <= priority:
                        i += 1
                    queue.insert(i, (*priority, new_x, new_y, new_path, distance + 1))

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
        return len(self.players) >= 2

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
        if not self.players:
            return

        # Save current game state before changing turn
        self.save_turn_state()

        # clear the moved hero ID
        self.moved_hero_id = None
            
        # Get list of player IDs
        player_ids = list(self.players.keys())
            
        if self.current_turn is None:
            # Start with first player
            self.current_turn = player_ids[0]
        else:
            # Find current player's index
            current_idx = player_ids.index(self.current_turn)
            # Set to next player (wrap around to 0 if at end)
            self.current_turn = player_ids[(current_idx + 1) % len(player_ids)]
            
        # Reset movement points for current player's heroes
        if self.current_turn in self.players:
            current_player = self.players[self.current_turn]
            for hero in current_player.heroes:
                hero.reset_movement()
                # Reset action points at turn start
                hero.current_action_points = hero.max_action_points

    def save_turn_state(self) -> None:
        """Save the current game state at the start of a turn"""
        # Create a copy of the current state, excluding the start_of_turn_state and current_turn
        current_state = self.dict(exclude={'start_of_turn_state', 'current_turn'})
        
        # Convert PlayerState objects to their dict representation
        if 'players' in current_state:
            current_state['players'] = {
                player_id: player.dict() 
                for player_id, player in self.players.items()
            }
        
        self.start_of_turn_state = current_state

    def undo_turn(self) -> bool:
        """Restore the game state to the start of the current turn"""
        if self.start_of_turn_state is None:
            return False

        # Remember whose turn it is
        current_turn = self.current_turn

        saved_state = self.start_of_turn_state.copy()
        
        # Convert saved player states back to PlayerState objects
        if 'players' in saved_state:
            saved_state['players'] = {
                player_id: PlayerState(**player_data)
                for player_id, player_data in saved_state['players'].items()
            }

        # Restore all fields from the saved state
        for field, value in saved_state.items():
            if hasattr(self, field):
                setattr(self, field, value)

        # Ensure it's still the same player's turn
        self.current_turn = current_turn

        # Clear the moved hero ID since we're undoing
        self.moved_hero_id = None
        return True

    def remove_dead_heroes(self) -> List[Hero]:
        """Remove any heroes with 0 or less HP and return the list of removed heroes"""
        dead_heroes = []
        for player in self.players.values():
            # Find dead heroes
            dead = [hero for hero in player.heroes if hero.current_hp <= 0]
            # Remove them from the player's hero list
            player.heroes = [hero for hero in player.heroes if hero.current_hp > 0]
            dead_heroes.extend(dead)
            
            # Check if this player has lost (no heroes left)
            if not player.heroes:
                self.status = GameStatus.GAME_OVER
                # Set the winner to the other player
                winner_id = next(pid for pid in self.players.keys() if pid != player.player_id)
                self.current_turn = winner_id
                logger.info(f"Game {self.game_id} over. Winner: {winner_id}")
                break
                
        return dead_heroes

    def apply_effect(self, target_hero: Hero, effect: Effect) -> List[Hero]:
        """Apply an effect to a hero and handle any resulting deaths"""
        if effect.type == EffectType.DAMAGE:
            # Apply damage, considering armor reduction
            damage_reduction = target_hero.armor / 100.0  # Convert armor to percentage
            actual_damage = int(effect.amount * (1 - damage_reduction))
            target_hero.current_hp = max(0, target_hero.current_hp - actual_damage)
        elif effect.type == EffectType.HEAL:
            # Apply healing, not exceeding max HP
            target_hero.current_hp = min(target_hero.max_hp, target_hero.current_hp + effect.amount)
        
        # Check for and handle any deaths
        dead_heroes = self.remove_dead_heroes()
        return dead_heroes

    def use_ability(self, hero_id: str, ability_id: str, target_position: Position) -> Tuple[bool, Optional[str], List[Hero]]:
        """Use a hero's ability. Returns (success, error_message, list_of_dead_heroes)"""
        # Find the hero
        hero = self.get_hero_by_id(hero_id)
        if not hero:
            return False, "Hero not found", []
            
        # Verify it's the hero's owner's turn
        if hero.owner_id != self.current_turn:
            return False, "Not your turn", []
            
        # Find the ability
        ability = next((a for a in hero.abilities if a.id == ability_id), None)
        if not ability:
            return False, "Ability not found", []
            
        # Check if hero has enough action points
        if hero.current_action_points < ability.action_cost:
            return False, "Not enough action points", []
            
        # Check range using Manhattan distance
        distance = abs(hero.position.x - target_position.x) + abs(hero.position.y - target_position.y)
        if distance > ability.range:
            return False, "Target out of range", []
            
        # For area effects, we don't need a target hero at the exact position
        if ability.effect.area_of_effect == 0:
            # Single target ability needs a hero at the position
            target_hero = self.get_hero_at_position(target_position)
            if not target_hero:
                return False, "No target at that position", []
            affected_heroes = [target_hero]
        else:
            # Area effect - get all heroes in range
            affected_heroes = self.get_heroes_in_area(target_position, ability.effect.area_of_effect)
            if not affected_heroes:
                return False, "No targets in area", []
            
        # Consume action points
        hero.current_action_points -= ability.action_cost
            
        # Apply the effect to all affected heroes
        dead_heroes = []
        for target_hero in affected_heroes:
            dead_heroes.extend(self.apply_effect(target_hero, ability.effect))
        
        # Remove duplicates from dead_heroes list
        dead_heroes = list(set(dead_heroes))
            
        return True, None, dead_heroes

    def get_hero_by_id(self, hero_id: str) -> Optional[Hero]:
        """Find a hero by ID"""
        for player in self.players.values():
            for hero in player.heroes:
                if hero.id == hero_id:
                    return hero
        return None

    def get_hero_at_position(self, position: Position) -> Optional[Hero]:
        """Find a hero at a given position"""
        for player in self.players.values():
            for hero in player.heroes:
                if hero.position.x == position.x and hero.position.y == position.y:
                    return hero
        return None

    def is_in_range(self, start: Position, end: Position, range: int) -> bool:
        """Check if a position is within a given range using find_path.
        For ability range checks, we ignore heroes blocking the path."""
        path = self.find_path(start, end, range, ignore_heroes=True)
        if not path:
            return False
        return len(path) - 1 <= range

    def start_game(self) -> None:
        """Start the game by initializing heroes and setting initial game state"""
        if len(self.players) != 2:
            return
            
        # First generate obstacles
        self.generate_obstacles()
        
        # Then initialize heroes
        if not self.initialize_heroes():
            logger.error("Failed to initialize heroes")
            return
            
        # Finally, set game state
        self.status = GameStatus.IN_PROGRESS
        self.current_turn = list(self.players.keys())[0]

    def can_move_to(self, hero_id: str, new_position: Position) -> bool:
        """Check if a hero can move to a new position"""
        hero = self.get_hero_by_id(hero_id)
        if not hero:
            return False
        
        # Check if it's this hero's turn
        if hero.owner_id != self.current_turn:
            return False
            
        # Check if another hero has already moved (only one hero can move per turn)
        if self.moved_hero_id and self.moved_hero_id != hero_id:
            return False
            
        # Try to move the hero
        # Get path to new position
        path = self.find_path(hero.position, new_position, hero.movement_points, ignore_heroes=False)
        if not path:
            return False
            
        # Check if path length is within movement points
        path_length = len(path) - 1
        if path_length > hero.movement_points:
            return False
            
        return True

    def move_hero(self, hero_id: str, new_position: Position) -> bool:
        """Move a hero to a new position"""
        hero = self.get_hero_by_id(hero_id)
        if not hero:
            return False
            
        # Verify it's this hero's turn
        if hero.owner_id != self.current_turn:
            return False
            
        # Check if another hero has already moved (only one hero can move per turn)
        if self.moved_hero_id and self.moved_hero_id != hero_id:
            return False
            
        # Try to move the hero
        if hero.move_to(new_position, self):
            self.moved_hero_id = hero_id
            return True
            
        return False

    def get_heroes_in_area(self, center: Position, radius: int) -> List[Hero]:
        """Find all heroes within a radius of a position using Manhattan distance"""
        heroes_in_area = []
        for player in self.players.values():
            for hero in player.heroes:
                distance = abs(hero.position.x - center.x) + abs(hero.position.y - center.y)
                if distance <= radius:
                    heroes_in_area.append(hero)
        return heroes_in_area
