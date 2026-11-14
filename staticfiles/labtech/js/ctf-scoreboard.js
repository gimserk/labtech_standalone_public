/* LabTech CTF live scoreboard, authenticated polling; never exposes flags or private hints. */
(() => {
  'use strict';
  const init = () => {
    const root = document.getElementById('ctfWall');
    if (!root) return;
    const rows = document.getElementById('ctfWallRows');
    const recent = document.getElementById('ctfWallRecent');
    const status = document.getElementById('ctfWallStatus');
    const notice = document.getElementById('ctfWallNotice');
    let state;
    try { state = JSON.parse(document.getElementById('ctfWallInitial').textContent); }
    catch (_) { state = { rows: [], recent: [], frozen: false }; }

    const element = (tag, label, className) => {
      const item = document.createElement(tag);
      item.textContent = String(label);
      if (className) item.className = className;
      return item;
    };
    const render = data => {
      if (!data || !Array.isArray(data.rows) || !Array.isArray(data.recent)) return;
      // Use textContent for every untrusted name and challenge title.
      const body = document.createDocumentFragment();
      data.rows.forEach((entry, n) => {
        const tr = document.createElement('tr');
        const rank = element('th', '#' + (entry.rank || n + 1));
        rank.scope = 'row';
        tr.appendChild(rank);
        tr.appendChild(element('td', entry.display_name));
        tr.appendChild(element('td', entry.solves, 'text-end'));
        const points = element('td', '', 'text-end');
        points.appendChild(element('strong', entry.points));
        tr.appendChild(points);
        body.appendChild(tr);
      });
      if (!data.rows.length) {
        const tr = document.createElement('tr');
        const empty = element('td', 'No teams or participants have joined yet.');
        empty.colSpan = 4;
        tr.appendChild(empty);
        body.appendChild(tr);
      }
      rows.replaceChildren(body);
      const activity = document.createDocumentFragment();
      data.recent.forEach(entry => {
        const li = document.createElement('li');
        li.appendChild(element('strong', entry.display_name));
        li.appendChild(document.createTextNode(' solved ' + entry.challenge));
        li.appendChild(element('span', '+' + entry.points + ' pts · ' + entry.when));
        activity.appendChild(li);
      });
      if (!data.recent.length) activity.appendChild(element('li', 'No successful solves yet.'));
      recent.replaceChildren(activity);
      const label = data.frozen ? 'Standings frozen' : 'Live standings';
      status.textContent = label + ' · ' + data.status +
        ' · ' + (data.mode === 'team' ? 'Team competition' : 'Individual competition');
      const message = data.frozen
        ? 'Standings are frozen. New scores and recent solves remain hidden until the instructor unfreezes the board.'
        : data.paused
          ? 'Flag submissions and hints are temporarily paused. Standings continue to refresh.'
          : 'Scoreboard updates automatically every 12 seconds.';
      if (notice.textContent.trim() !== message) notice.textContent = message;
      state = data;
    };

    let fetching = false;
    async function refresh() {
      if (fetching || document.hidden) return;
      fetching = true;
      const controller = new AbortController();
      const abort = window.setTimeout(() => controller.abort(), 8000);
      try {
        const response = await fetch(root.dataset.feedUrl, {
          credentials: 'same-origin', cache: 'no-store',
          headers: {Accept: 'application/json'}, signal: controller.signal,
        });
        if (!response.ok) throw new Error('Scoreboard feed unavailable');
        render(await response.json());
      } catch (_) {
        notice.textContent = 'Scoreboard temporarily unavailable; showing the last verified standings.';
      } finally {
        window.clearTimeout(abort);
        fetching = false;
      }
    }
    render(state);
    window.setInterval(refresh, 12000);
    document.addEventListener('visibilitychange', () => { if (!document.hidden) refresh(); });
    document.getElementById('ctfWallFullscreen')?.addEventListener('click', () => {
      if (document.fullscreenElement) document.exitFullscreen?.();
      else root.requestFullscreen?.();
    });
  };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();
