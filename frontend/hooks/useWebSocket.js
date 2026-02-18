'use client';

import { useEffect, useRef, useState, useCallback } from 'react';
import { getWsUrl } from '../lib/constants';
import { getAlertKey, getCameraId, getEventType } from '../lib/utils';

export function useWebSocket() {
  const [status, setStatus] = useState('connecting');
  const [alerts, setAlerts] = useState({});
  const [incidents, setIncidents] = useState([]);
  const [alertCount, setAlertCount] = useState(0);
  const wsRef = useRef(null);
  const reconnectTimeoutRef = useRef(null);
  const reconnectAttempts = useRef(0);

  const connect = useCallback(() => {
    const wsUrl = getWsUrl();
    console.log('[WS] Connecting to:', wsUrl);
    
    try {
      wsRef.current = new WebSocket(wsUrl);

      wsRef.current.onopen = () => {
        console.log('[WS] Connected');
        setStatus('connected');
        reconnectAttempts.current = 0;
      };

      wsRef.current.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          
          if (data.alert || data.event) {
            const alertObj = data.alert || data;
            const eventObj = data.event || {};
            const cameraId = getCameraId(alertObj);
            const eventType = getEventType(alertObj);
            const eventId = getAlertKey(alertObj);
            const incidentId = data.id || eventObj.event_id || `inc_${Date.now()}`;

            // Update active alerts by camera
            setAlerts(prev => {
              const current = prev[cameraId];
              if (current) {
                const currentType = getEventType(current);
                const currentId = getAlertKey(current);
                if (currentType === eventType || currentId === eventId) {
                  return prev;
                }
              }
              return { ...prev, [cameraId]: alertObj };
            });

            // Add to incidents
            const incidentObj = {
              id: incidentId,
              event: eventObj,
              alert: alertObj,
              timestamp: eventObj.timestamp || Date.now(),
            };

            setIncidents(prev => {
              const exists = prev.some(inc => 
                inc.event?.event_id === eventObj.event_id || 
                inc.id === incidentId
              );
              if (exists) return prev;
              
              const updated = [incidentObj, ...prev];
              return updated.length > 500 ? updated.slice(0, 500) : updated;
            });

            setAlertCount(c => c + 1);
          }
        } catch (e) {
          console.error('[WS] Parse error:', e.message);
        }
      };

      wsRef.current.onerror = () => {
        console.error('[WS] Error');
        setStatus('error');
      };

      wsRef.current.onclose = () => {
        console.log('[WS] Closed');
        setStatus('disconnected');
        
        // Exponential backoff reconnect
        const delay = Math.min(1000 * Math.pow(2, reconnectAttempts.current), 30000);
        reconnectAttempts.current++;
        
        console.log(`[WS] Reconnecting in ${delay}ms (attempt ${reconnectAttempts.current})`);
        reconnectTimeoutRef.current = setTimeout(connect, delay);
      };
    } catch (e) {
      console.error('[WS] Connection error:', e);
      setStatus('error');
    }
  }, []);

  const dismissAlert = useCallback((cameraId) => {
    setAlerts(prev => {
      const next = { ...prev };
      delete next[cameraId];
      return next;
    });
  }, []);

  const clearIncident = useCallback((incidentId) => {
    setIncidents(prev => prev.filter(inc => inc.id !== incidentId));
  }, []);

  const markResolved = useCallback((incidentId) => {
    setIncidents(prev => prev.map(inc => 
      inc.id === incidentId ? { ...inc, resolved: true } : inc
    ));
  }, []);

  useEffect(() => {
    connect();
    return () => {
      wsRef.current?.close();
      clearTimeout(reconnectTimeoutRef.current);
    };
  }, [connect]);

  return {
    status,
    alerts,
    incidents,
    alertCount,
    dismissAlert,
    clearIncident,
    markResolved,
    setIncidents,
  };
}
