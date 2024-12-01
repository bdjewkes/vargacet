import { useEffect, useRef, useCallback, useState } from 'react';

export const useWebSocket = (
  url: string,
  onMessage: (event: MessageEvent) => void
) => {
  const ws = useRef<WebSocket | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  const reconnectAttempts = useRef(0);
  const maxReconnectAttempts = 3;

  // Store the URL to detect changes
  const urlRef = useRef(url);
  const onMessageRef = useRef(onMessage);

  // Update refs when props change
  useEffect(() => {
    urlRef.current = url;
    onMessageRef.current = onMessage;
  }, [url, onMessage]);

  const connect = useCallback(() => {
    // Don't create a new connection if we already have one that's connecting or open
    if (ws.current && [WebSocket.CONNECTING, WebSocket.OPEN].includes(ws.current.readyState)) {
      if (ws.current.readyState === WebSocket.OPEN) {
        setIsConnected(true);
      }
      return;
    }

    try {
      console.log('Creating new WebSocket connection to:', urlRef.current);
      ws.current = new WebSocket(urlRef.current);

      ws.current.onopen = () => {
        console.log('WebSocket connected successfully');
        setIsConnected(true);
        reconnectAttempts.current = 0;
      };

      ws.current.onclose = (event) => {
        console.log('WebSocket disconnected:', event.code, event.reason);
        setIsConnected(false);

        // Don't reconnect if the close was intentional (code 1000) or the game is full (code 4000)
        // or if the game has ended (code 4001)
        if (event.code === 1000 || event.code === 4000 || event.code === 4001) {
          console.log('WebSocket closed intentionally or game ended, not reconnecting');
          return;
        }

        // Attempt to reconnect if not intentionally closed
        if (reconnectAttempts.current < maxReconnectAttempts) {
          console.log(`Reconnecting... Attempt ${reconnectAttempts.current + 1}/${maxReconnectAttempts}`);
          reconnectAttempts.current += 1;
          setTimeout(connect, 1000 * Math.pow(2, reconnectAttempts.current));  // Exponential backoff
        } else {
          console.log('Max reconnection attempts reached');
        }
      };

      ws.current.onmessage = (event) => {
        try {
          console.log('WebSocket message received:', event.data);
          onMessageRef.current(event);
        } catch (error) {
          console.error('Error processing WebSocket message:', error);
        }
      };
      
      ws.current.onerror = (error) => {
        console.error('WebSocket error:', error);
        // Don't set isConnected to false here, let onclose handle the state
      };
    } catch (error) {
      console.error('Error creating WebSocket connection:', error);
      setIsConnected(false);
    }
  }, []); // No dependencies since we use refs

  useEffect(() => {
    connect();
    return () => {
      console.log('Cleaning up WebSocket connection');
      if (ws.current) {
        ws.current.onclose = null; // Prevent reconnection attempts during cleanup
        ws.current.close();
        ws.current = null;
        setIsConnected(false);
      }
    };
  }, [connect]);

  const send = useCallback((data: any) => {
    if (ws.current?.readyState === WebSocket.OPEN) {
      const message = typeof data === 'string' ? data : JSON.stringify(data);
      console.log('Sending WebSocket message:', message);
      ws.current.send(message);
    } else {
      console.error('WebSocket is not open. Current state:', ws.current?.readyState);
    }
  }, []);

  return { send, isConnected };
};
