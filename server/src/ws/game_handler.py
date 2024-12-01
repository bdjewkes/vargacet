import json
import logging
from typing import Dict, Set
from fastapi import WebSocket
from ..models.game import GameState, Position, GameStatus

logger = logging.getLogger(__name__)

class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, Dict[str, WebSocket]] = {}
        self.games: Dict[str, GameState] = {}

    async def connect(self, websocket: WebSocket, game_id: str, player_id: str):
        try:
            await websocket.accept()
            if game_id not in self.active_connections:
                self.active_connections[game_id] = {}
            self.active_connections[game_id][player_id] = websocket

            if game_id in self.games:
                game = self.games[game_id]
                game.update_player_connection(player_id, True)
                await self.broadcast_game_state(game_id)
        except Exception as e:
            logger.error(f"Error connecting player {player_id} to game {game_id}: {str(e)}")
            raise

    def disconnect(self, game_id: str, player_id: str):
        try:
            if game_id in self.active_connections:
                # Remove the connection
                self.active_connections[game_id].pop(player_id, None)
                
                # If this was the last player, clean up the game
                if not self.active_connections[game_id]:
                    self.active_connections.pop(game_id, None)
                    # Optionally, you might want to remove the game if it's empty
                    # self.games.pop(game_id, None)
                
                # Update player connection status
                if game_id in self.games:
                    game = self.games[game_id]
                    game.update_player_connection(player_id, False)
        except Exception as e:
            logger.error(f"Error disconnecting player {player_id} from game {game_id}: {str(e)}")

    async def broadcast_game_state(self, game_id: str):
        if game_id not in self.games:
            return
        
        game = self.games[game_id]
        game_state = game.get_game_status()
        
        if game_id in self.active_connections:
            for player_id, connection in self.active_connections[game_id].items():
                try:
                    await connection.send_json({
                        "type": "game_state",
                        "payload": game_state
                    })
                except Exception as e:
                    logger.error(f"Error sending game state to player {player_id}: {e}")

    async def send_error(self, websocket: WebSocket, message: str):
        await websocket.send_json({
            "type": "error",
            "payload": {
                "message": message
            }
        })

    async def handle_message(self, websocket: WebSocket, game_id: str, player_id: str, data: dict):
        if game_id not in self.games:
            await self.send_error(websocket, "Game not found")
            return

        game = self.games[game_id]
        message_type = data.get("type")

        if message_type == "update_name":
            name = data.get("payload", {}).get("name")
            if name:
                game.update_player_name(player_id, name)
                await self.broadcast_game_state(game_id)

        elif message_type == "start_game":
            if game.status != GameStatus.LOBBY:
                await self.send_error(websocket, "Game has already started")
                return

            if not game.is_full():
                await self.send_error(websocket, "Game is not full")
                return

            if not all(p.name for p in game.players.values()):
                await self.send_error(websocket, "All players must set their names")
                return

            logger.info(f"Starting game {game_id}")
            game.status = GameStatus.IN_PROGRESS
            game.initialize_heroes()
            game.generate_obstacles()
            game.set_next_turn()
            await self.broadcast_game_state(game_id)

        elif message_type == "move_hero":
            if game.status != GameStatus.IN_PROGRESS:
                await self.send_error(websocket, "Game is not in progress")
                return

            if game.current_turn != player_id:
                await self.send_error(websocket, "Not your turn")
                return

            payload = data.get("payload", {})
            hero_id = payload.get("hero_id")
            new_position = payload.get("position")

            if not hero_id or not new_position:
                await self.send_error(websocket, "Invalid move request")
                return

            # Convert position dict to Position object
            try:
                new_pos = Position(**new_position)
            except Exception as e:
                await self.send_error(websocket, "Invalid position format")
                return

            if game.moved_hero_id is not None and game.moved_hero_id != hero_id:
                await self.send_error(websocket, "You can only move one hero per turn")
                return

            # Find the hero
            hero = None
            for player in game.players.values():
                for h in player.heroes:
                    if h.id == hero_id:
                        hero = h
                        break
                if hero:
                    break

            if not hero:
                await self.send_error(websocket, "Hero not found")
                return

            if hero.owner_id != player_id:
                await self.send_error(websocket, "Not your hero")
                return

            # Check if the move is valid
            if not hero.move_to(new_pos):
                await self.send_error(websocket, "Invalid move")
                return

            # Track which hero moved this turn
            game.moved_hero_id = hero_id

            await self.broadcast_game_state(game_id)

        elif message_type == "undo_move":
            if game.status != GameStatus.IN_PROGRESS:
                await self.send_error(websocket, "Game is not in progress")
                return

            if game.current_turn != player_id:
                await self.send_error(websocket, "Not your turn")
                return

            # Find all heroes owned by the player and undo their moves
            for player in game.players.values():
                if player.player_id == player_id:
                    for hero in player.heroes:
                        hero.undo_move()
            
            # Reset the moved hero tracking
            game.moved_hero_id = None

            await self.broadcast_game_state(game_id)

        elif message_type == "end_turn":
            if game.status != GameStatus.IN_PROGRESS:
                await self.send_error(websocket, "Game is not in progress")
                return

            if game.current_turn != player_id:
                await self.send_error(websocket, "Not your turn")
                return

            game.set_next_turn()
            await self.broadcast_game_state(game_id)

manager = ConnectionManager()
