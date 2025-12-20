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
      applyStoredTogglePreferences();
      attachInteractions();
    });
}

function attachInteractions() {
  document.querySelectorAll('[data-sortable="tags"]').forEach((el) => {
    if (el.dataset.bound === 'true') return;
    el.dataset.bound = 'true';
    Sortable.create(el, {
      animation: 150,
      handle: '.drag-handle',
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

function setToggleVisibility(target, button, shouldShow, storageKey) {
  const showLabel = button.dataset.toggleLabelShow || 'Show';
  const hideLabel = button.dataset.toggleLabelHide || 'Hide';
  if (shouldShow) {
    target.removeAttribute('hidden');
    target.classList.remove('is-hidden');
    button.textContent = hideLabel;
    button.setAttribute('aria-expanded', 'true');
  } else {
    target.setAttribute('hidden', '');
    target.classList.add('is-hidden');
    button.textContent = showLabel;
    button.setAttribute('aria-expanded', 'false');
  }
  if (storageKey) {
    localStorage.setItem(`toggle:${storageKey}`, shouldShow ? 'visible' : 'hidden');
  }
}

function applyStoredTogglePreferences() {
  document.querySelectorAll('[data-toggle-target][data-toggle-storage-key]').forEach((btn) => {
    const target = document.querySelector(btn.dataset.toggleTarget || '');
    if (!target) return;
    const storageKey = btn.dataset.toggleStorageKey;
    const stored = localStorage.getItem(`toggle:${storageKey}`);
    if (stored === 'hidden') {
      setToggleVisibility(target, btn, false, storageKey);
    } else if (stored === 'visible') {
      setToggleVisibility(target, btn, true, storageKey);
    }
  });
}

function handleCompletionToggle(event) {
  const xhr = event.detail && event.detail.xhr;
  if (!xhr) return;
  let data;
  try {
    data = JSON.parse(xhr.responseText || '{}');
  } catch (e) {
    return;
  }
  if (typeof data.is_complete === 'undefined') return;
  const isComplete = Boolean(data.is_complete);

  const form = event.target.closest('form');
  if (form) {
    const toggleInput = form.querySelector('input[name="complete"]');
    if (toggleInput) {
      toggleInput.value = (!isComplete).toString();
    }
    const button = form.querySelector('button[type="submit"]');
    if (button) {
      button.textContent = isComplete ? 'Mark incomplete' : 'Mark complete';
    }
  }

  const badge = document.getElementById('completion-badge');
  if (badge) {
    badge.textContent = isComplete ? 'Complete' : 'Incomplete';
    badge.classList.toggle('success', isComplete);
  }

  const hintsComplete = document.getElementById('hints-complete');
  const hintsActive = document.getElementById('hints-active');
  if (hintsComplete && hintsActive) {
    if (isComplete) {
      hintsComplete.removeAttribute('hidden');
      hintsActive.setAttribute('hidden', '');
    } else {
      hintsActive.removeAttribute('hidden');
      hintsComplete.setAttribute('hidden', '');
    }
  }
}

document.addEventListener('DOMContentLoaded', () => {
  applyStoredTogglePreferences();
  attachInteractions();
});
document.body.addEventListener('htmx:afterSwap', () => {
  applyStoredTogglePreferences();
  attachInteractions();
});

document.body.addEventListener('click', (event) => {
  const editButton = event.target.closest('.edit-tag-btn');
  if (editButton) {
    const currentValue = editButton.dataset.currentValue || '';
    const imageId = editButton.dataset.imageId;
    const index = editButton.dataset.index;
    const newValue = window.prompt('Edit tag', currentValue);
    if (newValue === null) return;
    const trimmed = newValue.trim();
    if (!trimmed) return;

    fetch(`/api/image/${imageId}/ops`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ type: 'edit', index, old_tag: currentValue, new_tag: trimmed }),
    }).then(() => {
      window.location.reload();
    });
    return;
  }

  const toggleButton = event.target.closest('[data-toggle-target]');
  if (toggleButton) {
    const target = document.querySelector(toggleButton.dataset.toggleTarget || '');
    if (target) {
      const storageKey = toggleButton.dataset.toggleStorageKey;
      const isHidden = target.hasAttribute('hidden');
      setToggleVisibility(target, toggleButton, isHidden, storageKey);
    }
    return;
  }

  const copyButton = event.target.closest('[data-copy-text]');
  if (copyButton) {
    const text = copyButton.dataset.copyText || '';
    if (!text) return;
    if (!navigator.clipboard) return;
    const originalLabel = copyButton.dataset.originalLabel || copyButton.textContent;
    copyButton.dataset.originalLabel = originalLabel;
    navigator.clipboard.writeText(text).then(() => {
      copyButton.textContent = 'Copied';
      setTimeout(() => {
        copyButton.textContent = copyButton.dataset.originalLabel || originalLabel;
      }, 1500);
    });
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
