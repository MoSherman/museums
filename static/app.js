document.addEventListener('DOMContentLoaded', () => {
  const btn = document.getElementById('refresh-btn');
  if (!btn) return;

  // Simple toast notification
  let toast = document.getElementById('toast');
  if (!toast) {
    toast = document.createElement('div');
    toast.id = 'toast';
    document.body.appendChild(toast);
  }

  function showToast(msg, duration = 3000) {
    toast.textContent = msg;
    toast.classList.add('show');
    setTimeout(() => toast.classList.remove('show'), duration);
  }

  btn.addEventListener('click', async () => {
    btn.disabled = true;
    btn.textContent = 'Refreshing…';

    try {
      const resp = await fetch('/api/refresh', { method: 'POST' });
      if (resp.ok) {
        showToast('Scrape started — reload the page in ~30s to see updates.', 5000);
      } else {
        showToast('Refresh failed. Check server logs.');
      }
    } catch {
      showToast('Network error — is the server running?');
    } finally {
      setTimeout(() => {
        btn.disabled = false;
        btn.textContent = 'Refresh data';
      }, 5000);
    }
  });
});
