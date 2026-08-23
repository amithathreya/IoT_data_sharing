import React from 'react';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
  BarChart,
  Bar
} from 'recharts';

const CustomTooltip = ({ active, payload, label }) => {
  if (active && payload && payload.length) {
    return (
      <div style={{
        backgroundColor: 'rgba(15, 15, 25, 0.95)',
        border: '1px solid var(--panel-border)',
        borderRadius: '8px',
        padding: '10px 14px',
        backdropFilter: 'blur(12px)'
      }}>
        <p style={{ color: 'var(--text-secondary)', marginBottom: 6, fontSize: 12 }}>Round {label}</p>
        {payload.map(p => (
          <p key={p.name} style={{ color: p.color, fontSize: 13, marginBottom: 2 }}>
            {p.name}: <strong>{typeof p.value === 'number' ? p.value.toFixed(5) : p.value}</strong>
          </p>
        ))}
      </div>
    );
  }
  return null;
};

const BarTooltip = ({ active, payload, label }) => {
  if (active && payload && payload.length) {
    return (
      <div style={{
        backgroundColor: 'rgba(15, 15, 25, 0.95)',
        border: '1px solid var(--panel-border)',
        borderRadius: '8px',
        padding: '10px 14px',
      }}>
        <p style={{ color: 'var(--text-secondary)', marginBottom: 6, fontSize: 12 }}>Round {label}</p>
        {payload.map(p => (
          <p key={p.name} style={{ color: p.color, fontSize: 13, marginBottom: 2 }}>
            {p.name}: <strong>{p.value}</strong>
          </p>
        ))}
      </div>
    );
  }
  return null;
};

export default function XFLPanel({ rounds }) {
  if (!rounds || rounds.length === 0) {
    return (
      <div style={{
        height: '280px',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        color: 'var(--text-secondary)',
        gap: 12
      }}>
        <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" opacity="0.4">
          <circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/>
        </svg>
        <p style={{ fontSize: 14 }}>Waiting for the first XFL aggregation round...</p>
      </div>
    );
  }

  const latest = rounds[rounds.length - 1];
  const prev = rounds.length > 1 ? rounds[rounds.length - 2] : null;
  const lossDelta = prev ? (latest.avg_reconstruction_loss - prev.avg_reconstruction_loss) : null;

  const statCards = [
    {
      label: 'Current Round',
      value: latest.round,
    },
    {
      label: 'Clients in Round',
      value: latest.num_clients,
    },
    {
      label: 'Avg Reconstruction Loss',
      value: latest.avg_reconstruction_loss?.toFixed(5),
      color: lossDelta !== null ? (lossDelta < 0 ? '#10b981' : '#f59e0b') : undefined,
      sub: lossDelta !== null ? `${lossDelta > 0 ? '▲' : '▼'} ${Math.abs(lossDelta).toFixed(5)} vs last` : null,
    },
    {
      label: 'Avg Dynamic Threshold',
      value: latest.avg_dynamic_threshold?.toFixed(5),
    },
    {
      label: 'Samples Gated (Anomalous)',
      value: latest.total_gated_anomalies,
      color: latest.total_gated_anomalies > 0 ? '#ef4444' : '#10b981',
    },
    {
      label: 'Gating Rate',
      value: `${latest.gating_rate_pct}%`,
      color: latest.gating_rate_pct > 40 ? '#ef4444' : latest.gating_rate_pct > 20 ? '#f59e0b' : '#10b981',
    },
  ];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 28 }}>
      {/* Stat Cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: 12 }}>
        {statCards.map(card => (
          <div key={card.label} style={{
            background: 'rgba(255,255,255,0.03)',
            border: '1px solid var(--panel-border)',
            borderRadius: 10,
            padding: '14px 16px',
          }}>
            <p style={{ color: 'var(--text-secondary)', fontSize: 11, textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: 6 }}>
              {card.label}
            </p>
            <p style={{ fontSize: 20, fontWeight: 700, color: card.color || 'var(--text-primary)', fontFamily: "'JetBrains Mono', monospace" }}>
              {card.value ?? '—'}
            </p>
            {card.sub && <p style={{ fontSize: 11, color: card.color, marginTop: 4 }}>{card.sub}</p>}
          </div>
        ))}
      </div>

      {/* Two charts side by side */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 24 }}>
        {/* Loss vs Threshold Convergence Chart */}
        <div>
          <p style={{ color: 'var(--text-secondary)', fontSize: 12, marginBottom: 12, textTransform: 'uppercase', letterSpacing: '0.5px' }}>
            Reconstruction Loss vs Anomaly Threshold per Round
          </p>
          <div style={{ width: '100%', height: 220 }}>
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={rounds} margin={{ top: 5, right: 20, bottom: 5, left: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                <XAxis dataKey="round" stroke="var(--text-secondary)" />
                <YAxis stroke="var(--text-secondary)" width={75} tickFormatter={v => v.toFixed(4)} />
                <Tooltip content={<CustomTooltip />} />
                <Legend wrapperStyle={{ color: 'var(--text-secondary)', fontSize: 12 }} />
                <Line
                  type="monotone"
                  dataKey="avg_reconstruction_loss"
                  name="Avg Reconstruction Loss"
                  stroke="#818cf8"
                  strokeWidth={2.5}
                  dot={{ r: 4, fill: '#818cf8' }}
                  activeDot={{ r: 6, stroke: '#fff', strokeWidth: 2 }}
                  connectNulls
                />
                <Line
                  type="monotone"
                  dataKey="avg_dynamic_threshold"
                  name="Avg Dynamic Threshold"
                  stroke="#f59e0b"
                  strokeWidth={2}
                  strokeDasharray="5 4"
                  dot={false}
                  connectNulls
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Gated Anomalies per Round Bar Chart */}
        <div>
          <p style={{ color: 'var(--text-secondary)', fontSize: 12, marginBottom: 12, textTransform: 'uppercase', letterSpacing: '0.5px' }}>
            Loss-Gated Anomalies per Round (Backprop Frozen Samples)
          </p>
          <div style={{ width: '100%', height: 220 }}>
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={rounds} margin={{ top: 5, right: 20, bottom: 5, left: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                <XAxis dataKey="round" stroke="var(--text-secondary)" />
                <YAxis stroke="var(--text-secondary)" allowDecimals={false} />
                <Tooltip content={<BarTooltip />} />
                <Legend wrapperStyle={{ color: 'var(--text-secondary)', fontSize: 12 }} />
                <Bar dataKey="total_trained_samples" name="Clean Samples Trained" fill="rgba(16, 185, 129, 0.6)" radius={[4, 4, 0, 0]} />
                <Bar dataKey="total_gated_anomalies" name="Gated (Anomalous)" fill="rgba(239, 68, 68, 0.7)" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>
    </div>
  );
}
