(() => {
  function initNavbarArrows() {
    const tabsGrid = document.querySelector('.md-tabs .md-grid');
    const tabsList = tabsGrid?.querySelector('.md-tabs__list');
    if (!tabsGrid || !tabsList) return;

    if (tabsGrid.dataset.ergoArrowsReady === 'true') {
      updateArrows();
      return;
    }

    tabsGrid.dataset.ergoArrowsReady = 'true';
    tabsGrid.classList.add('ergo-tabs-nav');

    const prevBtn = document.createElement('button');
    prevBtn.type = 'button';
    prevBtn.className = 'ergo-tabs-arrow ergo-tabs-arrow--prev';
    prevBtn.setAttribute('aria-label', 'Ver abas anteriores');
    prevBtn.innerHTML =
      '<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="15 18 9 12 15 6"></polyline></svg>';

    const nextBtn = document.createElement('button');
    nextBtn.type = 'button';
    nextBtn.className = 'ergo-tabs-arrow ergo-tabs-arrow--next';
    nextBtn.setAttribute('aria-label', 'Ver próximas abas');
    nextBtn.innerHTML =
      '<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="9 18 15 12 9 6"></polyline></svg>';

    tabsGrid.insertBefore(prevBtn, tabsList);
    tabsGrid.appendChild(nextBtn);

    function updateArrows() {
      const maxScroll = Math.max(0, tabsList.scrollWidth - tabsList.clientWidth);
      const hasOverflow = maxScroll > 4;

      prevBtn.hidden = !hasOverflow;
      nextBtn.hidden = !hasOverflow;

      if (!hasOverflow) return;

      prevBtn.disabled = tabsList.scrollLeft <= 2;
      nextBtn.disabled = tabsList.scrollLeft >= maxScroll - 2;
    }

    const scrollStep = () => Math.max(200, Math.round(tabsList.clientWidth * 0.55));

    prevBtn.addEventListener('click', () => {
      tabsList.scrollBy({ left: -scrollStep(), behavior: 'smooth' });
    });

    nextBtn.addEventListener('click', () => {
      tabsList.scrollBy({ left: scrollStep(), behavior: 'smooth' });
    });

    tabsList.addEventListener('scroll', updateArrows, { passive: true });
    window.addEventListener('resize', updateArrows);

    const activeItem = tabsList.querySelector('.md-tabs__item--active');
    if (activeItem) {
      activeItem.scrollIntoView({ behavior: 'auto', block: 'nearest', inline: 'center' });
    }

    requestAnimationFrame(updateArrows);
  }

  if (typeof document$ !== 'undefined') {
    document$.subscribe(initNavbarArrows);
  } else if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initNavbarArrows);
  } else {
    initNavbarArrows();
  }
})();
