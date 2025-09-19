document.addEventListener('DOMContentLoaded', () => {
  const domainButton = document.getElementById('domainDropdown');
  const domainOptions = document.querySelectorAll('.domain-option');
  if (!domainButton) {
    return;
  }
  const categoryLinks = document.querySelectorAll('.category-filter');
  const defaultLabel = domainButton.dataset.defaultLabel || domainButton.textContent.trim();

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
    domainOptions.forEach(opt => {
      if (opt.dataset.domain === domain) {
        opt.classList.add('active');
      } else {
        opt.classList.remove('active');
      }
    });
    domainButton.textContent = domain || defaultLabel;
    if (domain) {
      categoryLinks.forEach(link => link.classList.remove('active'));
    }
  }

  function resetDomainUI() {
    domainOptions.forEach(opt => {
      if (!opt.dataset.domain) {
        opt.classList.add('active');
      } else {
        opt.classList.remove('active');
      }
    });
    domainButton.textContent = defaultLabel;
  }

  domainOptions.forEach(option => {
    option.addEventListener('click', e => {
      e.preventDefault();
      const domain = option.dataset.domain;
      if (domain) {
        window.location.hash = `domain:${domain}`;
      } else {
        history.replaceState(null, '', window.location.pathname + window.location.search);
      }
      applyFilter(domain);
    });
  });

  window.addEventListener('hashchange', () => {
    const hash = window.location.hash.substring(1);
    if (hash.startsWith('domain:')) {
      const domain = hash.slice(7);
      applyFilter(domain);
    } else if (!hash || !categoryLinks.length) {
      applyFilter('');
    } else {
      resetDomainUI();
    }
  });

  const initial = window.location.hash.substring(1);
  if (initial.startsWith('domain:')) {
    const domain = initial.slice(7);
    applyFilter(domain);
  }
});
