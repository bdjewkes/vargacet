from fastapi import WebSocket
from typing import Dict, Optional, List
import logging
from ..models.game import GameState

logger = logging.getLogger(__name__)

async def send_error(websocket: WebSocket, message: str):
    """Send an error message to a client"""
    await websocket.send_json({
        "type": "error",
        "payload": {"message": message}
    })

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

manager = ConnectionManager()
