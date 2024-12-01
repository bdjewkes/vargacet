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

        // Attempt to reconnect if not intentionally closed
        if (reconnectAttempts.current < maxReconnectAttempts) {
          console.log(`Reconnecting... Attempt ${reconnectAttempts.current + 1}/${maxReconnectAttempts}`);
          reconnectAttempts.current += 1;
          setTimeout(connect, 1000 * reconnectAttempts.current);  // Exponential backoff
        }
      };

      ws.current.onmessage = (event) => {
        console.log('WebSocket message received:', event.data);
        onMessageRef.current(event);
      };
      
      ws.current.onerror = (error) => {
        console.error('WebSocket error:', error);
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

  const send = useCallback((data: string) => {
    if (ws.current?.readyState === WebSocket.OPEN) {
      console.log('Sending WebSocket message:', data);
      ws.current.send(data);
    } else {
      console.error('WebSocket is not open. Current state:', ws.current?.readyState);
    }
  }, []);

  return { send, isConnected };
};
