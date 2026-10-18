/* Native media controls work without JavaScript; enhancement explains playback failures. */
document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('[data-audio-player]').forEach(player => {
        const audio = player.querySelector('audio');
        const status = player.querySelector('[data-audio-status]');
        const retry = player.querySelector('[data-audio-retry]');
        const external = player.dataset.sourceType === 'external_url';
        const update = (state, message) => {
            player.dataset.state = state;
            status.textContent = message;
        };
        const failed = () => {
            update('error', external
                ? 'Unable to play this audio here. Retry loading or open the audio source below.'
                : 'Unable to play this recording. Retry loading or download the audio below.');
            retry.hidden = false;
        };
        const ready = () => {
            if (audio.error) return failed();
            update('ready', 'Ready to listen. Press play.');
            if (document.activeElement === retry) audio.focus();
            retry.hidden = true;
        };
        audio.addEventListener('loadstart', () => update('loading', 'Loading audio…'));
        audio.addEventListener('loadedmetadata', ready);
        audio.addEventListener('canplay', () => {
            if (player.dataset.state !== 'loading') return;
            if (audio.paused) ready();
            else update('playing', 'Playing');
            retry.hidden = true;
        });
        audio.addEventListener('playing', () => { retry.hidden = true; update('playing', 'Playing'); });
        audio.addEventListener('pause', () => { if (!audio.error && !audio.ended) update('paused', 'Paused — press play to continue.'); });
        audio.addEventListener('waiting', () => update('loading', 'Buffering audio…'));
        audio.addEventListener('stalled', () => {
            if (audio.error) return failed();
            if (audio.readyState >= HTMLMediaElement.HAVE_FUTURE_DATA) return;
            update('loading', 'Loading is taking longer than expected. You can retry or use the link below.');
            retry.hidden = false;
        });
        audio.addEventListener('ended', () => update('ended', 'Recording finished. You can replay it or mark this lesson complete below.'));
        audio.addEventListener('error', failed);
        retry.addEventListener('click', () => { update('loading', 'Reloading audio…'); audio.load(); });
        // Metadata or errors can arrive before this deferred script initializes.
        if (audio.error) failed();
        else if (audio.readyState >= 1) ready();
    });
});
