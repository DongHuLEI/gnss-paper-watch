(function () {
  'use strict';

  const reader = document.querySelector('[data-deep-reader]');
  if (!reader) return;
  const article = reader.querySelector('.dr-body');
  const sections = Array.from(reader.querySelectorAll('[data-reading-section]'));
  const progress = reader.querySelector('[data-reading-progress]');
  const meter = progress.querySelector('progress');
  const percent = reader.querySelector('[data-reading-percent]');
  const dialog = reader.querySelector('dialog');
  let scheduled = false;
  let figureReturn;

  function updateProgress() {
    const rect = article.getBoundingClientRect();
    const distance = Math.max(1, rect.height - window.innerHeight + 110);
    const value = Math.max(0, Math.min(100, Math.round((110 - rect.top) / distance * 100)));
    meter.value = value;
    percent.textContent = '阅读进度 ' + value + '%';
    let active = sections[0].id;
    sections.forEach(function (section) {
      if (section.getBoundingClientRect().top <= 150) active = section.id;
    });
    reader.querySelectorAll('.dr-toc nav a').forEach(function (link) {
      if (link.hash === '#' + active) link.setAttribute('aria-current', 'location');
      else link.removeAttribute('aria-current');
    });
    scheduled = false;
  }

  function scheduleProgress() {
    if (!scheduled) {
      scheduled = true;
      window.requestAnimationFrame(updateProgress);
    }
  }

  function updateChart(chart) {
    const metric = chart.querySelector('[data-result-metric]');
    const scope = chart.querySelector('[data-result-scope][aria-pressed="true"]').dataset.resultScope;
    chart.querySelectorAll('[data-result-view]').forEach(function (view) {
      view.hidden = view.dataset.resultView !== metric.value + '-' + scope;
    });
    chart.querySelector('[data-chart-announcement]').textContent = '当前：' + metric.options[metric.selectedIndex].text + ' · ' + (scope === 'average' ? '1–24 h 全时效平均' : '24 h 单点') + '，越低越好。';
    scheduleProgress();
  }

  reader.querySelectorAll('[data-chart-controls]').forEach(function (node) { node.hidden = false; });
  reader.querySelector('[data-print-reading]').hidden = false;
  progress.hidden = false;
  if (dialog && typeof dialog.showModal === 'function') {
    reader.querySelectorAll('[data-expand-figure]').forEach(function (node) { node.hidden = false; });
    dialog.addEventListener('close', function () {
      dialog.querySelector('.dr-viewer-body').replaceChildren();
      if (figureReturn) figureReturn.focus({ preventScroll: true });
    });
    dialog.addEventListener('click', function (event) {
      if (event.target !== dialog) return;
      const bounds = dialog.getBoundingClientRect();
      if (event.clientX < bounds.left || event.clientX > bounds.right || event.clientY < bounds.top || event.clientY > bounds.bottom) dialog.close();
    });
  }

  reader.addEventListener('click', function (event) {
    const expand = event.target.closest('[data-expand-figure]');
    if (expand) {
      figureReturn = expand;
      const figure = expand.closest('.dr-figure');
      const graphic = figure.querySelector('.dr-graphic').cloneNode(true);
      graphic.querySelectorAll('[id]').forEach(function (node) { node.removeAttribute('id'); });
      dialog.querySelector('.dr-dialog-header strong').textContent = figure.querySelector('.dr-figure-heading strong').textContent;
      dialog.querySelector('.dr-viewer-body').replaceChildren(graphic);
      dialog.showModal();
    }
    if (event.target.closest('[data-close-figure]')) dialog.close();
    const scope = event.target.closest('[data-result-scope]');
    if (scope) {
      const chart = scope.closest('[data-result-chart]');
      chart.querySelectorAll('[data-result-scope]').forEach(function (button) {
        button.setAttribute('aria-pressed', String(button === scope));
      });
      updateChart(chart);
    }
    if (event.target.closest('.dr-mobile-toc a')) reader.querySelector('.dr-mobile-toc').open = false;
    if (event.target.closest('[data-print-reading]')) window.print();
  });
  reader.addEventListener('change', function (event) {
    if (event.target.matches('[data-result-metric]')) updateChart(event.target.closest('[data-result-chart]'));
  });
  reader.addEventListener('toggle', scheduleProgress, true);
  window.addEventListener('scroll', scheduleProgress, { passive: true });
  window.addEventListener('resize', scheduleProgress);
  window.addEventListener('load', scheduleProgress);
  window.addEventListener('beforeprint', function () {
    reader.querySelectorAll('details').forEach(function (node) {
      node.dataset.printWasOpen = String(node.open);
      node.open = true;
    });
  });
  window.addEventListener('afterprint', function () {
    reader.querySelectorAll('details[data-print-was-open]').forEach(function (node) {
      node.open = node.dataset.printWasOpen === 'true';
      delete node.dataset.printWasOpen;
    });
    scheduleProgress();
  });
  if (document.fonts && document.fonts.ready) document.fonts.ready.then(scheduleProgress);
  updateProgress();
})();
