// live.js — standalone fetch logic if needed outside live.html
const LIVE_API = 'http://127.0.0.1:8000/api/live';

async function getLiveData() {
  const res = await fetch(LIVE_API);
  return res.json();
}

export { getLiveData };