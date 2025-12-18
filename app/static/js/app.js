function refreshDatasetSection() {
  const form = document.getElementById('filters-form');
  const container = document.getElementById('dataset-content');
  if (!form || !container) return;
  const params = new URLSearchParams(new FormData(form));
  const url = '/dataset' + (params.toString() ? `?${params.toString()}` : '');
  fetch(url, { headers: { 'HX-Request': 'true' } })
    .then((res) => res.text())
    .then((html) => {
      container.innerHTML = html;
      attachInteractions();
    });
}

function attachInteractions() {
  document.querySelectorAll('[data-sortable="tags"]').forEach((el) => {
    if (el.dataset.bound === 'true') return;
    el.dataset.bound = 'true';
    Sortable.create(el, {
      animation: 150,
      onEnd: () => {
        const imageId = el.dataset.imageId;
        const tags = Array.from(el.querySelectorAll('[data-tag-value]')).map((li) => li.dataset.tagValue);
        fetch(`/api/image/${imageId}/ops`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ type: 'reorder', tags }),
        }).then(() => {
          const notice = document.getElementById('reorder-status');
          if (notice) {
            notice.textContent = 'Order staged';
          }
        });
      },
    });
  });
}

document.addEventListener('DOMContentLoaded', attachInteractions);
document.body.addEventListener('htmx:afterSwap', attachInteractions);

document.body.addEventListener('click', (event) => {
  const toggleButton = event.target.closest('[data-toggle-target]');
  if (toggleButton) {
    const target = document.querySelector(toggleButton.dataset.toggleTarget || '');
    if (target) {
      const showLabel = toggleButton.dataset.toggleLabelShow || 'Show';
      const hideLabel = toggleButton.dataset.toggleLabelHide || 'Hide';
      const isHidden = target.hasAttribute('hidden');
      if (isHidden) {
        target.removeAttribute('hidden');
        target.classList.remove('is-hidden');
        toggleButton.textContent = hideLabel;
        toggleButton.setAttribute('aria-expanded', 'true');
      } else {
        target.setAttribute('hidden', '');
        target.classList.add('is-hidden');
        toggleButton.textContent = showLabel;
        toggleButton.setAttribute('aria-expanded', 'false');
      }
    }
    return;
  }

  const targetButton = event.target.closest('#choose-folder');
  if (targetButton) {
    const rel = targetButton.dataset.rel || '';
    const hidden = document.getElementById('selected-rel');
    if (hidden) {
      hidden.value = rel;
    }
    const label = document.getElementById('selected-path-label');
    if (label) {
      const rootLabel = hidden?.dataset.rootLabel || 'training (root)';
      label.textContent = rel || rootLabel;
    }
  }
});

document.body.addEventListener('htmx:afterRequest', (event) => {
  const xhr = event.detail && event.detail.xhr;
  if (!xhr) return;
  const url = xhr.responseURL || '';
  if (url.includes('/api/ops/bulk')) {
    const target = document.getElementById('bulk-result');
    if (target) {
      try {
        const data = JSON.parse(xhr.responseText);
        target.textContent = `Affected ${data.affected_images} images`;
      } catch (e) {
        target.textContent = 'Bulk edit staged';
      }
    }
  }
  if (url.includes('/api/dataset/load')) {
    const target = document.getElementById('load-result');
    if (target) {
      try {
        const data = JSON.parse(xhr.responseText);
        target.textContent = `Loaded ${data.image_count} images`;
      } catch (e) {
        target.textContent = 'Dataset loaded';
      }
    }
  }
});
