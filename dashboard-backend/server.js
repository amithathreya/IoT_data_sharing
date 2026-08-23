const express = require('express');
const http = require('http');
const { Server } = require('socket.io');
const cors = require('cors');

const app = express();
const server = http.createServer(app);
const io = new Server(server, {
  cors: {
    origin: "*", // allow frontend to connect from anywhere for now
    methods: ["GET", "POST"]
  }
});

app.use(cors());
app.use(express.json());

// In-memory cache to send to newly connected clients
let latestMetrics = {};
let latestTransactions = [];
let xflRounds = [];

app.post('/api/data', (req, res) => {
  const data = req.body;
  
  if (!data.node_id) {
    return res.status(400).json({ error: "Missing node_id" });
  }

  // Update latest metrics for the node
  latestMetrics[data.node_id] = {
    ...latestMetrics[data.node_id],
    ...data
  };

  // Keep a small history of transactions
  if (data.tx_hash) {
    latestTransactions.unshift({
      node_id: data.node_id,
      tx_hash: data.tx_hash,
      payload_hash: data.payload_hash,
      timestamp: data.ts_ns ? parseInt(data.ts_ns) / 1000000 : Date.now()
    });
    // keep only last 10 transactions
    if (latestTransactions.length > 10) {
      latestTransactions.pop();
    }
  }

  // Broadcast to all connected clients
  io.emit('metrics_update', data);

  res.status(200).json({ status: "OK" });
});

app.post('/api/xfl', (req, res) => {
  const data = req.body;
  xflRounds.push(data);
  if (xflRounds.length > 20) xflRounds.shift(); // keep last 20 rounds
  io.emit('xfl_update', data);
  res.status(200).json({ status: "OK" });
});

app.get('/api/history', (req, res) => {
  res.json({
    metrics: latestMetrics,
    transactions: latestTransactions
  });
});

io.on('connection', (socket) => {
  console.log(`[+] Client connected: ${socket.id}`);
  
  // Send initial state
  socket.emit('initial_state', {
    metrics: latestMetrics,
    transactions: latestTransactions,
    xfl_rounds: xflRounds
  });

  socket.on('disconnect', () => {
    console.log(`[-] Client disconnected: ${socket.id}`);
  });
});

const PORT = 4000;
server.listen(PORT, () => {
  console.log(`🚀 Dashboard backend listening on port ${PORT}`);
});
