// Central API configuration — single source of truth for backend URL
const isDev = window.location.hostname === 'localhost';

export const API_BASE = isDev ? '' : 'https://vaaksetu-x1uf.onrender.com';

export const WS_URL = isDev 
  ? `ws://${window.location.hostname}:8000/ws/dashboard` 
  : `wss://vaaksetu-x1uf.onrender.com/ws/dashboard`;
