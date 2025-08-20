document.addEventListener('DOMContentLoaded', function() {

    const csrfToken = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') || '';
    const notyf = new Notyf({
        duration: 3000,
        position: { x: 'right', y: 'top' },
        dismissible: true
    });

    // --- HTMX SETUP ---
    function setupHtmx() {
        document.body.addEventListener('htmx:configRequest', (event) => {
            if (event.detail.verb !== 'get') {
                event.detail.headers['X-CSRFToken'] = csrfToken;
            }
        });
        document.body.addEventListener('htmx:responseError', () => {
            notyf.error('Произошла ошибка сети. Попробуйте обновить страницу.');
        });
    }

    // --- POPUPS (MODAL/SLIDE-OVER) LOGIC ---
    function initPopups() {
        const closePopup = (overlay) => {
            if (overlay && overlay.classList.contains('show')) {
                overlay.classList.remove('show');
            }
        };

        document.body.addEventListener('click', event => {
            const overlay = event.target.closest('.modal-overlay, .slide-over-overlay');
            if (event.target.closest('.modal-close, .slide-over-close') || event.target === overlay) {
                event.preventDefault();
                closePopup(overlay);
            }
        });

        document.addEventListener('keydown', e => {
            if (e.key === 'Escape') {
                document.querySelectorAll('.modal-overlay.show, .slide-over-overlay.show').forEach(closePopup);
            }
        });
    }
    
    // --- SIDEBAR LOGIC (НОВАЯ, ПРОСТАЯ ВЕРСИЯ) ---
    function applySidebarState() {
        const body = document.body;
        if (!body) return;
        const isCollapsed = localStorage.getItem('sidebarCollapsed') === 'true';
        body.classList.toggle('sidebar-collapsed', isCollapsed);

        if (body.classList.contains('sidebar-collapsed-init')) {
           body.classList.remove('sidebar-collapsed-init');
        }
    }
    
    function initSidebarBehavior() {
        document.body.addEventListener('click', function(event) {
            const isDesktop = () => window.innerWidth > 992;
            const collapseBtn = event.target.closest('#sidebar-collapse-btn');
            const expandBtn = event.target.closest('#sidebar-expand-btn');

            if (collapseBtn && isDesktop()) {
                const isCollapsed = document.body.classList.contains('sidebar-collapsed');
                localStorage.setItem('sidebarCollapsed', String(!isCollapsed));
                applySidebarState();
            } else if (expandBtn) {
                if (isDesktop()) {
                    localStorage.setItem('sidebarCollapsed', 'false');
                    applySidebarState();
                } else {
                    document.body.classList.add('sidebar-mobile-open');
                }
            }
            
            // Закрытие мобильного меню по клику на контент
            const contentWrapper = event.target.closest('#content-wrapper');
            if (contentWrapper && document.body.classList.contains('sidebar-mobile-open')) {
                 document.body.classList.remove('sidebar-mobile-open');
            }
        });
        window.addEventListener('resize', applySidebarState);
    }
    
    // --- ДРУГИЕ КОМПОНЕНТЫ (KANBAN, EXPORT) ---
    // Эти функции остались такими же, но с защитой от ошибок
    function initializeSortable() {
        const kanbanColumns = document.querySelectorAll('.kanban-column-body');
        if (kanbanColumns.length === 0) return;

        kanbanColumns.forEach(column => {
            if (Sortable.get(column)) Sortable.get(column).destroy();
            new Sortable(column, { group: 'kanban', animation: 150, ghostClass: 'kanban-card-ghost', onEnd: async (evt) => {
                if (evt.from === evt.to && evt.oldIndex === evt.newIndex) return;
                const card = evt.item;
                const quoteId = card.dataset.id;
                const newStatus = evt.to.closest('.kanban-column').dataset.status;
                try {
                    const response = await fetch('/admin/api/quoterequests/update-status', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken },
                        body: JSON.stringify({ id: parseInt(quoteId, 10), status: newStatus })
                    });
                    if (!response.ok) throw new Error('Server error');
                    notyf.success('Статус обновлен!');
                    htmx.trigger('#kanban-board-container', 'updateKanban');
                } catch (error) {
                    evt.from.insertBefore(card, evt.from.children[evt.oldIndex]);
                    notyf.error('Не удалось обновить статус.');
                }}
            });
        });
    }
    
    function setupExportLogic() {
        const listContent = document.getElementById('list-content');
        if (!listContent || !document.getElementById('export-selected-btn')) return;

        const updateButtonState = () => {
            const selectedIds = Array.from(listContent.querySelectorAll('.row-checkbox:checked')).map(cb => cb.value);
            const count = selectedIds.length;
            const exportBtn = document.getElementById('export-selected-btn');
            const exportBtnText = document.getElementById('export-btn-text');
            if (exportBtn) exportBtn.disabled = count === 0;
            if (exportBtnText) exportBtnText.textContent = count > 0 ? `Экспорт выбранных (${count})` : 'Экспорт выбранных';
        };
        
        listContent.addEventListener('change', (e) => {
            if (e.target.matches('.row-checkbox, #select-all-checkbox')) {
                if (e.target.id === 'select-all-checkbox') {
                    listContent.querySelectorAll('.row-checkbox').forEach(cb => { cb.checked = e.target.checked; });
                }
                updateButtonState();
            }
        });

        const exportBtn = document.getElementById('export-selected-btn');
        if (exportBtn && !exportBtn.dataset.listenerAttached) {
             exportBtn.addEventListener('click', () => {
                const ids = Array.from(listContent.querySelectorAll('.row-checkbox:checked')).map(cb => encodeURIComponent(cb.value)).join(',');
                if (ids) { window.location.href = `/admin/quoterequest/export/?ids=${ids}`; }
            });
            exportBtn.dataset.listenerAttached = 'true';
        }
        updateButtonState();
    }

    // --- ЕДИНАЯ ТОЧКА ИНИЦИАЛИЗАЦИИ ---
    function initializePage() {
        applySidebarState();
        initializeSortable();
        setupExportLogic();
    }

    // --- ЗАПУСК ---
    setupHtmx();
    initPopups();
    initSidebarBehavior(); // Устанавливаем обработчики кликов один раз
    initializePage(); // Первый запуск для текущей страницы
    
    // Пере-инициализация после каждого HTMX перехода
    document.body.addEventListener('htmx:afterSwap', () => {
        initializePage();
    });
});