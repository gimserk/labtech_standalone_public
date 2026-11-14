/* Student-facing CTF 2.0: filter, keyboard-operable challenges and safe API controls. */
(() => {
  'use strict';
  function init() {
    const board = document.getElementById('ctfBoard');
    if (!board) return;
    const el = id => document.getElementById(id);
    const cards = [...board.querySelectorAll('.ctf-challenge')];
    const modal = el('ctfChallengeModal');
    const hints = JSON.parse(el('ctfHintsData')?.textContent || '[]');
    const csrf = board.dataset.csrf;
    let current = null;

    function setFeedback(msg, error = false) {
      const target = el('ctfFlagFeedback');
      target.textContent = msg;
      target.className = 'ctf-feedback small mt-2 ' + (error ? 'text-danger' : 'text-success');
    }
    async function send(url, body) {
      const response = await fetch(url, {
        method: 'POST', credentials: 'same-origin',
        headers: {'Content-Type':'application/json', 'X-CSRFToken':csrf},
        body: JSON.stringify(body),
      });
      const data = await response.json().catch(() => ({status:'error', message:'Unable to read server response.'}));
      if (!response.ok || data.status !== 'success') throw new Error(data.message || 'Unable to save.');
      return data;
    }
    function refreshFilter() {
      const search = el('ctfSearch').value.trim().toLocaleLowerCase();
      const category = el('ctfCategoryFilter').value;
      const difficulty = el('ctfDifficultyFilter').value;
      const progress = el('ctfSolveFilter').value;
      let visible = 0;
      for (const card of cards) {
        const matches = (!search || card.dataset.title.toLocaleLowerCase().includes(search))
          && (!category || card.dataset.category === category)
          && (!difficulty || card.dataset.difficulty === difficulty)
          && (!progress || card.dataset.solved === (progress === 'solved' ? 'true' : 'false'));
        card.hidden = !matches;
        if (matches) visible += 1;
      }
      board.querySelectorAll('.ctf-category').forEach(group => {
        group.hidden = ![...group.querySelectorAll('.ctf-challenge')].some(card => !card.hidden);
      });
      el('ctfFilterCount').textContent = visible + ' of ' + cards.length + ' challenges shown.';
    }
    ['ctfSearch','ctfCategoryFilter','ctfDifficultyFilter','ctfSolveFilter'].forEach(id => {
      el(id)?.addEventListener(id === 'ctfSearch' ? 'input' : 'change', refreshFilter);
    });
    refreshFilter();

    function link(label, url, download = false) {
      if (!url) return;
      const a = document.createElement('a');
      a.textContent = label;
      a.className = 'btn btn-sm btn-outline-primary me-2 mb-2';
      a.href = url;
      if (download) a.setAttribute('download', '');
      else {
        // Avoid introducing javascript: links even if an older database row
        // has a malformed external resource URL.
        let check;
        try { check = new URL(url, window.location.origin); } catch (_) { return; }
        if (!['http:', 'https:'].includes(check.protocol)) return;
        a.target = '_blank';
        a.rel = 'noopener noreferrer';
      }
      el('ctfModalResources').appendChild(a);
    }

    function showChallenge(card) {
      if (!card) return;
      current = card;
      el('ctfModalTitle').textContent = card.dataset.title;
      el('ctfModalPoints').textContent = card.dataset.points + ' pts · ' + card.dataset.difficulty;
      el('ctfModalDescription').replaceChildren();
      const description = el('ctf-desc-' + card.dataset.id);
      if (description) el('ctfModalDescription').appendChild(description.content.cloneNode(true));
      el('ctfModalResources').replaceChildren();
      link('Download evidence', card.dataset.fileUrl, true);
      link('Open external challenge', card.dataset.externalUrl);
      link('Open LabTech lab', card.dataset.labUrl);
      el('ctfModalHints').replaceChildren();
      const relevant = hints.filter(h => String(h.challenge_id) === card.dataset.id);
      if (relevant.length) {
        const heading = document.createElement('h3');
        heading.className = 'h6 mt-3';
        heading.textContent = 'Hints';
        el('ctfModalHints').appendChild(heading);
      }
      for (const hint of relevant) {
        const wrap = document.createElement('div');
        wrap.className = 'ctf-hint';
        if (hint.is_unveiled) {
          const label = document.createElement('strong');
          label.textContent = 'Hint ' + hint.order + ' (' + hint.cost + ' point cost)';
          const content = document.createElement('p');
          content.textContent = hint.text;
          wrap.append(label, content);
        } else {
          const button = document.createElement('button');
          button.type = 'button';
          button.className = 'btn btn-outline-secondary btn-sm';
          button.textContent = 'Reveal hint ' + hint.order + ' (' + hint.cost + ' points)';
          button.disabled = board.dataset.active !== 'true';
          button.addEventListener('click', async () => {
            if (!window.confirm('Reveal this hint? Its ' + hint.cost + '-point cost will reduce your solve points.')) return;
            button.disabled = true;
            try {
              const data = await send(board.dataset.hintPrefix + hint.id + '/unveil/', {});
              hint.is_unveiled = true;
              hint.text = data.hint_text;
              wrap.replaceChildren();
              const label = document.createElement('strong');
              label.textContent = 'Hint ' + hint.order + ' (' + hint.cost + ' point cost)';
              const text = document.createElement('p');
              text.textContent = data.hint_text;
              wrap.append(label, text);
            } catch (error) {
              setFeedback(error.message, true);
              button.disabled = false;
            }
          });
          wrap.append(button);
        }
        el('ctfModalHints').appendChild(wrap);
      }
      const canSubmit = board.dataset.active === 'true' && card.dataset.solved !== 'true';
      const evidence = card.dataset.scoringMethod === 'evidence';
      el('ctfFlagForm').hidden = !canSubmit || evidence;
      el('ctfEvidenceActions').hidden = !canSubmit || !evidence;
      el('ctfFlagInput').value = '';
      setFeedback(canSubmit ? '' : card.dataset.solved === 'true'
        ? 'This challenge has already been solved.' : 'This competition is not accepting flags.');
    }
    modal?.addEventListener('show.bs.modal', event => showChallenge(event.relatedTarget));
    el('ctfEvidenceClaim')?.addEventListener('click', async () => {
      if (!current || current.dataset.scoringMethod !== 'evidence') return;
      const button = el('ctfEvidenceClaim');
      button.disabled = true;
      setFeedback('Checking live LabTech evidence...');
      try {
        const data = await send(board.dataset.claimUrl, {challenge_id: Number(current.dataset.id)});
        setFeedback(data.message);
        current.classList.add('solved');
        current.dataset.solved = 'true';
        current.setAttribute('aria-label', current.dataset.title + ', solved');
        el('ctfEvidenceActions').hidden = true;
        window.setTimeout(() => window.location.reload(), 1200);
      } catch (error) {
        setFeedback(error.message, true);
      } finally { button.disabled = false; }
    });
    el('ctfFlagForm')?.addEventListener('submit', async event => {
      event.preventDefault();
      if (!current || !el('ctfFlagForm').reportValidity()) return;
      const button = el('ctfFlagSubmit');
      button.disabled = true;
      setFeedback('Checking flag...');
      try {
        const data = await send(board.dataset.submitUrl, {
          challenge_id: Number(current.dataset.id), flag: el('ctfFlagInput').value,
        });
        setFeedback(data.message);
        current.classList.add('solved');
        current.dataset.solved = 'true';
        current.setAttribute('aria-label', current.dataset.title + ', solved');
        el('ctfFlagForm').hidden = true;
        const existing = current.querySelector('.ctf-chip:last-child');
        if (existing) { existing.classList.add('solved'); existing.textContent = '✓ Solved'; }
        window.setTimeout(() => window.location.reload(), 1200);
      } catch (error) {
        setFeedback(error.message, true);
      } finally { button.disabled = false; }
    });
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();
