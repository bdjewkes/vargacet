from datetime import datetime
import logging
from fastapi import WebSocket
from ...models.chat import ChatMessage, ChatManager
from ...models.game import GameState

logger = logging.getLogger(__name__)

async def handle_chat_message(
    websocket: WebSocket,
    game: GameState,
    player_id: str,
    chat_manager: ChatManager,
    connection_manager,
    message_data: dict
) -> None:
    """Handle incoming chat messages"""
    try:
        content = message_data.get('content', '').strip()
        channel = message_data.get('channel', 'global')
        player_name = message_data.get('player_name', 'Unknown Player')
        
        if not content:
            return

        message = ChatMessage(
            sender_id=player_id,
            sender_name=player_name,
            content=content,
            timestamp=datetime.utcnow(),
            channel=channel if channel == 'global' else game.game_id
        )
        
        chat_manager.add_message(message)
        
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
            for ws in connection_manager.global_connections.values():
                try:
                    await ws.send_json(response)
                except Exception as e:
                    logger.error(f"Error sending global message: {e}")
        else:
            # Broadcast only to players in the game
            if game.game_id in connection_manager.active_connections:
                for ws in connection_manager.active_connections[game.game_id].values():
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
