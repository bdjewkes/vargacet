import json
import logging
from typing import Dict, Set, List, Optional
from fastapi import WebSocket
from ..models.game import GameState, Position, GameStatus, Hero
from .connection_manager import manager
from .handlers import (
    handle_move,
    handle_ability,
    handle_end_turn,
    handle_undo_move,
    handle_update_name,
    handle_start_game
)

logger = logging.getLogger(__name__)

class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, Dict[str, WebSocket]] = {}
        self.games: Dict[str, GameState] = {}

    async def connect(self, websocket: WebSocket, game_id: str, player_id: str):
        """Connect a new client"""
        await websocket.accept()
        
        if game_id not in self.active_connections:
            self.active_connections[game_id] = {}
            
        self.active_connections[game_id][player_id] = websocket
        
        if game_id in self.games:
            game = self.games[game_id]
            if player_id in game.players:
                game.update_player_connection(player_id, True)
                await self.broadcast_game_state(game_id)

    def disconnect(self, game_id: str, player_id: str):
        """Disconnect a client"""
        if game_id in self.active_connections:
            if player_id in self.active_connections[game_id]:
                del self.active_connections[game_id][player_id]
            
            if not self.active_connections[game_id]:
                del self.active_connections[game_id]
                
        if game_id in self.games:
            game = self.games[game_id]
            if player_id in game.players:
                game.update_player_connection(player_id, False)

    async def broadcast_game_state(self, game_id: str, dead_heroes: Optional[List[Dict]] = None):
        """Broadcast game state to all players"""
        if game_id not in self.active_connections or game_id not in self.games:
            return
            
        game = self.games[game_id]
        game_state = game.get_game_status()
        
        if dead_heroes:
            game_state["dead_heroes"] = dead_heroes
            
        message = {
            "type": "game_state",
            "payload": game_state
        }
        
        for player_id, connection in self.active_connections[game_id].items():
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.error(f"Error sending game state to player {player_id}: {e}")

    async def send_error(self, websocket: WebSocket, message: str):
        """Send an error message to a client"""
        await websocket.send_json({
            "type": "error",
            "payload": {"message": message}
        })

    async def handle_message(self, websocket: WebSocket, game_id: str, player_id: str, data: dict):
        """Handle incoming WebSocket messages"""
        if game_id not in self.games:
            await self.send_error(websocket, "Game not found")
            return

        game = self.games[game_id]
        message_type = data.get("type")
        payload = data.get("payload", {})

        if message_type == "move_hero":
            success, error = await handle_move(websocket, game, player_id, payload)
            if success:
                await self.broadcast_game_state(game_id)

        elif message_type == "use_ability":
            success, error, dead_heroes = await handle_ability(websocket, game, player_id, payload)
            if success:
                await self.broadcast_game_state(game_id, dead_heroes)

        elif message_type == "end_turn":
            success, error = await handle_end_turn(websocket, game, player_id)
            if success:
                await self.broadcast_game_state(game_id)

        elif message_type == "undo_move":
            success, error = await handle_undo_move(websocket, game, player_id)
            if success:
                await self.broadcast_game_state(game_id)

        elif message_type == "update_name":
            success, error = await handle_update_name(websocket, game, player_id, payload)
            if success:
                await self.broadcast_game_state(game_id)

        elif message_type == "start_game":
            success, error = await handle_start_game(websocket, game, player_id)
            if success:
                await self.broadcast_game_state(game_id)

        elif message_type == "get_game_state":
            await self.broadcast_game_state(game_id)

        else:
            await self.send_error(websocket, f"Unknown message type: {message_type}")

manager = ConnectionManager()
