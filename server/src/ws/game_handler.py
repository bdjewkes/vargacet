from typing import Dict, Set
from fastapi import WebSocket
import json
import logging
from ..game.game_manager import game_manager

logger = logging.getLogger(__name__)

class GameConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, Dict[str, WebSocket]] = {}  # game_id -> {player_id -> websocket}
        self._logger = logging.getLogger(__name__)

    async def connect(self, websocket: WebSocket, game_id: str, player_id: str) -> bool:
        """Connect a player to a game. Returns True if successful."""
        game = game_manager.get_game(game_id)
        if not game:
            self._logger.error(f"Game {game_id} not found")
            return False

        # Add player to game if not already in
        if player_id not in game.players:
            if not game_manager.add_player_to_game(game_id, player_id):
                self._logger.error(f"Failed to add player {player_id} to game {game_id}")
                return False

        try:
            await websocket.accept()
            if game_id not in self.active_connections:
                self.active_connections[game_id] = {}
            self.active_connections[game_id][player_id] = websocket
            self._logger.info(f"Player {player_id} connected to game {game_id}")

            # Update player connection status
            game.update_player_connection(player_id, True)
            await self.broadcast_game_state(game_id)
            return True

        except Exception as e:
            self._logger.error(f"Error connecting player {player_id} to game {game_id}: {e}")
            return False

    def disconnect(self, game_id: str, player_id: str):
        """Handle player disconnection."""
        if game_id in self.active_connections and player_id in self.active_connections[game_id]:
            self._logger.info(f"Player {player_id} disconnected from game {game_id}")
            del self.active_connections[game_id][player_id]
            if not self.active_connections[game_id]:
                del self.active_connections[game_id]

            # Update player connection status
            game = game_manager.get_game(game_id)
            if game:
                game.update_player_connection(player_id, False)
                self.broadcast_game_state(game_id)
                return game

    async def broadcast_game_state(self, game_id: str):
        """Broadcast current game state to all players in the game."""
        game = game_manager.get_game(game_id)
        if not game:
            return

        game_state = game.get_game_status()
        message = {
            "type": "game_state",
            "payload": game_state
        }
        await self.broadcast(game_id, message)

    async def broadcast(self, game_id: str, message: dict):
        """Broadcast a message to all players in a game."""
        if game_id not in self.active_connections:
            return

        for websocket in self.active_connections[game_id].values():
            try:
                await websocket.send_json(message)
            except Exception as e:
                self._logger.error(f"Error broadcasting message: {e}")

    async def handle_message(self, game_id: str, player_id: str, message: dict):
        """Handle incoming messages from players."""
        self._logger.info(f"Handling message from player {player_id} in game {game_id}: {message}")
        
        message_type = message.get("type")
        if not message_type:
            return

        game = game_manager.get_game(game_id)
        if not game:
            return

        if message_type == "update_name":
            game.update_player_name(player_id, message.get("payload", {}).get("name"))
            await self.broadcast_game_state(game_id)

        elif message_type == "start_game":
            if game_manager.start_game(game_id):
                await self.broadcast_game_state(game_id)
            else:
                error_message = {
                    "type": "error",
                    "payload": {"message": "Could not start game"}
                }
                if game_id in self.active_connections and player_id in self.active_connections[game_id]:
                    await self.active_connections[game_id][player_id].send_json(error_message)

    async def broadcast_to_game(self, game_id: str, message: dict):
        """Broadcast message to all players in a game."""
        if game_id in self.active_connections:
            for websocket in self.active_connections[game_id].values():
                await websocket.send_json(message)

    async def send_to_player(self, game_id: str, player_id: str, message: dict):
        """Send message to a specific player."""
        if game_id in self.active_connections and player_id in self.active_connections[game_id]:
            await self.active_connections[game_id][player_id].send_json(message)

manager = GameConnectionManager()
