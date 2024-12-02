from fastapi import WebSocket
from typing import Tuple
import logging
from ...models.game import GameState, GameStatus
from ..connection_manager import send_error

logger = logging.getLogger(__name__)

async def handle_update_name(websocket: WebSocket, game: GameState, player_id: str, payload: dict) -> Tuple[bool, str]:
    """Handle player name update"""
    name = payload.get("name")
    if not name:
        await send_error(websocket, "Name is required")
        return False, "Name is required"

    if not game.update_player_name(player_id, name):
        await send_error(websocket, "Failed to update name")
        return False, "Failed to update name"

    return True, ""

async def handle_start_game(websocket: WebSocket, game: GameState, player_id: str) -> Tuple[bool, str]:
    """Handle game start request"""
    if game.status != GameStatus.LOBBY:
        await send_error(websocket, "Game has already started")
        return False, "Game already started"

    if not game.is_full():
        await send_error(websocket, "Game is not full")
        return False, "Game not full"

    if not all(p.name for p in game.players.values()):
        await send_error(websocket, "All players must set their names")
        return False, "Missing player names"

    game.start_game()
    
    return True, ""
