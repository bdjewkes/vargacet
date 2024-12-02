import json
import logging
from datetime import datetime
from typing import Dict, Set, List, Optional
from fastapi import WebSocket
from ..models.game import GameState, Position, GameStatus, Hero
from ..models.chat import ChatManager, ChatMessage
from .connection_manager import manager
from .handlers import (
    handle_move,
    handle_ability,
    handle_end_turn,
    handle_undo_move,
    handle_update_name,
    handle_start_game,
    chat_handler
)

logger = logging.getLogger(__name__)

class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, Dict[str, WebSocket]] = {}
        self.games: Dict[str, GameState] = {}
        self.chat_manager = ChatManager()
        self.global_connections: Dict[str, WebSocket] = {}  # player_id -> websocket

    async def connect(self, websocket: WebSocket, game_id: str, player_id: str):
        """Connect a new client"""
        await websocket.accept()
        
        # Store global connection
        self.global_connections[player_id] = websocket
        
        if game_id not in self.active_connections:
            self.active_connections[game_id] = {}
            
        self.active_connections[game_id][player_id] = websocket
        
        if game_id in self.games:
            game = self.games[game_id]
            if player_id in game.players:
                game.update_player_connection(player_id, True)
                await self.broadcast_game_state(game_id)
                
                # Send chat history
                lobby_messages = self.chat_manager.get_lobby_messages(game_id)
                global_messages = self.chat_manager.get_global_messages()
                
                for message in global_messages + lobby_messages:
                    await websocket.send_json({
                        'type': 'chat_message',
                        'payload': {
                            'sender_id': message.sender_id,
                            'sender_name': message.sender_name,
                            'content': message.content,
                            'timestamp': message.timestamp.isoformat(),
                            'channel': message.channel
                        }
                    })

    def disconnect(self, game_id: str, player_id: str):
        """Disconnect a client"""
        if game_id in self.active_connections:
            if player_id in self.active_connections[game_id]:
                del self.active_connections[game_id][player_id]
            
            if not self.active_connections[game_id]:
                del self.active_connections[game_id]
                # Cleanup chat when game is done
                self.chat_manager.cleanup_lobby(game_id)
                
        if game_id in self.games:
            game = self.games[game_id]
            if player_id in game.players:
                game.update_player_connection(player_id, False)
        
        # Remove from global connections
        if player_id in self.global_connections:
            del self.global_connections[player_id]

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

        elif message_type == "chat_message":
            await chat_handler.handle_chat_message(
                websocket=websocket,
                game=game,
                player_id=player_id,
                chat_manager=self.chat_manager,
                connection_manager=self,
                message_data=data.get("payload", {})
            )

        else:
            await self.send_error(websocket, f"Unknown message type: {message_type}")

    async def handle_chat_message(self, websocket: WebSocket, game_id: str, player_id: str, data: dict):
        """Handle incoming chat messages"""
        try:
            content = data.get('content', '').strip()
            channel = data.get('channel', 'global')
            player_name = data.get('player_name', 'Unknown Player')
            
            if not content:
                return

            message = ChatMessage(
                sender_id=player_id,
                sender_name=player_name,
                content=content,
                timestamp=datetime.utcnow(),
                channel=channel if channel == 'global' else game_id
            )
            
            self.chat_manager.add_message(message)
            
            response = {
                'type': 'chat_message',
                'payload': {
                    'sender_id': message.sender_id,
                    'sender_name': message.sender_name,
                    'content': message.content,
                    'timestamp': message.timestamp.isoformat(),
                    'channel': message.channel
                }
            }
            
            if channel == 'global':
                # Broadcast to all connected clients
                for ws in self.global_connections.values():
                    try:
                        await ws.send_json(response)
                    except Exception as e:
                        logger.error(f"Error sending global message: {e}")
            else:
                # Broadcast only to players in the game
                if game_id in self.active_connections:
                    for ws in self.active_connections[game_id].values():
                        try:
                            await ws.send_json(response)
                        except Exception as e:
                            logger.error(f"Error sending lobby message: {e}")
                            
        except Exception as e:
            logger.error(f"Error handling chat message: {e}")
            await websocket.send_json({
                'type': 'error',
                'payload': {'message': 'Failed to send chat message'}
            })

manager = ConnectionManager()
