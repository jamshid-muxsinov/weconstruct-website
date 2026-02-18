/* --- src/static/js/admin-core.js --- */

(function () {
    const getCsrfToken = () => document.querySelector('meta[name="csrf-token"]')?.content || '';

    async function adminApiFetch(url, options = {}) {
        const method = (options.method || 'GET').toUpperCase();
        const headers = {
            ...(options.headers || {}),
        };

        if (method !== 'GET' && method !== 'HEAD') {
            headers['X-CSRFToken'] = headers['X-CSRFToken'] || getCsrfToken();
        }

        const controller = new AbortController();
        const timeoutMs = options.timeoutMs || 10000;
        const timeoutId = setTimeout(() => controller.abort(), timeoutMs);

        try {
            const response = await fetch(url, {
                ...options,
                headers,
                signal: controller.signal,
            });
            return response;
        } finally {
            clearTimeout(timeoutId);
        }
    }

    function showOfflineBanner() {
        if (document.getElementById('offline-banner')) return;
        const banner = document.createElement('div');
        banner.id = 'offline-banner';
        banner.textContent = 'Нет соединения с интернетом. Некоторые действия недоступны.';
        banner.style.cssText = [
            'position:fixed',
            'top:0',
            'left:0',
            'right:0',
            'z-index:9999',
            'padding:8px 12px',
            'text-align:center',
            'background:#b91c1c',
            'color:#fff',
            'font-size:14px',
            'font-weight:600',
        ].join(';');
        document.body.appendChild(banner);
    }

    function hideOfflineBanner() {
        document.getElementById('offline-banner')?.remove();
    }

    function runHtmxGet(url, targetSelector) {
        if (!url || !targetSelector || !window.htmx) return;
        window.htmx.ajax('GET', url, { target: targetSelector });
    }

    function bindDelegatedActions() {
        document.body.addEventListener('click', (event) => {
            if (event.target.closest('[data-stop-row-click]')) {
                event.stopPropagation();
                return;
            }

            const actionEl = event.target.closest('[data-action]');
            if (!actionEl) return;

            const action = actionEl.dataset.action;

            if (action === 'open-slide-over') {
                event.preventDefault();
                runHtmxGet(actionEl.dataset.url, actionEl.dataset.target || '#slide-over-content');
                return;
            }

            if (action === 'open-modal') {
                event.preventDefault();
                runHtmxGet(actionEl.dataset.url, actionEl.dataset.target || '#modal-body-content');
                return;
            }

            if (action === 'close-overlay') {
                event.preventDefault();
                const overlayId = actionEl.dataset.overlayId;
                if (overlayId && window.closeOverlay) window.closeOverlay(overlayId);
                return;
            }

            if (action === 'copy-text') {
                event.preventDefault();
                const text = actionEl.dataset.copyText || '';
                navigator.clipboard.writeText(text).then(() => {
                    if (window.notyf) window.notyf.success(actionEl.dataset.successMessage || 'Скопировано');
                }).catch(() => {
                    if (window.notyf) window.notyf.error('Не удалось скопировать');
                });
                return;
            }

            if (action === 'show-new-contact') {
                event.preventDefault();
                const block = document.getElementById('new-contact-fields');
                if (!block) return;
                block.style.display = 'block';
                const search = document.getElementById('contact-search');
                if (search) search.value = '';
                const results = document.getElementById('search-results');
                if (results) results.innerHTML = '';
                document.getElementById('new_contact_name')?.focus();
                return;
            }

            if (action === 'hide-new-contact') {
                event.preventDefault();
                const block = document.getElementById('new-contact-fields');
                if (block) block.style.display = 'none';
                const nameEl = document.getElementById('new_contact_name');
                const phoneEl = document.getElementById('new_contact_phone');
                if (nameEl) nameEl.value = '';
                if (phoneEl) phoneEl.value = '';
                return;
            }

            if (action === 'select-contact') {
                event.preventDefault();
                const contactId = actionEl.dataset.contactId;
                const contactLabel = actionEl.dataset.contactLabel;
                const contactIdEl = document.getElementById('contact_id');
                const searchEl = document.getElementById('contact-search');
                const results = document.getElementById('search-results');
                const block = document.getElementById('new-contact-fields');
                if (contactIdEl) contactIdEl.value = contactId || '';
                if (searchEl && contactLabel) searchEl.value = contactLabel;
                if (results) results.innerHTML = '';
                if (block) block.style.display = 'none';
                return;
            }

            if (action === 'navigate') {
                event.preventDefault();
                const url = actionEl.dataset.url;
                if (url) window.location.href = url;
            }
        });
    }

    window.adminApiFetch = adminApiFetch;

    document.addEventListener('DOMContentLoaded', () => {
        bindDelegatedActions();
        window.addEventListener('offline', showOfflineBanner);
        window.addEventListener('online', hideOfflineBanner);
        if (!navigator.onLine) showOfflineBanner();
    });
})();
