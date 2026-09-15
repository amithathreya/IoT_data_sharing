import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.jsx'
import LiveAudioPlayer from './components/LiveAudioPlayer.jsx'

const path = window.location.pathname;

createRoot(document.getElementById('root')).render(
  <StrictMode>
    {path === '/audio' ? <LiveAudioPlayer /> : <App />}
  </StrictMode>,
)
