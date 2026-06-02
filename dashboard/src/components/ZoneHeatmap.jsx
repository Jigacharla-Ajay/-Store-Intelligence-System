import { ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip, CartesianGrid, Cell } from 'recharts';

const CustomTooltip = ({ active, payload, label }) => {
  if (active && payload && payload.length) {
    const data = payload[0].payload;
    return (
      <div className="simple-box" style={{ padding: '1rem', border: '1px solid #e2e8f0', background: '#fff' }}>
        <p style={{ margin: 0, fontWeight: 600, color: 'var(--primary)' }}>{data.zone_id}</p>
        <div style={{ marginTop: '0.5rem', display: 'flex', flexDirection: 'column', gap: '0.25rem', color: '#475569' }}>
          <span style={{ fontSize: '0.9rem' }}>Visits: <strong style={{ color: '#0f172a' }}>{data.visit_count}</strong></span>
          <span style={{ fontSize: '0.9rem' }}>Visit Score: <strong style={{ color: '#0f172a' }}>{data.visit_score.toFixed(1)}/100</strong></span>
          <span style={{ fontSize: '0.9rem' }}>Dwell Score: <strong style={{ color: '#0f172a' }}>{data.dwell_score.toFixed(1)}/100</strong></span>
        </div>
      </div>
    );
  }
  return null;
};

const ZoneHeatmap = ({ heatmapData }) => {
  if (!heatmapData || !heatmapData.zones) return null;

  // We use visit_score to determine color intensity
  const getColor = (score) => {
    if (score > 80) return '#c92a8b'; // High intensity (primary)
    if (score > 50) return '#e879f9'; // Medium (secondary)
    if (score > 20) return '#fbcfe8'; // Low (light pink)
    return '#f1f5f9'; // Very low (light gray)
  };

  return (
    <div className="simple-box" style={{ padding: '1.5rem', flex: 1, display: 'flex', flexDirection: 'column' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem' }}>
        <h2 style={{ fontSize: '1.1rem', fontWeight: 600, margin: 0, color: 'var(--text-main)' }}>
          Zone Activity Heatmap
        </h2>
        {heatmapData.confidence_flag === 'LOW' && (
          <span style={{ fontSize: '0.75rem', padding: '0.25rem 0.5rem', background: 'var(--status-warn)', color: '#000', borderRadius: '4px', fontWeight: 600 }}>
            LOW CONFIDENCE
          </span>
        )}
      </div>
      
      <div style={{ flex: 1, minHeight: '300px' }}>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={heatmapData.zones} layout="vertical" margin={{ top: 0, right: 30, left: 20, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" horizontal={false} />
            <XAxis 
              type="number" 
              domain={[0, 100]} 
              stroke="#64748b" 
              tick={{ fill: '#64748b', fontSize: 12 }}
              tickLine={false}
              axisLine={false}
            />
            <YAxis 
              dataKey="zone_id" 
              type="category" 
              stroke="#64748b" 
              tick={{ fill: '#64748b', fontSize: 11 }}
              tickLine={false}
              axisLine={false}
              width={80}
            />
            <Tooltip content={<CustomTooltip />} cursor={{ fill: '#f8fafc' }} />
            <Bar dataKey="visit_score" radius={[0, 4, 4, 0]} barSize={24}>
              {heatmapData.zones.map((entry, index) => (
                <Cell key={`cell-${index}`} fill={getColor(entry.visit_score)} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
};

export default ZoneHeatmap;
