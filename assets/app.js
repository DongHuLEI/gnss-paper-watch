(function () {
  const langKey = 'gnss-reader-lang';

  function setLang(lang) {
    const next = lang === 'en' ? 'en' : 'zh';
    document.documentElement.dataset.lang = next;
    try { localStorage.setItem(langKey, next); } catch (error) {}
    document.querySelectorAll('[data-set-lang]').forEach(function (button) {
      button.setAttribute('aria-pressed', button.dataset.setLang === next ? 'true' : 'false');
    });
  }

  let initial = 'zh';
  try { initial = localStorage.getItem(langKey) || initial; } catch (error) {}
  setLang(initial);

  document.addEventListener('click', function (event) {
    const langButton = event.target.closest('[data-set-lang]');
    if (langButton) {
      setLang(langButton.dataset.setLang);
      return;
    }

    const filterButton = event.target.closest('[data-filter]');
    if (filterButton) {
      const bar = filterButton.closest('.filter-bar');
      const grid = document.querySelector('[data-paper-grid]');
      if (!bar || !grid) return;
      bar.querySelectorAll('[data-filter]').forEach(function (button) {
        button.setAttribute('aria-pressed', button === filterButton ? 'true' : 'false');
      });
      applyFilters();
      return;
    }

    const link = event.target.closest('a[href^="#"]');
    if (!link) return;
    const target = document.querySelector(link.getAttribute('href'));
    if (target) {
      event.preventDefault();
      target.scrollIntoView({ behavior: 'smooth' });
    }
  });

  function applyFilters() {
    const grid = document.querySelector('[data-paper-grid]');
    if (!grid) return;
    const active = document.querySelector('.filter-bar [data-filter][aria-pressed="true"]');
    const domain = active ? active.dataset.filter : 'all';
    const input = document.querySelector('[data-paper-search]');
    const query = input ? input.value.trim().toLowerCase() : '';
    let visible = 0;

    grid.querySelectorAll('[data-paper-card]').forEach(function (card) {
      const domainMatch = domain === 'all' || card.dataset.domain === domain;
      const haystack = (card.dataset.search || '').toLowerCase();
      const queryMatch = !query || haystack.indexOf(query) !== -1;
      const show = domainMatch && queryMatch;
      card.hidden = !show;
      if (show) visible += 1;
    });

    const count = document.querySelector('[data-result-count]');
    if (count) {
      count.textContent = visible + ' / ' + grid.querySelectorAll('[data-paper-card]').length + ' 篇';
    }
    const empty = document.querySelector('[data-empty-state]');
    if (empty) empty.style.display = visible === 0 ? 'block' : 'none';
  }

  const search = document.querySelector('[data-paper-search]');
  if (search) {
    search.addEventListener('input', applyFilters);
    document.addEventListener('keydown', function (event) {
      if (event.key !== '/' || event.ctrlKey || event.metaKey || event.altKey) return;
      const tag = (document.activeElement && document.activeElement.tagName) || '';
      if (tag === 'INPUT' || tag === 'TEXTAREA') return;
      event.preventDefault();
      search.focus();
    });
  }
})();
