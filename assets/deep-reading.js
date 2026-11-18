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
  const supportsDialog = dialog && typeof dialog.showModal === 'function';
  const printButton = reader.querySelector('[data-print-reading]');
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

  function imageState(image, state) {
    const graphic = image.closest('[data-original-graphic]');
    if (!graphic) return;
    graphic.dataset.imageState = state;
    graphic.querySelector('.dr-image-status').hidden = state === 'loaded';
    graphic.querySelector('[data-retry-original]').hidden = state !== 'error';
    graphic.querySelector('[data-image-message]').textContent = state === 'error'
      ? '原图暂未加载，可能是网络限制或图源暂时不可用。解说仍可阅读；可重试，或打开下方原图 / 原文链接。'
      : (graphic.hasAttribute('data-licensed-original') ? '正在加载本站授权转载的原图…' : '正在从 arXiv 加载原图…') + ' 若长时间未显示，可打开下方原图链接。';
    scheduleProgress();
  }

  function inspectImage(image) {
    imageState(image, image.complete ? (image.naturalWidth > 0 ? 'loaded' : 'error') : 'loading');
  }

  function originalSize(size) {
    const graphic = dialog.querySelector('[data-original-graphic]');
    if (!graphic) return;
    graphic.dataset.imageSize = size;
    dialog.querySelectorAll('[data-original-size]').forEach(function (button) {
      button.setAttribute('aria-pressed', String(button.dataset.originalSize === size));
    });
    const scroll = graphic.querySelector('.dr-original-scroll');
    scroll.scrollLeft = 0;
    scroll.scrollTop = 0;
  }

  function expandFigure(trigger) {
    const figure = trigger.closest('.dr-figure');
    if (!supportsDialog || !figure) return;
    figureReturn = trigger;
    const graphic = figure.querySelector('.dr-graphic').cloneNode(true);
    graphic.querySelectorAll('[id]').forEach(function (node) { node.removeAttribute('id'); });
    graphic.querySelectorAll('[data-expand-original]').forEach(function (node) { node.removeAttribute('data-expand-original'); });
    graphic.querySelectorAll('[data-original-image]').forEach(function (image) { image.loading = 'eager'; });
    dialog.querySelector('.dr-dialog-header strong').textContent = figure.querySelector('.dr-figure-heading strong').textContent;
    dialog.querySelector('[data-original-controls]').hidden = !graphic.matches('[data-original-graphic]');
    dialog.querySelector('.dr-viewer-body').replaceChildren(graphic);
    originalSize('fit');
    dialog.showModal();
    graphic.querySelectorAll('[data-original-image]').forEach(inspectImage);
  }

  function waitForImage(image) {
    image.loading = 'eager';
    if (image.complete) return Promise.resolve();
    return new Promise(function (resolve) {
      function done() {
        window.clearTimeout(timer);
        image.removeEventListener('load', done);
        image.removeEventListener('error', done);
        resolve();
      }
      const timer = window.setTimeout(done, 10000);
      image.addEventListener('load', done);
      image.addEventListener('error', done);
    });
  }

  async function printReading() {
    printButton.disabled = true;
    printButton.textContent = '正在准备原图…';
    try {
      const images = Array.from(article.querySelectorAll('[data-original-image]'));
      await Promise.all(images.map(waitForImage));
      images.filter(function (image) { return !image.complete; }).forEach(function (image) {
        image.closest('[data-original-graphic]').querySelector('[data-image-message]').textContent = '原图尚未加载完成，打印可能缺图；请通过原图链接查看，或稍后重试。';
      });
      window.print();
    } finally {
      printButton.disabled = false;
      printButton.textContent = '打印 / 存 PDF';
    }
  }

  reader.querySelectorAll('[data-chart-controls]').forEach(function (node) { node.hidden = false; });
  printButton.hidden = false;
  progress.hidden = false;
  reader.addEventListener('load', function (event) {
    if (event.target.matches && event.target.matches('[data-original-image]')) inspectImage(event.target);
  }, true);
  reader.addEventListener('error', function (event) {
    if (event.target.matches && event.target.matches('[data-original-image]')) imageState(event.target, 'error');
  }, true);
  reader.querySelectorAll('[data-original-image]').forEach(inspectImage);
  if (supportsDialog) {
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
    const expand = event.target.closest('[data-expand-figure], [data-expand-original]');
    if (expand && supportsDialog) {
      event.preventDefault();
      expandFigure(expand);
    }
    if (event.target.closest('[data-close-figure]')) dialog.close();
    const size = event.target.closest('[data-original-size]');
    if (size) originalSize(size.dataset.originalSize);
    const retry = event.target.closest('[data-retry-original]');
    if (retry) {
      const image = retry.closest('[data-original-graphic]').querySelector('[data-original-image]');
      imageState(image, 'loading');
      image.loading = 'eager';
      image.src = image.getAttribute('src');
    }
    const scope = event.target.closest('[data-result-scope]');
    if (scope) {
      const chart = scope.closest('[data-result-chart]');
      chart.querySelectorAll('[data-result-scope]').forEach(function (button) {
        button.setAttribute('aria-pressed', String(button === scope));
      });
      updateChart(chart);
    }
    if (event.target.closest('.dr-mobile-toc a')) reader.querySelector('.dr-mobile-toc').open = false;
    if (event.target.closest('[data-print-reading]')) printReading();
  });
  reader.addEventListener('change', function (event) {
    if (event.target.matches('[data-result-metric]')) updateChart(event.target.closest('[data-result-chart]'));
  });
  reader.addEventListener('toggle', scheduleProgress, true);
  window.addEventListener('scroll', scheduleProgress, { passive: true });
  window.addEventListener('resize', scheduleProgress);
  window.addEventListener('load', scheduleProgress);
  window.addEventListener('beforeprint', function () {
    article.querySelectorAll('[data-original-image]').forEach(function (image) { image.loading = 'eager'; });
    reader.querySelectorAll('details').forEach(function (node) {
      if (node.dataset.printWasOpen === undefined) node.dataset.printWasOpen = String(node.open);
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
