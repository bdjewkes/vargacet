from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime

class ChatMessage(BaseModel):
    sender_id: str
    sender_name: str
    content: str
    timestamp: datetime
    channel: str  # 'global' or game_id for lobby chat

class ChatManager:
    def __init__(self):
        self.global_messages: List[ChatMessage] = []
        self.lobby_messages: dict[str, List[ChatMessage]] = {}  # game_id -> messages
        self.max_messages = 100  # Keep last 100 messages per channel

    def add_message(self, message: ChatMessage) -> None:
        """Add a message to the appropriate channel"""
        if message.channel == 'global':
            self.global_messages.append(message)
            # Trim to keep only last N messages
            if len(self.global_messages) > self.max_messages:
                self.global_messages = self.global_messages[-self.max_messages:]
        else:
            # Lobby chat
            if message.channel not in self.lobby_messages:
                self.lobby_messages[message.channel] = []
            
            self.lobby_messages[message.channel].append(message)
            # Trim to keep only last N messages
            if len(self.lobby_messages[message.channel]) > self.max_messages:
                self.lobby_messages[message.channel] = self.lobby_messages[message.channel][-self.max_messages:]

    def get_global_messages(self) -> List[ChatMessage]:
        """Get all global chat messages"""
        return self.global_messages

    def get_lobby_messages(self, game_id: str) -> List[ChatMessage]:
        """Get all messages for a specific game lobby"""
        return self.lobby_messages.get(game_id, [])

    def cleanup_lobby(self, game_id: str) -> None:
        """Remove messages for a finished game"""
        if game_id in self.lobby_messages:
            del self.lobby_messages[game_id]
