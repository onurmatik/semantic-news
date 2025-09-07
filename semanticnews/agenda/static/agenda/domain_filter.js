document.addEventListener('DOMContentLoaded', () => {
  const domainSelect = document.getElementById('domainFilter');
  if (!domainSelect) {
    return;
  }
  const categoryLinks = document.querySelectorAll('.category-filter');

  function applyFilter(domain) {
    const items = document.querySelectorAll('.event-item');
    items.forEach(item => {
      const domains = (item.dataset.domains || '').split(' ').filter(Boolean);
      if (!domain || domains.includes(domain)) {
        item.classList.remove('d-none');
      } else {
        item.classList.add('d-none');
      }
    });
    if (domain) {
      categoryLinks.forEach(link => link.classList.remove('active'));
    }
  }

  domainSelect.addEventListener('change', () => {
    const domain = domainSelect.value;
    if (domain) {
      window.location.hash = `domain:${domain}`;
    } else {
      history.replaceState(null, '', window.location.pathname + window.location.search);
    }
    applyFilter(domain);
  });

  window.addEventListener('hashchange', () => {
    const hash = window.location.hash.substring(1);
    if (hash.startsWith('domain:')) {
      const domain = hash.slice(7);
      domainSelect.value = domain;
      applyFilter(domain);
    } else {
      domainSelect.value = '';
      applyFilter('');
    }
  });

  const initial = window.location.hash.substring(1);
  if (initial.startsWith('domain:')) {
    const domain = initial.slice(7);
    domainSelect.value = domain;
    applyFilter(domain);
  }
});
