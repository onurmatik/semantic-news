document.addEventListener('DOMContentLoaded', () => {
  const categoryLinks = document.querySelectorAll('.category-filter');
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
  }

  categoryLinks.forEach(link => {
    link.addEventListener('click', e => {
      e.preventDefault();
      const category = link.dataset.category;
      window.location.hash = category;
      applyFilter(category);
    });
  });

  window.addEventListener('hashchange', () => {
    applyFilter(window.location.hash.substring(1));
  });

  applyFilter(window.location.hash.substring(1));
});
