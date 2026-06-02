import { AlertCircle, Info, AlertTriangle } from 'lucide-react';
import clsx from 'clsx';

const SeverityIcon = ({ severity }) => {
  switch (severity) {
    case 'CRITICAL':
      return <AlertCircle size={18} color="var(--status-critical)" />;
    case 'WARN':
      return <AlertTriangle size={18} color="var(--status-warn)" />;
    case 'INFO':
    default:
      return <Info size={18} color="var(--status-info)" />;
  }
};

const AnomalyFeed = ({ anomaliesData }) => {
  if (!anomaliesData || !anomaliesData.active_anomalies) return null;
  
  const { active_anomalies, anomaly_count } = anomaliesData;

  return (
    <div className="simple-box" style={{ padding: '1.5rem', display: 'flex', flexDirection: 'column', height: '100%' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem' }}>
        <h2 style={{ fontSize: '1.1rem', fontWeight: 600, margin: 0, color: 'var(--text-main)' }}>
          Live Anomalies
        </h2>
        <div style={{ padding: '0.25rem 0.6rem', background: anomaly_count > 0 ? '#fee2e2' : '#f1f5f9', borderRadius: '12px', fontSize: '0.8rem', color: anomaly_count > 0 ? 'var(--status-critical)' : 'var(--text-muted)', fontWeight: 600 }}>
          {anomaly_count} Active
        </div>
      </div>
      
      <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem', overflowY: 'auto', flex: 1 }}>
        {active_anomalies.length === 0 ? (
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: 'var(--text-muted)', fontSize: '0.9rem' }}>
            No anomalies detected. Store operating normally.
          </div>
        ) : (
          active_anomalies.map((anomaly) => (
            <div 
              key={anomaly.anomaly_id}
              style={{
                padding: '1rem',
                borderRadius: '8px',
                background: '#f8fafc',
                border: '1px solid #e2e8f0',
                borderLeft: `4px solid var(--status-${anomaly.severity.toLowerCase()})`,
                display: 'flex',
                flexDirection: 'column',
                gap: '0.5rem'
              }}
            >
              <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
                <SeverityIcon severity={anomaly.severity} />
                <span style={{ fontWeight: 600, fontSize: '0.9rem' }}>{anomaly.type.replace(/_/g, ' ')}</span>
                <span style={{ marginLeft: 'auto', fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                  {new Date(anomaly.detected_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                </span>
              </div>
              <p style={{ margin: 0, fontSize: '0.85rem', color: 'var(--text-muted)' }}>
                {anomaly.description}
              </p>
              {anomaly.suggested_action && (
                <div style={{ marginTop: '0.25rem', padding: '0.5rem', background: '#fff', border: '1px solid #e2e8f0', borderRadius: '4px', fontSize: '0.8rem', color: 'var(--text-main)' }}>
                  <strong>Action:</strong> {anomaly.suggested_action}
                </div>
              )}
            </div>
          ))
        )}
      </div>
    </div>
  );
};

export default AnomalyFeed;
