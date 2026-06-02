import { useStoreData } from './hooks/useStoreData';
import Header from './components/Header';
import MetricsGrid from './components/MetricsGrid';
import FunnelChart from './components/FunnelChart';
import ZoneHeatmap from './components/ZoneHeatmap';
import AnomalyFeed from './components/AnomalyFeed';

const STORE_ID = 'STORE_BLR_002'; // Default store for demo

function App() {
  const { data, loading, error, isConnected, refreshData } = useStoreData(STORE_ID);

  if (loading && !data.metrics) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh', flexDirection: 'column', gap: '1rem' }}>
        <div className="status-indicator" style={{ width: '20px', height: '20px' }}></div>
        <div style={{ color: 'var(--primary)', fontWeight: 600 }}>Loading Store Intelligence...</div>
      </div>
    );
  }

  if (error && !data.metrics) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh', flexDirection: 'column', gap: '1rem' }}>
        <div style={{ color: 'var(--status-critical)' }}>Failed to load data: {error}</div>
        <button onClick={refreshData} style={{ padding: '0.5rem 1rem', background: 'var(--primary)', color: 'white', border: 'none', borderRadius: '4px', cursor: 'pointer' }}>
          Retry
        </button>
      </div>
    );
  }

  return (
    <div className="dashboard-layout">
      <Header storeId={STORE_ID} isConnected={isConnected} onRefresh={refreshData} />
      
      <MetricsGrid metrics={data.metrics} />
      
      <div className="main-content">
        <div className="left-column">
          <div style={{ display: 'flex', gap: '1.5rem', minHeight: '350px' }}>
            <FunnelChart funnelData={data.funnel} />
            <ZoneHeatmap heatmapData={data.heatmap} />
          </div>
        </div>
        
        <div className="right-column">
          <AnomalyFeed anomaliesData={data.anomalies} />
        </div>
      </div>
    </div>
  );
}

export default App;
