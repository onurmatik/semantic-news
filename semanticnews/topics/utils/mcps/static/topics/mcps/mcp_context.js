document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('.mcp-server-link').forEach((btn) => {
    btn.addEventListener('click', () => {
      const url = btn.dataset.url;
      if (url) {
        window.open(url, '_blank');
      }
    });
  });
});
