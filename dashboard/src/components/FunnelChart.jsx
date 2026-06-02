import { ResponsiveContainer, AreaChart, Area, XAxis, YAxis, Tooltip, CartesianGrid } from 'recharts';

const CustomTooltip = ({ active, payload, label }) => {
  if (active && payload && payload.length) {
    const data = payload[0].payload;
    return (
      <div className="simple-box" style={{ padding: '1rem', border: '1px solid #e2e8f0', background: '#fff' }}>
        <p style={{ margin: 0, fontWeight: 600, color: 'var(--primary)' }}>{data.stage.replace('_', ' ')}</p>
        <div style={{ marginTop: '0.5rem', display: 'flex', flexDirection: 'column', gap: '0.25rem', color: '#475569' }}>
          <span style={{ fontSize: '0.9rem' }}>Sessions: <strong style={{ color: '#0f172a' }}>{data.sessions}</strong></span>
          <span style={{ fontSize: '0.9rem' }}>Drop-off: <strong style={{ color: '#0f172a' }}>{(data.dropoff_pct * 100).toFixed(1)}%</strong></span>
        </div>
      </div>
    );
  }
  return null;
};

const FunnelChart = ({ funnelData }) => {
  if (!funnelData || !funnelData.funnel) return null;

  // Format data for Recharts AreaChart (which we use to look like a funnel)
  const data = funnelData.funnel.map(stage => ({
    ...stage,
    displayStage: stage.stage.split('_').join('\n'),
  }));

  return (
    <div className="simple-box" style={{ padding: '1.5rem', flex: 1, display: 'flex', flexDirection: 'column' }}>
      <h2 style={{ fontSize: '1.1rem', fontWeight: 600, marginBottom: '1.5rem', color: 'var(--text-main)' }}>
        Conversion Funnel
      </h2>
      
      <div style={{ flex: 1, minHeight: '300px' }}>
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={data} margin={{ top: 10, right: 30, left: 0, bottom: 0 }}>
            <defs>
              <linearGradient id="colorSessions" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="var(--primary)" stopOpacity={0.4}/>
                <stop offset="95%" stopColor="var(--secondary)" stopOpacity={0.05}/>
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" vertical={false} />
            <XAxis 
              dataKey="displayStage" 
              stroke="#64748b" 
              tick={{ fill: '#64748b', fontSize: 12 }}
              tickLine={false}
              axisLine={false}
              dy={10}
            />
            <YAxis 
              stroke="#64748b" 
              tick={{ fill: '#64748b', fontSize: 12 }}
              tickLine={false}
              axisLine={false}
            />
            <Tooltip content={<CustomTooltip />} />
            <Area 
              type="monotone" 
              dataKey="sessions" 
              stroke="var(--primary)" 
              strokeWidth={3}
              fillOpacity={1} 
              fill="url(#colorSessions)" 
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
};

export default FunnelChart;
