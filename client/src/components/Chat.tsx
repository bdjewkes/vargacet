import React, { useState, useRef, useEffect } from 'react';
import './Chat.css';

interface ChatMessage {
    sender_id: string;
    sender_name: string;
    content: string;
    timestamp: string;
    channel: string;
}

interface ChatProps {
    gameId: string | null;
    playerId: string;
    playerName: string;
    onSendMessage: (content: string, channel: string) => void;
    messages: ChatMessage[];
}

const Chat: React.FC<ChatProps> = ({ gameId, playerId, playerName, onSendMessage, messages }) => {
    const [message, setMessage] = useState<string>('');
    const [activeChannel, setActiveChannel] = useState<'global' | 'lobby'>('lobby');
    const messagesEndRef = useRef<HTMLDivElement>(null);

    const scrollToBottom = () => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    };

    useEffect(() => {
        scrollToBottom();
    }, [messages]);

    const handleSubmit = (e: React.FormEvent) => {
        e.preventDefault();
        if (message.trim()) {
            onSendMessage(message.trim(), activeChannel);
            setMessage('');
        }
    };

    const filteredMessages = messages.filter(msg => 
        activeChannel === 'global' ? msg.channel === 'global' : msg.channel === gameId
    );

    return (
        <div className="chat-container">
            <div className="chat-tabs">
                <button 
                    className={`chat-tab ${activeChannel === 'lobby' ? 'active' : ''}`}
                    onClick={() => setActiveChannel('lobby')}
                >
                    Lobby
                </button>
                <button 
                    className={`chat-tab ${activeChannel === 'global' ? 'active' : ''}`}
                    onClick={() => setActiveChannel('global')}
                >
                    Global
                </button>
            </div>
            
            <div className="chat-messages">
                {filteredMessages.map((msg, index) => (
                    <div 
                        key={index} 
                        className={`chat-message ${msg.sender_id === playerId ? 'own-message' : ''}`}
                    >
                        <div className="message-header">
                            <span className="sender-name">{msg.sender_name}</span>
                            <span className="timestamp">
                                {new Date(msg.timestamp).toLocaleTimeString()}
                            </span>
                        </div>
                        <div className="message-content">{msg.content}</div>
                    </div>
                ))}
                <div ref={messagesEndRef} />
            </div>

            <form onSubmit={handleSubmit} className="chat-input">
                <input
                    type="text"
                    value={message}
                    onChange={(e) => setMessage(e.target.value)}
                    placeholder={`Message ${activeChannel} chat...`}
                />
                <button type="submit">Send</button>
            </form>
        </div>
    );
};

export default Chat;
