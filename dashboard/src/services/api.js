const API_BASE_URL = 'http://localhost:8000';
const WS_BASE_URL = 'ws://localhost:8000';

export const fetchHealth = async () => {
  const response = await fetch(`${API_BASE_URL}/health`);
  if (!response.ok) throw new Error('Network response was not ok');
  return response.json();
};

export const fetchMetrics = async (storeId) => {
  const response = await fetch(`${API_BASE_URL}/stores/${storeId}/metrics`);
  if (!response.ok) throw new Error('Network response was not ok');
  return response.json();
};

export const fetchFunnel = async (storeId) => {
  const response = await fetch(`${API_BASE_URL}/stores/${storeId}/funnel`);
  if (!response.ok) throw new Error('Network response was not ok');
  return response.json();
};

export const fetchHeatmap = async (storeId) => {
  const response = await fetch(`${API_BASE_URL}/stores/${storeId}/heatmap`);
  if (!response.ok) throw new Error('Network response was not ok');
  return response.json();
};

export const fetchAnomalies = async (storeId) => {
  const response = await fetch(`${API_BASE_URL}/stores/${storeId}/anomalies`);
  if (!response.ok) throw new Error('Network response was not ok');
  return response.json();
};

export const getWsUrl = (storeId) => {
  return `${WS_BASE_URL}/ws/stores/${storeId}`;
};
