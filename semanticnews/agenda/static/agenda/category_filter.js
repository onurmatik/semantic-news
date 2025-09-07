document.addEventListener('DOMContentLoaded', () => {
  const categoryLinks = document.querySelectorAll('.category-filter');
  const domainButton = document.getElementById('domainDropdown');
  const domainOptions = document.querySelectorAll('.domain-option');
  const domainDefault = domainButton ? domainButton.dataset.defaultLabel || domainButton.textContent.trim() : '';
  if (!categoryLinks.length) {
    return;
  }

  function applyFilter(category) {
    const items = document.querySelectorAll('.event-item');
    items.forEach(item => {
      const cats = (item.dataset.categories || '').split(' ').filter(Boolean);
      if (!category || cats.includes(category)) {
        item.classList.remove('d-none');
      } else {
        item.classList.add('d-none');
      }
    });
    categoryLinks.forEach(link => {
      if (link.dataset.category === category) {
        link.classList.add('active');
      } else {
        link.classList.remove('active');
      }
    });
    if (domainButton && category) {
      domainButton.textContent = domainDefault;
      domainOptions.forEach(opt => opt.classList.remove('active'));
    }
  }

  categoryLinks.forEach(link => {
    link.addEventListener('click', e => {
      e.preventDefault();
      const category = link.dataset.category;
      const current = window.location.hash.substring(1);
      if (current === category) {
        history.replaceState(null, '', window.location.pathname + window.location.search);
        applyFilter('');
      } else {
        window.location.hash = category;
        applyFilter(category);
      }
      if (domainButton) {
        domainButton.textContent = domainDefault;
        domainOptions.forEach(opt => opt.classList.remove('active'));
      }
  });
  });

  window.addEventListener('hashchange', () => {
    const hash = window.location.hash.substring(1);
    if (hash.startsWith('domain:')) {
      applyFilter('');
    } else {
      applyFilter(hash);
    }
  });

  const initial = window.location.hash.substring(1);
  if (!initial.startsWith('domain:')) {
    applyFilter(initial);
  } else {
    applyFilter('');
  }
});
