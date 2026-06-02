import { useState, useEffect, useRef } from 'react';
import { fetchMetrics, fetchFunnel, fetchHeatmap, fetchAnomalies, getWsUrl } from '../services/api';

export const useStoreData = (storeId) => {
  const [data, setData] = useState({
    metrics: null,
    funnel: null,
    heatmap: null,
    anomalies: null,
  });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [isConnected, setIsConnected] = useState(false);
  const wsRef = useRef(null);

  // Initial Data Fetch
  useEffect(() => {
    let mounted = true;
    
    const loadData = async () => {
      try {
        setLoading(true);
        const [metricsData, funnelData, heatmapData, anomaliesData] = await Promise.all([
          fetchMetrics(storeId),
          fetchFunnel(storeId),
          fetchHeatmap(storeId),
          fetchAnomalies(storeId)
        ]);
        
        if (mounted) {
          setData({
            metrics: metricsData,
            funnel: funnelData,
            heatmap: heatmapData,
            anomalies: anomaliesData,
          });
          setError(null);
        }
      } catch (err) {
        if (mounted) setError(err.message);
      } finally {
        if (mounted) setLoading(false);
      }
    };
    
    loadData();
    
    return () => {
      mounted = false;
    };
  }, [storeId]);

  // WebSocket Connection
  useEffect(() => {
    let reconnectTimeout;
    let pingInterval;
    
    const connectWs = () => {
      const ws = new WebSocket(getWsUrl(storeId));
      wsRef.current = ws;
      
      ws.onopen = () => {
        setIsConnected(true);
        // Setup ping
        pingInterval = setInterval(() => {
          if (ws.readyState === WebSocket.OPEN) {
            ws.send('ping');
          }
        }, 30000);
      };
      
      ws.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data);
          
          if (msg.type === 'EVENT') {
            // Handle raw event if needed, or rely on metric updates
            console.log('Live Event:', msg.data);
          } 
          else if (msg.type === 'METRICS_UPDATE') {
            setData(prev => ({ ...prev, metrics: msg.data }));
          }
          else if (msg.type === 'ANOMALY') {
            setData(prev => {
              // Add new anomaly to the list
              const currentAnomalies = prev.anomalies?.active_anomalies || [];
              const exists = currentAnomalies.find(a => a.anomaly_id === msg.data.anomaly_id);
              
              if (exists) return prev; // Already have this anomaly
              
              return {
                ...prev,
                anomalies: {
                  ...prev.anomalies,
                  active_anomalies: [msg.data, ...currentAnomalies],
                  anomaly_count: (prev.anomalies?.anomaly_count || 0) + 1
                }
              };
            });
          }
        } catch (e) {
          console.error('Error parsing WS message', e);
        }
      };
      
      ws.onclose = () => {
        setIsConnected(false);
        clearInterval(pingInterval);
        // Auto-reconnect after 3 seconds
        reconnectTimeout = setTimeout(connectWs, 3000);
      };
      
      ws.onerror = (err) => {
        console.error('WebSocket Error:', err);
      };
    };
    
    connectWs();
    
    return () => {
      clearInterval(pingInterval);
      clearTimeout(reconnectTimeout);
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, [storeId]);

  // Expose a manual refresh function
  const refreshData = async () => {
    try {
      const [metricsData, funnelData, heatmapData, anomaliesData] = await Promise.all([
        fetchMetrics(storeId),
        fetchFunnel(storeId),
        fetchHeatmap(storeId),
        fetchAnomalies(storeId)
      ]);
      
      setData({
        metrics: metricsData,
        funnel: funnelData,
        heatmap: heatmapData,
        anomalies: anomaliesData,
      });
      setError(null);
    } catch (err) {
      setError(err.message);
    }
  };

  return { data, loading, error, isConnected, refreshData };
};
