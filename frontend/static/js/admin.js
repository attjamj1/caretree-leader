const API = '/api/admin';
const API_KEY = 'change-this-to-a-secret-key'; // match your .env
const HEADERS = { 'Content-Type': 'application/json', 'x-api-key': API_KEY };

let activeProject = null;
let editingStationId = null;
let editingStationIdx = null;

// ─── Init ──────────────────────────────────────────────────────────────────

window.onload = () => {
  loadProjects();
};

// ─── API helpers ───────────────────────────────────────────────────────────

async function api(method, path, body = null) {
  const res = await fetch(`${API}${path}`, {
    method,
    headers: HEADERS,
    body: body ? JSON.stringify(body) : null,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    alert(`Error: ${err.detail || res.statusText}`);
    throw new Error(err.detail || res.statusText);
  }
  return res.json();
}

// ─── Projects ──────────────────────────────────────────────────────────────

async function loadProjects() {
  const projects = await api('GET', '/projects');
  renderSidebar(projects);
  if (projects.length) selectProject(projects[0].id);
}

function renderSidebar(projects) {
  const list = document.getElementById('proj-list');
  list.innerHTML = projects.map(p => `
    <div class="proj-item ${activeProject?.id === p.id ? 'active' : ''}"
         onclick="selectProject('${p.id}')">
      <span class="proj-item-name">${p.name}</span>
      <span class="proj-badge ${p.status}">${p.status}</span>
    </div>
  `).join('');
}

async function selectProject(id) {
  const p = await api('GET', `/projects/${id}`);
  activeProject = p;
  renderSidebar(await api('GET', '/projects'));
  renderTopbar(p);
  renderContent(p);
}

function renderTopbar(p) {
  document.getElementById('main-title').textContent = p.name;
  document.getElementById('main-sub').textContent =
    `${p.org} · ${p.event_date} · ${p.team_count || p.teams?.length || 0} teams`;

  const badge = document.getElementById('race-badge');
  badge.style.display = '';
  badge.className = `badge badge-${p.status}`;
  badge.textContent = p.status === 'live' ? 'Race live'
    : p.status === 'done' ? 'Completed' : 'Draft';

  document.getElementById('start-btn').style.display = '';
  document.getElementById('start-label').textContent =
    p.status === 'live' ? 'End race' : 'Start race';
  document.getElementById('start-btn').className =
    `btn btn-sm ${p.status === 'live' ? 'btn-red' : 'btn-green'}`;
  document.getElementById('live-btn').style.display = '';
}

async function createProject() {
  const name = document.getElementById('np-name').value.trim();
  if (!name) { alert('Please enter a project name'); return; }

  await api('POST', '/projects', {
    name,
    org: document.getElementById('np-org').value.trim(),
    event_date: document.getElementById('np-date').value.trim(),
    team_count: parseInt(document.getElementById('np-teams').value) || 4,
  });

  closeModal('modal-newproj');
  ['np-name','np-org','np-date'].forEach(id => document.getElementById(id).value = '');
  await loadProjects();
}

async function toggleRace() {
  if (!activeProject) return;
  if (activeProject.status === 'live') {
    if (!confirm('End the race for all teams?')) return;
    await api('POST', `/projects/${activeProject.id}/end`);
  } else {
    if (!confirm('Start the race? Missions will be sent to all teams immediately.')) return;
    await api('POST', `/projects/${activeProject.id}/start`);
  }
  await selectProject(activeProject.id);
}

function openLive() {
  window.open('../templates/live.html', '_blank');
}

// ─── Main content ──────────────────────────────────────────────────────────

function renderContent(p) {
  document.getElementById('main-content').innerHTML = `
    <div class="tab-bar">
      <button class="tab-btn active" onclick="showTab('overview', this)">Overview</button>
      <button class="tab-btn" onclick="showTab('stations', this)">Stations</button>
      <button class="tab-btn" onclick="showTab('routes', this)">Routes</button>
      <button class="tab-btn" onclick="showTab('teams', this)">Teams</button>
      <button class="tab-btn" onclick="showTab('scoring', this)">Scoring</button>
      <button class="tab-btn" onclick="showTab('logs', this)">Activity log</button>
    </div>
    <div id="tab-overview" class="tab-pane active">${renderOverview(p)}</div>
    <div id="tab-stations" class="tab-pane">${renderStations(p)}</div>
    <div id="tab-routes" class="tab-pane">${renderRoutes(p)}</div>
    <div id="tab-teams" class="tab-pane">${renderTeams(p)}</div>
    <div id="tab-scoring" class="tab-pane">${renderScoring(p)}</div>
    <div id="tab-logs" class="tab-pane"><div id="logs-content">Loading...</div></div>
  `;
  updateFormula();
}

function showTab(id, btn) {
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
  document.querySelectorAll('.tab-pane').forEach(p => p.classList.remove('active'));
  btn.classList.add('active');
  document.getElementById(`tab-${id}`).classList.add('active');
  if (id === 'logs') loadLogs();
}

// ─── Overview ──────────────────────────────────────────────────────────────

function renderOverview(p) {
  const totalStages = (p.teams || []).reduce((s, t) => s + t.stages_done, 0);
  const totalWrong = (p.teams || []).reduce((s, t) => s + t.wrong_count, 0);
  const sorted = [...(p.teams || [])].sort((a, b) =>
    b.stages_done - a.stages_done || a.penalty_mins - b.penalty_mins
  );
  const medals = ['🥇', '🥈', '🥉'];

  return `
    <div class="metrics">
      <div class="metric">
        <div class="metric-val">${(p.stations || []).length}</div>
        <div class="metric-lbl">Stations</div>
      </div>
      <div class="metric">
        <div class="metric-val">${(p.teams || []).length}</div>
        <div class="metric-lbl">Teams</div>
      </div>
      <div class="metric">
        <div class="metric-val">${totalStages}</div>
        <div class="metric-lbl">Stages cleared</div>
      </div>
      <div class="metric">
        <div class="metric-val">${totalWrong}</div>
        <div class="metric-lbl">Wrong answers</div>
      </div>
    </div>

    <div style="display:flex;gap:10px;margin-bottom:16px">
      <button class="btn btn-sm" onclick="openModal('modal-broadcast')">
        <i class="ti ti-speakerphone"></i> Broadcast
      </button>
    </div>

    ${sorted.length ? `
    <div class="tbl-wrap">
      <table>
        <thead>
          <tr>
            <th>#</th><th>Team</th><th>Leader</th>
            <th>Progress</th><th>Wrong</th><th>Penalty</th>
            <th>Status</th><th>Actions</th>
          </tr>
        </thead>
        <tbody>
          ${sorted.map((t, i) => `
            <tr>
              <td style="font-family:var(--font-hand);font-size:16px">
                ${medals[i] || `#${i + 1}`}
              </td>
              <td style="font-family:var(--font-hand);font-size:16px">${t.name}</td>
              <td style="color:var(--tan-dark)">${t.leader_name}</td>
              <td style="min-width:120px">
                <div style="font-size:12px">${t.stages_done} / ${(p.stations||[]).length}</div>
                <div class="prog-bg">
                  <div class="prog-fill" style="width:${(p.stations||[]).length ? Math.round(t.stages_done / (p.stations||[]).length * 100) : 0}%"></div>
                </div>
              </td>
              <td style="color:var(--red);font-family:var(--font-hand);font-size:16px">${t.wrong_count}</td>
              <td style="font-family:monospace;font-size:12px">+${t.penalty_mins}min</td>
              <td><span class="badge badge-${p.status === 'live' ? 'live' : 'draft'}">${t.status}</span></td>
              <td style="display:flex;gap:6px">
                <button class="btn btn-sm" onclick="openPenalty('${t.id}','${t.name}')">
                  <i class="ti ti-alert-triangle"></i>
                </button>
              </td>
            </tr>
          `).join('')}
        </tbody>
      </table>
    </div>` : `
    <div class="empty-state">
      <div class="empty-state-icon">👥</div>
      <div class="empty-state-text">No teams yet — add them in the Teams tab</div>
    </div>`}
  `;
}

// ─── Stations ──────────────────────────────────────────────────────────────

function renderStations(p) {
  const stations = p.stations || [];
  return `
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:14px">
      <div style="font-family:var(--font-hand);font-size:18px">${stations.length} station${stations.length !== 1 ? 's' : ''}</div>
      <button class="btn btn-primary btn-sm" onclick="openAddStation()">
        <i class="ti ti-plus"></i> Add station
      </button>
    </div>
    ${stations.length ? stations.map((s, i) => `
      <div class="station-row">
        <div class="station-num">${s.station_code}</div>
        <div style="flex:1;min-width:0">
          <div style="display:flex;align-items:center;flex-wrap:wrap;gap:4px">
            <span class="station-name">${s.name}</span>
            <span class="type-pill tp-${s.mission_type}">${s.mission_type}</span>
            ${s.photo_required ? '<span class="type-pill" style="background:#fdf4ff;color:#7e22ce">📸 photo</span>' : ''}
          </div>
          <div class="station-detail">${s.clue_text}</div>
          <div style="margin-top:4px;display:flex;gap:8px;flex-wrap:wrap">
            <span style="font-size:11px;color:var(--tan-dark)">
              Answer: <strong style="color:var(--dark)">${s.answer}</strong>
            </span>
            <span style="font-size:11px;background:var(--cream-dark);padding:1px 6px;border-radius:4px">
              Hint −${s.hint_cost}pts
            </span>
            <span style="font-size:11px;background:var(--cream-dark);padding:1px 6px;border-radius:4px">
              Reveal −${s.answer_cost}pts
            </span>
          </div>
        </div>
        <button class="btn btn-sm" onclick="openEditStation('${s.id}', ${i})">
          <i class="ti ti-edit"></i>
        </button>
      </div>
    `).join('') : `
    <div class="empty-state">
      <div class="empty-state-icon">📍</div>
      <div class="empty-state-text">No stations yet</div>
      <button class="btn btn-primary" onclick="openAddStation()">
        <i class="ti ti-plus"></i> Add first station
      </button>
    </div>`}
  `;
}

// ─── Routes ────────────────────────────────────────────────────────────────

function renderRoutes(p) {
  const teams = p.teams || [];
  const stations = p.stations || [];
  if (!teams.length || !stations.length) {
    return `<div class="empty-state">
      <div class="empty-state-icon">🗺️</div>
      <div class="empty-state-text">Add stations and teams first</div>
    </div>`;
  }

  return `
    <div style="display:flex;gap:10px;margin-bottom:16px">
      <button class="btn btn-primary btn-sm" onclick="shuffleRoutes()">
        <i class="ti ti-arrows-shuffle"></i> Auto-shuffle all routes
      </button>
    </div>
    ${teams.map(t => {
      const route = t.route || stations.map(s => s.station_code);
      return `
        <div class="card" style="margin-bottom:10px">
          <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">
            <div style="font-family:var(--font-hand);font-size:17px">${t.name}</div>
            <span style="font-size:11px;color:var(--tan-dark)">${route.length} stations</span>
          </div>
          <div class="route-pills">
            ${route.map((code, i) => {
              const cls = i < t.stages_done ? 'done'
                : i === t.stages_done && p.status === 'live' ? 'cur' : '';
              return `<span class="rp ${cls}">${code}</span>`;
            }).join('')}
          </div>
        </div>`;
    }).join('')}
  `;
}

// ─── Teams ─────────────────────────────────────────────────────────────────

function renderTeams(p) {
  const teams = p.teams || [];
  return `
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:14px">
      <div style="font-family:var(--font-hand);font-size:18px">${teams.length} team${teams.length !== 1 ? 's' : ''}</div>
      <button class="btn btn-primary btn-sm" onclick="openModal('modal-team')">
        <i class="ti ti-plus"></i> Add team
      </button>
    </div>
    ${teams.length ? `
    <div class="tbl-wrap">
      <table>
        <thead>
          <tr>
            <th>Team name</th><th>Leader</th><th>Mobile</th>
            <th>WhatsApp</th><th>Status</th><th>Actions</th>
          </tr>
        </thead>
        <tbody>
          ${teams.map(t => `
            <tr>
              <td style="font-family:var(--font-hand);font-size:16px">${t.name}</td>
              <td>${t.leader_name}</td>
              <td style="font-family:monospace;font-size:12px">${t.mobile}</td>
              <td style="font-family:monospace;font-size:12px">${t.group_number}</td>
              <td><span class="badge badge-${t.status === 'racing' ? 'live' : 'draft'}">${t.status}</span></td>
              <td>
                <button class="btn btn-sm btn-red" onclick="deleteTeam('${t.id}')">
                  <i class="ti ti-trash"></i>
                </button>
              </td>
            </tr>
          `).join('')}
        </tbody>
      </table>
    </div>` : `
    <div class="empty-state">
      <div class="empty-state-icon">👥</div>
      <div class="empty-state-text">No teams yet</div>
    </div>`}
  `;
}

// ─── Scoring ───────────────────────────────────────────────────────────────

function renderScoring(p) {
  const s = p.scoring || {};
  return `
    <div class="grid2">
      <div class="card">
        <div class="card-title">Point rules</div>
        <div class="form-group">
          <label class="form-label">Points per station</label>
          <input type="number" id="sc-stage" value="${s.stage_pts || 100}" oninput="updateFormula()">
        </div>
        <div class="form-group">
          <label class="form-label">Wrong answer deduction</label>
          <input type="number" id="sc-wrong" value="${s.wrong_pts || 10}" oninput="updateFormula()">
        </div>
        <div class="form-group">
          <label class="form-label">Hint cost</label>
          <input type="number" id="sc-hint" value="${s.hint_pts || 5}" oninput="updateFormula()">
        </div>
        <div class="form-group">
          <label class="form-label">Answer reveal cost</label>
          <input type="number" id="sc-answer" value="${s.answer_pts || 20}" oninput="updateFormula()">
        </div>
      </div>
      <div class="card">
        <div class="card-title">Time rules</div>
        <div class="form-group">
          <label class="form-label">Time penalty per wrong answer (min)</label>
          <input type="number" id="sc-wtime" value="${s.wrong_time || 5}" oninput="updateFormula()">
        </div>
        <div class="form-group">
          <label class="form-label">Tiebreaker</label>
          <select id="sc-tie">
            <option>Fastest overall time</option>
            <option>Fewest wrong answers</option>
            <option>Fewest hints used</option>
          </select>
        </div>
        <hr class="divider">
        <div style="font-size:12px;color:var(--tan-dark);margin-bottom:6px">Score formula</div>
        <div class="formula-box" id="formula-box"></div>
      </div>
    </div>
    <div style="margin-top:14px">
      <button class="btn btn-primary" onclick="saveScoring()">
        <i class="ti ti-check"></i> Save rules
      </button>
    </div>
  `;
}

function updateFormula() {
  const sp = document.getElementById('sc-stage')?.value || 100;
  const wp = document.getElementById('sc-wrong')?.value || 10;
  const hp = document.getElementById('sc-hint')?.value || 5;
  const ap = document.getElementById('sc-answer')?.value || 20;
  const wt = document.getElementById('sc-wtime')?.value || 5;
  const box = document.getElementById('formula-box');
  if (box) box.textContent =
    `Score\n= stages × ${sp}\n− wrong × ${wp}\n− hints × ${hp}\n− reveals × ${ap}\n\nTime\n= duration + wrong × ${wt}min`;
}

async function saveScoring() {
  if (!activeProject) return;
  await api('PATCH', `/projects/${activeProject.id}`, {
    scoring_stage_pts: parseInt(document.getElementById('sc-stage').value),
    scoring_wrong_pts: parseInt(document.getElementById('sc-wrong').value),
    scoring_hint_pts:  parseInt(document.getElementById('sc-hint').value),
    scoring_answer_pts: parseInt(document.getElementById('sc-answer').value),
    scoring_wrong_time: parseInt(document.getElementById('sc-wtime').value),
  });
  alert('Scoring rules saved!');
  await selectProject(activeProject.id);
}

// ─── Logs ──────────────────────────────────────────────────────────────────

async function loadLogs() {
  if (!activeProject) return;
  const logs = await api('GET', `/projects/${activeProject.id}/logs`);
  const colors = {
    correct: 'dot-correct', wrong: 'dot-wrong',
    hint: 'dot-hint', penalty: 'dot-penalty', finish: 'dot-finish',
  };
  document.getElementById('logs-content').innerHTML = logs.length ? `
    <div class="card">
      ${logs.map(l => `
        <div class="log-row">
          <span class="log-time">${l.created_at ? new Date(l.created_at).toLocaleTimeString('en-SG', {hour:'2-digit',minute:'2-digit'}) : '—'}</span>
          <div class="log-dot ${colors[l.event_type] || 'dot-finish'}"></div>
          <div style="flex:1">
            <span style="font-family:var(--font-hand);font-size:15px">${getTeamName(l.team_id)}</span>
            <span style="color:var(--tan-dark)"> — ${l.message}</span>
          </div>
          ${l.pts_change ? `<span style="font-size:12px;color:${l.pts_change < 0 ? 'var(--red)' : 'var(--green)'}">${l.pts_change > 0 ? '+' : ''}${l.pts_change}pts</span>` : ''}
        </div>
      `).join('')}
    </div>` : `<div class="empty-state"><div class="empty-state-text">No activity yet</div></div>`;
}

function getTeamName(teamId) {
  if (!activeProject) return teamId;
  const t = (activeProject.teams || []).find(t => t.id === teamId);
  return t ? t.name : teamId;
}

// ─── Station CRUD ──────────────────────────────────────────────────────────

function openAddStation() {
  editingStationId = null;
  editingStationIdx = null;
  document.getElementById('station-modal-title').textContent = 'Add station';
  document.getElementById('delete-station-btn').style.display = 'none';
  ['s-code','s-name','s-clue','s-answer','s-hint','s-media'].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.value = '';
  });
  document.getElementById('s-type').value = 'text';
  document.getElementById('s-hint-cost').value = 5;
  document.getElementById('s-answer-cost').value = 20;
  document.getElementById('s-photo').checked = false;
  updateTypeHint();
  openModal('modal-station');
}

function openEditStation(id, idx) {
  const s = activeProject.stations[idx];
  editingStationId = id;
  editingStationIdx = idx;
  document.getElementById('station-modal-title').textContent = `Edit station ${s.station_code}`;
  document.getElementById('delete-station-btn').style.display = '';
  document.getElementById('s-code').value = s.station_code;
  document.getElementById('s-name').value = s.name;
  document.getElementById('s-type').value = s.mission_type;
  document.getElementById('s-clue').value = s.clue_text;
  document.getElementById('s-answer').value = s.answer;
  document.getElementById('s-hint').value = s.hint_text;
  document.getElementById('s-hint-cost').value = s.hint_cost;
  document.getElementById('s-answer-cost').value = s.answer_cost;
  document.getElementById('s-photo').checked = s.photo_required;
  if (s.clue_media_url) document.getElementById('s-media').value = s.clue_media_url;
  if (s.gps_lat) document.getElementById('s-lat').value = s.gps_lat;
  if (s.gps_lng) document.getElementById('s-lng').value = s.gps_lng;
  updateTypeHint();
  openModal('modal-station');
}

function updateTypeHint() {
  const type = document.getElementById('s-type').value;
  const hints = {
    text: 'Bot sends text. Team replies with a text answer.',
    image: 'Bot sends an image. Team replies with text.',
    gps: 'Bot sends a WhatsApp GPS pin. Team navigates there.',
    video: 'Bot sends a video. Team watches and replies.',
  };
  document.getElementById('s-type-hint').textContent = hints[type] || '';
  document.getElementById('s-media-group').style.display =
    ['image','video'].includes(type) ? '' : 'none';
  document.getElementById('s-gps-group').style.display =
    type === 'gps' ? '' : 'none';
}

async function saveStation() {
  const data = {
    station_code: document.getElementById('s-code').value.trim().toUpperCase(),
    name: document.getElementById('s-name').value.trim(),
    mission_type: document.getElementById('s-type').value,
    clue_text: document.getElementById('s-clue').value.trim(),
    clue_media_url: document.getElementById('s-media').value.trim(),
    answer: document.getElementById('s-answer').value.trim(),
    hint_text: document.getElementById('s-hint').value.trim(),
    hint_cost: parseInt(document.getElementById('s-hint-cost').value) || 5,
    answer_cost: parseInt(document.getElementById('s-answer-cost').value) || 20,
    photo_required: document.getElementById('s-photo').checked,
    order_index: editingStationIdx ?? (activeProject.stations?.length || 0),
    gps_lat: parseFloat(document.getElementById('s-lat')?.value) || null,
    gps_lng: parseFloat(document.getElementById('s-lng')?.value) || null,
  };

  if (!data.station_code || !data.answer) {
    alert('Station ID and answer are required'); return;
  }

  if (editingStationId) {
    await api('PATCH', `/projects/${activeProject.id}/stations/${editingStationId}`, data);
  } else {
    await api('POST', `/projects/${activeProject.id}/stations`, data);
  }

  closeModal('modal-station');
  await selectProject(activeProject.id);
  showTab('stations', document.querySelectorAll('.tab-btn')[1]);
}

async function deleteStation() {
  if (!editingStationId) return;
  if (!confirm('Delete this station?')) return;
  await api('DELETE', `/projects/${activeProject.id}/stations/${editingStationId}`);
  closeModal('modal-station');
  await selectProject(activeProject.id);
  showTab('stations', document.querySelectorAll('.tab-btn')[1]);
}

// ─── Team CRUD ─────────────────────────────────────────────────────────────

async function saveTeam() {
  const name = document.getElementById('t-name').value.trim();
  if (!name) { alert('Team name is required'); return; }

  await api('POST', `/projects/${activeProject.id}/teams`, {
    name,
    leader_name: document.getElementById('t-leader').value.trim(),
    mobile: document.getElementById('t-mobile').value.trim(),
    group_number: document.getElementById('t-wa').value.trim(),
  });

  closeModal('modal-team');
  ['t-name','t-leader','t-mobile','t-wa'].forEach(id =>
    document.getElementById(id).value = ''
  );
  await selectProject(activeProject.id);
  showTab('teams', document.querySelectorAll('.tab-btn')[3]);
}

async function deleteTeam(teamId) {
  if (!confirm('Remove this team?')) return;
  await api('DELETE', `/projects/${activeProject.id}/teams/${teamId}`);
  await selectProject(activeProject.id);
}

// ─── Broadcast ─────────────────────────────────────────────────────────────

async function sendBroadcast() {
  const msg = document.getElementById('bc-msg').value.trim();
  if (!msg) { alert('Please enter a message'); return; }
  await api('POST', `/projects/${activeProject.id}/broadcast`, { message: msg });
  closeModal('modal-broadcast');
  document.getElementById('bc-msg').value = '';
  alert('Message sent to all teams!');
}

// ─── Penalty ───────────────────────────────────────────────────────────────

function openPenalty(teamId, teamName) {
  document.getElementById('pen-team-id').value = teamId;
  document.getElementById('pen-team-name').value = teamName;
  document.getElementById('pen-reason').value = '';
  openModal('modal-penalty');
}

async function submitPenalty() {
  const reason = document.getElementById('pen-reason').value.trim();
  if (!reason) { alert('Please enter a reason'); return; }
  await api('POST', `/projects/${activeProject.id}/penalty`, {
    team_id: document.getElementById('pen-team-id').value,
    reason,
    pts: parseInt(document.getElementById('pen-pts').value) || 10,
    time_mins: parseInt(document.getElementById('pen-time').value) || 5,
  });
  closeModal('modal-penalty');
  alert('Penalty applied!');
  await selectProject(activeProject.id);
}

// ─── Routes ────────────────────────────────────────────────────────────────

async function shuffleRoutes() {
  if (!confirm('Auto-shuffle routes for all teams?')) return;
  await api('POST', `/projects/${activeProject.id}/shuffle-routes`);
  await selectProject(activeProject.id);
  showTab('routes', document.querySelectorAll('.tab-btn')[2]);
}

// ─── Modal helpers ─────────────────────────────────────────────────────────

function openModal(id) {
  document.getElementById(id).classList.add('open');
}
function closeModal(id) {
  document.getElementById(id).classList.remove('open');
}

document.querySelectorAll('.modal-overlay').forEach(m => {
  m.addEventListener('click', e => {
    if (e.target === m) m.classList.remove('open');
  });
});