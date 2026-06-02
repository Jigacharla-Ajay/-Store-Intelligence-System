import { Users, LogIn, TrendingUp, Clock, AlertTriangle } from 'lucide-react';

const MetricCard = ({ title, value, icon: Icon, color, subvalue }) => (
  <div className="simple-box" style={{ padding: '1.5rem', display: 'flex', flexDirection: 'column', gap: '1rem' }}>
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
      <span style={{ color: 'var(--text-muted)', fontSize: '0.9rem', fontWeight: 500 }}>{title}</span>
      <div style={{ padding: '0.5rem', borderRadius: '12px', background: `${color}15`, color: color }}>
        <Icon size={20} />
      </div>
    </div>
    <div>
      <div style={{ fontSize: '2rem', fontWeight: 700, lineHeight: 1 }}>{value}</div>
      {subvalue && <div style={{ fontSize: '0.85rem', color: 'var(--text-muted)', marginTop: '0.5rem' }}>{subvalue}</div>}
    </div>
  </div>
);

const MetricsGrid = ({ metrics }) => {
  if (!metrics) return null;
  
  const { visitors, conversion, dwell, abandonment } = metrics;
  
  // Format dwell time from ms to minutes
  const formatDwell = (ms) => {
    if (!ms) return '0m';
    const minutes = Math.floor(ms / 60000);
    return `${minutes}m`;
  };

  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '1.5rem' }}>
      <MetricCard 
        title="Unique Visitors" 
        value={visitors.unique_count || 0} 
        subvalue={`${visitors.total_entries || 0} total entries`}
        icon={Users} 
        color="var(--primary)" 
      />
      <MetricCard 
        title="Conversion Rate" 
        value={`${(conversion.rate * 100).toFixed(1)}%`} 
        subvalue={`${conversion.converted_visitors || 0} purchases`}
        icon={TrendingUp} 
        color="var(--status-success)" 
      />
      <MetricCard 
        title="Avg Dwell Time" 
        value={formatDwell(dwell.avg_total_ms)} 
        icon={Clock} 
        color="var(--status-info)" 
      />
      <MetricCard 
        title="Queue Abandonment" 
        value={`${(abandonment.rate * 100).toFixed(1)}%`} 
        subvalue={`${abandonment.abandoned_count || 0} dropped`}
        icon={AlertTriangle} 
        color={abandonment.rate > 0.3 ? 'var(--status-critical)' : 'var(--status-warn)'} 
      />
    </div>
  );
};

export default MetricsGrid;
