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
        await websocket.accept()
        if game_id not in self.active_connections:
            self.active_connections[game_id] = {}
        self.active_connections[game_id][player_id] = websocket

        if game_id in self.games:
            game = self.games[game_id]
            game.update_player_connection(player_id, True)
            await self.broadcast_game_state(game_id)

    def disconnect(self, game_id: str, player_id: str):
        if game_id in self.active_connections:
            self.active_connections[game_id].pop(player_id, None)
            if game_id in self.games:
                game = self.games[game_id]
                game.update_player_connection(player_id, False)

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
            game.current_turn = next(iter(game.players.keys()))  # First player starts
            
            if not game.initialize_heroes():
                await self.send_error(websocket, "Failed to initialize heroes")
                game.status = GameStatus.LOBBY  # Reset game status
                return

            await self.broadcast_game_state(game_id)

        elif message_type == "move_hero":
            if game.status != GameStatus.IN_PROGRESS:
                await self.send_error(websocket, "Game hasn't started")
                return

            if game.current_turn != player_id:
                await self.send_error(websocket, "Not your turn")
                return

            payload = data.get("payload", {})
            hero_id = payload.get("hero_id")
            position = payload.get("position")

            if not hero_id or not position:
                await self.send_error(websocket, "Invalid move data")
                return

            # Find the hero
            hero = None
            for p in game.players.values():
                for h in p.heroes:
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

            # Calculate Manhattan distance
            dx = abs(hero.position.x - position["x"])
            dy = abs(hero.position.y - position["y"])
            distance = dx + dy

            if distance > hero.movement_points:
                await self.send_error(websocket, "Move too far")
                return

            # Check if destination is occupied
            if game.is_position_occupied(position["x"], position["y"]):
                await self.send_error(websocket, "Position occupied")
                return

            # Check if destination is an obstacle
            if f"{position['x']},{position['y']}" in game.obstacles:
                await self.send_error(websocket, "Cannot move to obstacle")
                return

            # Move the hero
            for player in game.players.values():
                for hero in player.heroes:
                    if hero.id == hero_id:
                        hero.position = Position(x=position["x"], y=position["y"])
                        break
            
            await self.broadcast_game_state(game_id)

        elif message_type == "end_turn":
            if game.status != GameStatus.IN_PROGRESS:
                await self.send_error(websocket, "Game hasn't started")
                return

            if game.current_turn != player_id:
                await self.send_error(websocket, "Not your turn")
                return

            logger.info(f"Processing end turn for player {player_id}")
            logger.info(f"Game state before turn change - current_turn: {game.current_turn}, players: {list(game.players.keys())}")

            # Set next turn using the game state method
            game.set_next_turn()

            logger.info(f"Game state after turn change - current_turn: {game.current_turn}, players: {list(game.players.keys())}")
            await self.broadcast_game_state(game_id)

manager = ConnectionManager()
