from fastapi import WebSocket
from typing import Tuple
from ...models.game import GameState, GameStatus
from ..connection_manager import send_error

async def handle_end_turn(websocket: WebSocket, game: GameState, player_id: str) -> Tuple[bool, str]:
    """Handle end turn message type"""
    if game.status != GameStatus.IN_PROGRESS:
        await send_error(websocket, "Game is not in progress")
        return False, "Game not in progress"

    if game.current_turn != player_id:
        await send_error(websocket, "Not your turn")
        return False, "Not your turn"

    game.set_next_turn()
    return True, ""

async def handle_undo_move(websocket: WebSocket, game: GameState, player_id: str) -> Tuple[bool, str]:
    """Handle undo move message type"""
    if game.status != GameStatus.IN_PROGRESS:
        await send_error(websocket, "Game is not in progress")
        return False, "Game not in progress"

    if game.current_turn != player_id:
        await send_error(websocket, "Not your turn")
        return False, "Not your turn"

    if not game.undo_turn():
        await send_error(websocket, "No turn state to restore")
        return False, "No turn state to restore"

    return True, ""
