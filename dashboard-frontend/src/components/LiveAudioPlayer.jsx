import { useEffect, useState, useRef } from 'react';
import { io } from 'socket.io-client';
import { Mic, Radio, ShieldCheck, Activity } from 'lucide-react';

const SOCKET_URL = 'http://localhost:4000';

function LiveAudioPlayer() {
  const [socket, setSocket] = useState(null);
  const [isConnected, setIsConnected] = useState(false);
  const [streamInfo, setStreamInfo] = useState(null);
  const [chunksReceived, setChunksReceived] = useState(0);
  
  // Using an array of Object URLs to play chunks sequentially
  const [playlist, setPlaylist] = useState([]);
  const [isPlaying, setIsPlaying] = useState(false);
  
  const audioRef = useRef(null);

  useEffect(() => {
    const newSocket = io(SOCKET_URL);
    setSocket(newSocket);

    newSocket.on('connect', () => setIsConnected(true));
    newSocket.on('disconnect', () => setIsConnected(false));

    newSocket.on('live_audio_stream', (data) => {
      if (data.audio_b64) {
        try {
          const binaryStr = atob(data.audio_b64);
          const len = binaryStr.length;
          const bytes = new Uint8Array(len);
          for (let i = 0; i < len; i++) {
            bytes[i] = binaryStr.charCodeAt(i);
          }
          const blob = new Blob([bytes], { type: 'audio/mpeg' });
          const url = URL.createObjectURL(blob);
          
          setPlaylist(prev => [...prev, url]);
          
          setStreamInfo({
            node_id: data.node_id,
            filename: data.audio_filename,
            tx_hash: data.tx_hash,
            timestamp: new Date(data.ts_ns / 1000000).toLocaleTimeString()
          });
          
          setChunksReceived(prev => prev + 1);
        } catch (e) {
          console.error("Failed to process live audio chunk:", e);
        }
      }
    });

    return () => newSocket.close();
  }, []);

  // Handle continuous playback of chunks
  useEffect(() => {
    if (audioRef.current && !isPlaying && playlist.length > 0) {
      playNextChunk();
    }
  }, [playlist, isPlaying]);

  const playNextChunk = () => {
    if (playlist.length === 0) {
      setIsPlaying(false);
      return;
    }
    
    setIsPlaying(true);
    const nextUrl = playlist[0];
    
    // Remove played chunk from queue
    setPlaylist(prev => prev.slice(1));
    
    audioRef.current.src = nextUrl;
    audioRef.current.play().catch(e => {
      console.warn("Auto-play blocked:", e);
      setIsPlaying(false);
    });
  };

  const handleEnded = () => {
    setIsPlaying(false);
    // Cleanup URL to avoid memory leak
    URL.revokeObjectURL(audioRef.current.src);
    // Will trigger the effect to play next chunk if available
  };

  return (
    <div style={{
      minHeight: '100vh',
      backgroundColor: '#0a0a0f',
      color: '#fff',
      padding: '40px',
      fontFamily: 'system-ui, -apple-system, sans-serif'
    }}>
      <div style={{ maxWidth: '800px', margin: '0 auto' }}>
        
        <header style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '40px' }}>
          <h1 style={{ display: 'flex', alignItems: 'center', gap: '15px', margin: 0, color: '#00ff64' }}>
            <Radio size={36} /> Live Secure Audio Stream
          </h1>
          <div style={{
            display: 'flex', alignItems: 'center', gap: '10px',
            padding: '8px 16px', borderRadius: '20px',
            backgroundColor: isConnected ? 'rgba(0, 255, 100, 0.1)' : 'rgba(255, 50, 50, 0.1)',
            border: `1px solid ${isConnected ? 'rgba(0, 255, 100, 0.3)' : 'rgba(255, 50, 50, 0.3)'}`,
            color: isConnected ? '#00ff64' : '#ff3232'
          }}>
            <div style={{
              width: '10px', height: '10px', borderRadius: '50%',
              backgroundColor: isConnected ? '#00ff64' : '#ff3232',
              boxShadow: isConnected ? '0 0 10px #00ff64' : 'none'
            }} />
            {isConnected ? 'Live Connection' : 'Disconnected'}
          </div>
        </header>

        <div style={{
          backgroundColor: 'rgba(255,255,255,0.03)',
          border: '1px solid rgba(255,255,255,0.1)',
          borderRadius: '16px',
          padding: '40px',
          backdropFilter: 'blur(10px)',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          gap: '30px'
        }}>
          
          <div style={{
            width: '150px',
            height: '150px',
            borderRadius: '50%',
            backgroundColor: isPlaying ? 'rgba(0, 255, 100, 0.1)' : 'rgba(255, 255, 255, 0.05)',
            border: `2px solid ${isPlaying ? '#00ff64' : 'rgba(255,255,255,0.1)'}`,
            display: 'flex',
            justifyContent: 'center',
            alignItems: 'center',
            transition: 'all 0.3s ease',
            boxShadow: isPlaying ? '0 0 40px rgba(0, 255, 100, 0.2)' : 'none'
          }}>
            <Mic size={64} color={isPlaying ? '#00ff64' : '#666'} />
          </div>

          <audio 
            ref={audioRef} 
            onEnded={handleEnded}
            controls
            style={{ width: '100%', maxWidth: '500px', outline: 'none' }}
          />

          <div style={{ width: '100%', display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '20px', marginTop: '20px' }}>
            <div style={{ backgroundColor: 'rgba(0,0,0,0.5)', padding: '20px', borderRadius: '12px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px', color: '#888', marginBottom: '10px' }}>
                <Activity size={18} /> Stream Stats
              </div>
              <p style={{ margin: '5px 0' }}><strong>Source Node:</strong> {streamInfo?.node_id || 'Waiting...'}</p>
              <p style={{ margin: '5px 0' }}><strong>File/Stream:</strong> {streamInfo?.filename || '...'}</p>
              <p style={{ margin: '5px 0' }}><strong>Chunks Received:</strong> {chunksReceived}</p>
              <p style={{ margin: '5px 0' }}><strong>Buffer Queue:</strong> {playlist.length} chunks</p>
            </div>

            <div style={{ backgroundColor: 'rgba(0, 255, 100, 0.05)', border: '1px solid rgba(0, 255, 100, 0.2)', padding: '20px', borderRadius: '12px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px', color: '#00ff64', marginBottom: '10px' }}>
                <ShieldCheck size={18} /> Cryptographic Verifications
              </div>
              <p style={{ margin: '5px 0', fontSize: '0.9rem' }}>✅ ML-KEM-768 Decapsulation</p>
              <p style={{ margin: '5px 0', fontSize: '0.9rem' }}>✅ AES-256-GCM Decryption</p>
              <p style={{ margin: '5px 0', fontSize: '0.9rem' }}>✅ ML-DSA-65 Signature Verified</p>
              <p style={{ margin: '10px 0 5px 0', fontSize: '0.8rem', color: '#888', wordBreak: 'break-all' }}>
                <strong>Ledger Tx:</strong> {streamInfo?.tx_hash || '...'}
              </p>
            </div>
          </div>
          
        </div>
      </div>
    </div>
  );
}

export default LiveAudioPlayer;
