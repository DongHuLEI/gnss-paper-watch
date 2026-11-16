(function () {
  'use strict';

  const READING_KEY = 'gnss-radar-reading-v2';
  const ID_PATTERN = /^(?:\d{4}\.\d{4,5}|[a-z-]+(?:\.[A-Z]{2})?\/\d{7})(?:v\d+)?$/;
  const browser = document.querySelector('[data-browser]');
  const filters = browser && browser.querySelector('[data-filters]');
  const cards = browser ? Array.from(browser.querySelectorAll('[data-paper-card]')) : [];
  let page = 1;
  let view = 'cards';
  let toastTimer;
  let menuReturn;
  let reading = { saved: [], read: [] };

  function toast(message) {
    const node = document.querySelector('[data-toast]');
    if (!node) return;
    clearTimeout(toastTimer);
    node.textContent = message;
    node.hidden = false;
    toastTimer = setTimeout(function () { node.hidden = true; }, 5500);
  }

  function preference(key, fallback) {
    try { return localStorage.getItem(key) || fallback; } catch (error) { return fallback; }
  }

  function savePreference(key, value) {
    try { localStorage.setItem(key, value); } catch (error) {}
  }

  function validReading(value) {
    if (!value || typeof value !== 'object' || !Array.isArray(value.saved) || !Array.isArray(value.read)) {
      throw new Error('阅读文件缺少 saved / read 列表。');
    }
    const next = {};
    ['saved', 'read'].forEach(function (key) {
      if (value[key].length > 20000 || value[key].some(function (id) { return typeof id !== 'string' || !ID_PATTERN.test(id); })) {
        throw new Error('阅读文件包含无效论文 ID 或记录过多。');
      }
      next[key] = Array.from(new Set(value[key]));
    });
    return next;
  }

  function loadReading() {
    try { reading = validReading(JSON.parse(localStorage.getItem(READING_KEY) || '{"saved":[],"read":[]}')); }
    catch (error) { reading = { saved: [], read: [] }; }
  }

  function writeReading(next) {
    try {
      localStorage.setItem(READING_KEY, JSON.stringify(next));
      reading = next;
      syncReading();
      if (browser) applyFilters(false);
      return true;
    } catch (error) {
      toast('浏览器无法保存阅读数据；请检查隐私模式或存储权限。');
      return false;
    }
  }

  function syncReading() {
    document.querySelectorAll('[data-save]').forEach(function (button) {
      const saved = reading.saved.includes(button.dataset.save);
      button.setAttribute('aria-pressed', String(saved));
      button.textContent = saved ? '已收藏' : '收藏';
    });
    document.querySelectorAll('[data-read]').forEach(function (button) {
      const done = reading.read.includes(button.dataset.read);
      button.setAttribute('aria-pressed', String(done));
      button.textContent = done ? '已读' : '标为已读';
    });
    document.querySelectorAll('[data-saved-count]').forEach(function (node) { node.textContent = reading.saved.length; });
    document.querySelectorAll('[data-paper-card]').forEach(function (card) {
      card.classList.toggle('is-read', reading.read.includes(card.dataset.id));
    });
  }

  function setLanguage(value) {
    const language = value === 'en' ? 'en' : 'zh';
    document.documentElement.dataset.lang = language;
    document.querySelectorAll('[data-language]').forEach(function (button) {
      button.setAttribute('aria-pressed', String(language === 'en'));
      button.title = '切换论文标题与速读语言；导航和整理正文以中文为主';
    });
    savePreference('gnss-reader-lang', language);
  }

  function setTheme(value) {
    const theme = value === 'dark' ? 'dark' : 'light';
    document.documentElement.dataset.theme = theme;
    document.querySelectorAll('[data-theme-toggle]').forEach(function (button) {
      button.setAttribute('aria-label', theme === 'dark' ? '切换为浅色主题' : '切换为深色主题');
    });
    savePreference('gnss-radar-theme', theme);
  }

  function field(name) {
    return filters && filters.querySelector('[data-field="' + name + '"]');
  }

  function getState() {
    const values = {};
    filters.querySelectorAll('[data-field]').forEach(function (node) {
      values[node.dataset.field] = node.type === 'checkbox' ? node.checked : node.value;
    });
    values.q = values.q.trim().toLowerCase();
    return values;
  }

  function restoreQuery() {
    const params = new URLSearchParams(location.search);
    filters.querySelectorAll('[data-field]').forEach(function (node) {
      const key = node.dataset.field;
      if (node.type === 'checkbox') {
        node.checked = params.get(key) === '1';
      } else if (node.tagName === 'SELECT') {
        const fallback = key === 'domain' ? browser.dataset.defaultDomain : (key === 'sort' ? 'newest' : 'all');
        const wanted = params.get(key) || fallback;
        node.value = Array.from(node.options).some(function (option) { return option.value === wanted; }) ? wanted : fallback;
      } else {
        node.value = (params.get(key) || '').slice(0, 500);
      }
    });
    const requestedPage = Number(params.get('page'));
    page = Number.isInteger(requestedPage) && requestedPage > 0 ? Math.min(requestedPage, 10000) : 1;
    const requestedView = params.get('view') || preference('gnss-radar-view', 'cards');
    view = requestedView === 'list' ? 'list' : 'cards';
  }

  function updateURL(state) {
    const url = new URL(location.href);
    const defaults = { domain: browser.dataset.defaultDomain || 'all', lens: 'all', month: 'all', status: 'all', reading: 'all', sort: 'newest' };
    Object.keys(state).forEach(function (key) {
      const value = key === 'q' ? field('q').value.trim() : state[key];
      if (key === 'saved') {
        if (value) url.searchParams.set(key, '1'); else url.searchParams.delete(key);
      } else if (value && value !== defaults[key]) {
        url.searchParams.set(key, value);
      } else {
        url.searchParams.delete(key);
      }
    });
    if (page > 1) url.searchParams.set('page', String(page)); else url.searchParams.delete('page');
    if (view === 'list') url.searchParams.set('view', 'list'); else url.searchParams.delete('view');
    try { history.replaceState(null, '', url); } catch (error) {}
  }

  function applyFilters(syncURL) {
    if (!browser) return;
    const state = getState();
    const tokens = state.q.split(/\s+/).filter(Boolean);
    const matching = cards.filter(function (card) {
      const data = card.dataset;
      const haystack = data.search.toLowerCase();
      return (state.domain === 'all' || data.domains.split(' ').includes(state.domain)) &&
        (state.lens === 'all' || data.lenses.split(' ').includes(state.lens)) &&
        (state.month === 'all' || data.issues.split(' ').some(function (date) { return date.startsWith(state.month); })) &&
        (state.status === 'all' || data.status === state.status) &&
        (!state.saved || reading.saved.includes(data.id)) &&
        (state.reading === 'all' || reading.read.includes(data.id) === (state.reading === 'read')) &&
        tokens.every(function (token) { return haystack.includes(token); });
    });
    matching.sort(function (a, b) {
      if (state.sort === 'score') return Number(b.dataset.score) - Number(a.dataset.score) || b.dataset.date.localeCompare(a.dataset.date);
      if (state.sort === 'collected') return b.dataset.collected.localeCompare(a.dataset.collected) || b.dataset.date.localeCompare(a.dataset.date);
      if (state.sort === 'oldest') return a.dataset.date.localeCompare(b.dataset.date) || a.dataset.id.localeCompare(b.dataset.id);
      return b.dataset.date.localeCompare(a.dataset.date) || Number(b.dataset.score) - Number(a.dataset.score);
    });
    const size = Number(browser.dataset.pageSize) || 12;
    const pages = Math.max(1, Math.ceil(matching.length / size));
    page = Math.max(1, Math.min(page, pages));
    const grid = browser.querySelector('[data-paper-grid]');
    grid.dataset.view = view;
    cards.forEach(function (card) { card.hidden = true; });
    const fragment = document.createDocumentFragment();
    matching.forEach(function (card, index) {
      card.hidden = index < (page - 1) * size || index >= page * size;
      fragment.appendChild(card);
    });
    grid.appendChild(fragment);
    browser.querySelector('[data-result-count]').textContent = '匹配 ' + matching.length + ' / ' + cards.length + ' 篇' + (matching.length ? ' · 第 ' + page + ' 页' : '');
    browser.querySelector('[data-empty]').hidden = matching.length !== 0;
    browser.querySelector('[data-pagination]').hidden = pages < 2;
    browser.querySelector('[data-page-label]').textContent = page + ' / ' + pages;
    browser.querySelector('[data-prev]').disabled = page <= 1;
    browser.querySelector('[data-next]').disabled = page >= pages;
    browser.querySelectorAll('[data-view]').forEach(function (button) {
      if (button.tagName === 'BUTTON') button.setAttribute('aria-pressed', String(button.dataset.view === view));
    });
    if (syncURL !== false) updateURL(state);
  }

  function resetFilters() {
    filters.reset();
    filters.querySelectorAll('[data-field]').forEach(function (node) {
      if (node.type === 'checkbox') node.checked = false;
      else if (node.tagName !== 'SELECT') node.value = '';
      else node.value = node.dataset.field === 'sort' ? 'newest' : (node.dataset.field === 'domain' ? browser.dataset.defaultDomain : 'all');
    });
    page = 1;
    applyFilters();
  }

  function changePage(offset) {
    page += offset;
    applyFilters();
    browser.querySelector('[data-result-count]').scrollIntoView({ block: 'center', behavior: 'auto' });
  }

  function toggleMenu(open) {
    if (open) menuReturn = document.activeElement;
    document.body.classList.toggle('menu-open', open);
    document.querySelectorAll('[data-menu]').forEach(function (button) { button.setAttribute('aria-expanded', String(open)); });
    if (open) {
      const first = document.querySelector('.sidebar a');
      if (first) first.focus();
    } else if (menuReturn) {
      menuReturn.focus();
    }
  }

  function exportReading() {
    const data = { format: 'gnss-research-reading', version: 2, exported_at: new Date().toISOString(), saved: reading.saved, read: reading.read };
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = 'research-reading-' + new Date().toISOString().slice(0, 10) + '.json';
    document.body.appendChild(link);
    link.click();
    link.remove();
    setTimeout(function () { URL.revokeObjectURL(url); }, 1000);
    toast('已导出阅读数据；可在另一台设备导入。');
  }

  async function importReading(input) {
    const file = input.files[0];
    if (!file) return;
    try {
      if (file.size > 2 * 1024 * 1024) throw new Error('文件过大；请使用本站导出的 JSON。');
      const value = JSON.parse(await file.text());
      if (value.format !== 'gnss-research-reading' || value.version !== 2) throw new Error('不是本站支持的阅读文件格式。');
      const next = validReading(value);
      next.saved = Array.from(new Set(reading.saved.concat(next.saved)));
      next.read = Array.from(new Set(reading.read.concat(next.read)));
      validReading(next);
      if (writeReading(next)) toast('导入完成，已与当前阅读记录合并。');
    } catch (error) {
      toast(error.message || '无法读取导入文件。');
    } finally {
      input.value = '';
    }
  }

  async function copyCitation() {
    const node = document.getElementById('citation-data');
    if (!node) return;
    try {
      const data = JSON.parse(node.textContent);
      const citation = data.authors.join(', ') + '. ' + data.title + '. arXiv:' + data.id + ', ' + data.year + '. ' + data.url;
      if (navigator.clipboard && window.isSecureContext) {
        await navigator.clipboard.writeText(citation);
      } else {
        const area = document.createElement('textarea');
        area.value = citation;
        area.style.position = 'fixed';
        area.style.opacity = '0';
        document.body.appendChild(area);
        area.select();
        const success = document.execCommand('copy');
        area.remove();
        if (!success) throw new Error('copy failed');
      }
      toast('已复制引用；正式引用前请核对原文信息。');
    } catch (error) { toast('无法写入剪贴板，请从原文页面复制引用。'); }
  }

  function filterArchive() {
    const area = document.querySelector('[data-archive]');
    if (!area) return;
    const month = document.querySelector('[data-archive-month]').value;
    const domain = document.querySelector('[data-archive-domain]').value;
    let count = 0;
    area.querySelectorAll('[data-archive-item]').forEach(function (node) {
      node.hidden = !(month === 'all' || node.dataset.month === month) || !(domain === 'all' || node.dataset.domains.split(' ').includes(domain));
      if (!node.hidden) count += 1;
    });
    area.querySelectorAll('[data-archive-section]').forEach(function (section) {
      section.hidden = !Array.from(section.querySelectorAll('[data-archive-item]')).some(function (item) { return !item.hidden; });
    });
    document.querySelector('[data-archive-empty]').hidden = count !== 0;
    document.querySelector('[data-archive-count]').textContent = '找到 ' + count + ' 期';
  }

  loadReading();
  syncReading();
  setLanguage(preference('gnss-reader-lang', 'zh'));
  setTheme(preference('gnss-radar-theme', window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'));
  if (browser) {
    restoreQuery();
    applyFilters(false);
    filters.addEventListener('submit', function (event) { event.preventDefault(); page = 1; applyFilters(); });
    filters.addEventListener('input', function () { page = 1; applyFilters(); });
    filters.addEventListener('change', function () { page = 1; applyFilters(); });
    window.addEventListener('popstate', function () { restoreQuery(); applyFilters(false); });
  }
  filterArchive();

  document.addEventListener('click', function (event) {
    const button = event.target.closest('button');
    if (button) {
      if (button.matches('[data-save], [data-read]')) {
        const key = button.hasAttribute('data-save') ? 'saved' : 'read';
        const id = button.dataset.save || button.dataset.read;
        if (!ID_PATTERN.test(id)) return;
        const next = { saved: reading.saved.slice(), read: reading.read.slice() };
        const has = next[key].includes(id);
        next[key] = has ? next[key].filter(function (value) { return value !== id; }) : next[key].concat(id);
        writeReading(next);
      } else if (button.hasAttribute('data-language')) {
        setLanguage(document.documentElement.dataset.lang === 'zh' ? 'en' : 'zh');
      } else if (button.hasAttribute('data-theme-toggle')) {
        setTheme(document.documentElement.dataset.theme === 'light' ? 'dark' : 'light');
      } else if (button.hasAttribute('data-menu')) {
        toggleMenu(!document.body.classList.contains('menu-open'));
      } else if (button.hasAttribute('data-reset') && browser) {
        resetFilters();
      } else if (button.hasAttribute('data-view') && browser) {
        view = button.dataset.view === 'list' ? 'list' : 'cards';
        savePreference('gnss-radar-view', view);
        applyFilters();
      } else if (button.hasAttribute('data-prev')) {
        changePage(-1);
      } else if (button.hasAttribute('data-next')) {
        changePage(1);
      } else if (button.hasAttribute('data-export-reading')) {
        exportReading();
      } else if (button.hasAttribute('data-copy-citation')) {
        copyCitation();
      }
    }
    if (document.body.classList.contains('menu-open') && !event.target.closest('.sidebar, [data-menu]')) toggleMenu(false);
  });

  document.addEventListener('change', function (event) {
    if (event.target.matches('[data-import-reading]')) importReading(event.target);
    if (event.target.matches('[data-archive-month], [data-archive-domain]')) filterArchive();
  });

  document.addEventListener('keydown', function (event) {
    if (event.key === 'Escape' && document.body.classList.contains('menu-open')) toggleMenu(false);
    if (event.key === 'Tab' && document.body.classList.contains('menu-open')) {
      const controls = Array.from(document.querySelectorAll('.sidebar a, .sidebar button')).filter(function (node) { return node.offsetParent !== null; });
      const first = controls[0];
      const last = controls[controls.length - 1];
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
    }
    if (event.key !== '/' || event.ctrlKey || event.metaKey || event.altKey || event.target.isContentEditable) return;
    if (/INPUT|TEXTAREA|SELECT/.test(document.activeElement.tagName)) return;
    const search = document.querySelector('[data-field="q"]') || document.getElementById('global-search');
    if (search) { event.preventDefault(); search.focus(); }
  });

  window.addEventListener('storage', function (event) {
    if (event.key !== READING_KEY) return;
    loadReading();
    syncReading();
    if (browser) applyFilters(false);
  });
})();
