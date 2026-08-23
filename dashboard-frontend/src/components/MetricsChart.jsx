import React from 'react';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend
} from 'recharts';

export default function MetricsChart({ data }) {
  if (!data || data.length === 0) {
    return (
      <div style={{ height: '300px', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--text-secondary)' }}>
        Waiting for telemetry data...
      </div>
    );
  }

  return (
    <div style={{ width: '100%', height: '300px', marginTop: '20px' }}>
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ top: 5, right: 20, bottom: 5, left: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
          <XAxis dataKey="time" stroke="var(--text-secondary)" />
          <YAxis stroke="var(--text-secondary)" />
          <Tooltip 
            contentStyle={{ 
              backgroundColor: 'var(--panel-bg)', 
              borderColor: 'var(--panel-border)',
              borderRadius: '8px',
              color: 'var(--text-primary)'
            }} 
            itemStyle={{ color: 'var(--text-primary)' }}
          />
          <Legend />
          <Line 
            type="monotone" 
            dataKey="temperature" 
            name="Temperature (°C)" 
            stroke="var(--accent-color)" 
            strokeWidth={3}
            dot={{ r: 4, strokeWidth: 2 }}
            activeDot={{ r: 6, stroke: '#fff', strokeWidth: 2 }}
          />
          <Line 
            type="monotone" 
            dataKey="humidity" 
            name="Humidity (%)" 
            stroke="var(--success-color)" 
            strokeWidth={3}
            dot={{ r: 4, strokeWidth: 2 }}
            activeDot={{ r: 6, stroke: '#fff', strokeWidth: 2 }}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
