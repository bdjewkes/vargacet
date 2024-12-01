from typing import Dict, Optional
from ..models.game import GameState, GameStatus
import uuid
import logging

logger = logging.getLogger(__name__)

class GameManager:
    def __init__(self):
        self.games: Dict[str, GameState] = {}
        self._logger = logging.getLogger(__name__)

    def create_game(self) -> GameState:
        """Create a new game and return it."""
        game_id = str(uuid.uuid4())
        game = GameState(game_id=game_id)
        self.games[game_id] = game
        self._logger.info(f"Created game {game_id}. Total games: {len(self.games)}")
        return game

    def get_game(self, game_id: str) -> Optional[GameState]:
        """Get a game by ID."""
        game = self.games.get(game_id)
        if game:
            self._logger.info(f"Found game {game_id}")
        else:
            self._logger.error(f"Game {game_id} not found")
        return game

    def list_games(self) -> list:
        """List all active games."""
        games = [game.get_game_status() for game in self.games.values()]
        self._logger.info(f"Listing games. Total: {len(games)}")
        for game in games:
            self._logger.info(f"Game {game['game_id']}: {len(game['players'])} players")
        return games

    def add_player_to_game(self, game_id: str, player_id: str) -> bool:
        """Add a player to a game. Returns True if successful."""
        game = self.get_game(game_id)
        if game and not game.is_full():
            success = game.add_player(player_id)
            self._logger.info(f"Added player {player_id} to game {game_id}: {success}")
            return success
        return False

    def remove_player_from_game(self, game_id: str, player_id: str):
        """Remove a player from a game."""
        game = self.get_game(game_id)
        if game:
            game.remove_player(player_id)
            self._logger.info(f"Removed player {player_id} from game {game_id}")
            # Remove game if empty
            if not game.players:
                del self.games[game_id]
                self._logger.info(f"Deleted empty game {game_id}")

    def start_game(self, game_id: str) -> bool:
        """Start a game if possible. Returns True if successful."""
        game = self.get_game(game_id)
        if not game or len(game.players) != game.max_players:
            self._logger.error(f"Cannot start game {game_id}: Not enough players")
            return False
            
        if game.status != GameStatus.LOBBY:
            self._logger.error(f"Cannot start game {game_id}: Game already started")
            return False

        # Initialize heroes for all players
        if not game.initialize_heroes():
            return False

        self._logger.info(f"Starting game {game_id}")
        game.status = GameStatus.IN_PROGRESS
        # Set the first player's turn
        game.current_turn = next(iter(game.players))
        return True

game_manager = GameManager()
