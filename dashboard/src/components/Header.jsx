import { Clock, Activity } from 'lucide-react';
import { useEffect, useState } from 'react';
import clsx from 'clsx';

const Header = ({ storeId, isConnected, onRefresh }) => {
  const [time, setTime] = useState(new Date());

  useEffect(() => {
    const timer = setInterval(() => setTime(new Date()), 1000);
    return () => clearInterval(timer);
  }, []);

  return (
    <header className="simple-box" style={{ padding: '1rem 1.5rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
        <h1 style={{ fontSize: '1.5rem', fontWeight: 700, margin: 0, color: 'var(--primary)' }}>
          Purplle <span style={{ color: 'var(--text-main)', fontWeight: 500 }}>Store Intelligence</span>
        </h1>
        <div style={{ padding: '0.25rem 0.75rem', background: '#f1f5f9', border: '1px solid #e2e8f0', color: '#475569', borderRadius: '20px', fontSize: '0.875rem' }}>
          {storeId}
        </div>
      </div>
      
      <div style={{ display: 'flex', alignItems: 'center', gap: '1.5rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.9rem', color: 'var(--text-muted)' }}>
          <Clock size={16} />
          {time.toLocaleTimeString()}
        </div>
        
        <div 
          onClick={onRefresh}
          style={{ 
            display: 'flex', alignItems: 'center', gap: '0.5rem', 
            cursor: 'pointer', padding: '0.25rem 0.75rem',
            background: isConnected ? 'rgba(34, 197, 94, 0.1)' : 'rgba(239, 68, 68, 0.1)',
            borderRadius: '20px', fontSize: '0.875rem',
            border: `1px solid ${isConnected ? 'rgba(34, 197, 94, 0.2)' : 'rgba(239, 68, 68, 0.2)'}`
          }}
        >
          <div className={clsx('status-indicator', { 'offline': !isConnected })} />
          <span style={{ color: isConnected ? 'var(--status-success)' : 'var(--status-critical)' }}>
            {isConnected ? 'Live' : 'Disconnected'}
          </span>
        </div>
      </div>
    </header>
  );
};

export default Header;
