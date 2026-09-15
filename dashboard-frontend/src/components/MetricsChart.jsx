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

  const tooltipStyle = {
    backgroundColor: 'var(--panel-bg)', 
    borderColor: 'var(--panel-border)',
    borderRadius: '8px',
    color: 'var(--text-primary)'
  };

  return (
    <div style={{ width: '100%', display: 'flex', flexDirection: 'column', gap: '32px', marginTop: '20px' }}>
      
      {/* 1. Temperature & Humidity Graph */}
      <div style={{ height: '220px' }}>
        <p style={{ color: 'var(--text-secondary)', fontSize: 12, marginBottom: 8, textTransform: 'uppercase', letterSpacing: '0.5px' }}>
          Climate Telemetry
        </p>
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data} margin={{ top: 5, right: 20, bottom: 5, left: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
            <XAxis dataKey="time" stroke="var(--text-secondary)" />
            <YAxis stroke="var(--text-secondary)" />
            <Tooltip contentStyle={tooltipStyle} itemStyle={{ color: 'var(--text-primary)' }} />
            <Legend />
            <Line type="monotone" dataKey="temperature" name="Temp (°C)" stroke="var(--accent-color)" strokeWidth={3} dot={{ r: 4, strokeWidth: 2 }} activeDot={{ r: 6, stroke: '#fff', strokeWidth: 2 }} />
            <Line type="monotone" dataKey="humidity" name="Humidity (%)" stroke="var(--success-color)" strokeWidth={3} dot={{ r: 4, strokeWidth: 2 }} activeDot={{ r: 6, stroke: '#fff', strokeWidth: 2 }} />
          </LineChart>
        </ResponsiveContainer>
      </div>

      {/* 2. IR Sensor Graph */}
      <div style={{ height: '160px' }}>
        <p style={{ color: 'var(--text-secondary)', fontSize: 12, marginBottom: 8, textTransform: 'uppercase', letterSpacing: '0.5px' }}>
          Infrared Sensor (Obstacle)
        </p>
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data} margin={{ top: 5, right: 20, bottom: 5, left: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
            <XAxis dataKey="time" stroke="var(--text-secondary)" />
            <YAxis domain={[0, 1.2]} ticks={[0, 1]} stroke="var(--text-secondary)" />
            <Tooltip contentStyle={tooltipStyle} itemStyle={{ color: 'var(--text-primary)' }} />
            <Legend />
            <Line type="stepAfter" dataKey="ir" name="IR Sensor (0 = Detected, 1 = Clear)" stroke="#ff9800" strokeWidth={2} dot={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>

      {/* 3. PIR Sensor Graph */}
      <div style={{ height: '160px' }}>
        <p style={{ color: 'var(--text-secondary)', fontSize: 12, marginBottom: 8, textTransform: 'uppercase', letterSpacing: '0.5px' }}>
          PIR Sensor (Motion)
        </p>
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data} margin={{ top: 5, right: 20, bottom: 5, left: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
            <XAxis dataKey="time" stroke="var(--text-secondary)" />
            <YAxis domain={[0, 1.2]} ticks={[0, 1]} stroke="var(--text-secondary)" />
            <Tooltip contentStyle={tooltipStyle} itemStyle={{ color: 'var(--text-primary)' }} />
            <Legend />
            <Line type="stepAfter" dataKey="pir" name="PIR Sensor (1 = Motion, 0 = Still)" stroke="#e91e63" strokeWidth={2} dot={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>

    </div>
  );
}
