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

    // --- POPUPS (MODAL/SLIDE-OVER) ---
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
    
    // --- SIDEBAR LOGIC (НОВАЯ, НАДЕЖНАЯ ВЕРСИЯ) ---
    function initSidebar() {
        // Эта функция устанавливает состояние сайдбара
        const applyState = () => {
            const isCollapsed = localStorage.getItem('sidebarCollapsed') === 'true';
            document.body.classList.toggle('sidebar-collapsed', isCollapsed);
        };
        
        // Устанавливаем обработчики кликов ОДИН РАЗ
        document.body.addEventListener('click', function(event) {
            const isDesktop = () => window.innerWidth > 992;
            const collapseBtn = event.target.closest('#sidebar-collapse-btn');
            const expandBtn = event.target.closest('#sidebar-expand-btn');
            const contentWrapper = event.target.closest('#content-wrapper');

            if (collapseBtn && isDesktop()) {
                const isCollapsed = document.body.classList.contains('sidebar-collapsed');
                localStorage.setItem('sidebarCollapsed', String(!isCollapsed));
                applyState();
            } else if (expandBtn) {
                if (isDesktop()) {
                    localStorage.setItem('sidebarCollapsed', 'false');
                    applyState();
                } else {
                    document.body.classList.add('sidebar-mobile-open');
                }
            } else if (contentWrapper && document.body.classList.contains('sidebar-mobile-open')) {
                 document.body.classList.remove('sidebar-mobile-open');
            }
        });

        // Применяем состояние при изменении размера окна
        window.addEventListener('resize', applyState);

        // Первый запуск для текущей страницы
        applyState();
    }
    
    // --- ДРУГИЕ КОМПОНЕНТЫ ---
    function initializeSortable() {
        const kanbanColumns = document.querySelectorAll('.kanban-column-body');
        if (!kanbanColumns.length) return;
        kanbanColumns.forEach(column => {
            if (Sortable.get(column)) Sortable.get(column).destroy();
            new Sortable(column, { group: 'kanban', animation: 150, ghostClass: 'kanban-card-ghost', onEnd: async (evt) => {
                const card = evt.item;
                const quoteId = card.dataset.id;
                const newStatus = evt.to.closest('.kanban-column').dataset.status;
                try {
                    await fetch('/admin/api/quoterequests/update-status', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken },
                        body: JSON.stringify({ id: parseInt(quoteId, 10), status: newStatus })
                    });
                } catch (error) {
                    evt.from.insertBefore(card, evt.from.children[evt.oldIndex]);
                    notyf.error('Не удалось обновить статус.');
                }
            }});
        });
    }
    
    function setupExportLogic() {
        const listContent = document.getElementById('list-content');
        if (!listContent || !document.getElementById('export-selected-btn')) return;

        const updateButtonState = () => {
            const checked = listContent.querySelectorAll('.row-checkbox:checked');
            const exportBtn = document.getElementById('export-selected-btn');
            const exportBtnText = document.getElementById('export-btn-text');
            if (exportBtn) exportBtn.disabled = checked.length === 0;
            if (exportBtnText) exportBtnText.textContent = checked.length > 0 ? `Экспорт выбранных (${checked.length})` : 'Экспорт выбранных';
        };
        
        listContent.addEventListener('change', (e) => {
            if (e.target.matches('#select-all-checkbox')) {
                listContent.querySelectorAll('.row-checkbox').forEach(cb => { cb.checked = e.target.checked; });
            }
            updateButtonState();
        });

        document.getElementById('export-selected-btn').addEventListener('click', () => {
            const ids = Array.from(listContent.querySelectorAll('.row-checkbox:checked')).map(cb => cb.value).join(',');
            if (ids) window.location.href = `/admin/quoterequest/export/?ids=${ids}`;
        });
        updateButtonState();
    }

    // --- ГЛАВНЫЙ ИНИЦИАЛИЗАТОР ---
    function initializePageComponents() {
        initializeSortable();
        setupExportLogic();
    }

    // --- ЗАПУСК ВСЕГО ---
    setupHtmx();
    initPopups();
    initSidebar();
    initializePageComponents();

    // --- КЛЮЧЕВОЕ РЕШЕНИЕ ПРОБЛЕМЫ ДЕРГАНИЯ ---
    document.body.addEventListener('htmx:beforeSwap', function (evt) {
        // Если HTMX собирается заменить <body>
        if (evt.detail.target === document.body) {
            // Проверяем, должен ли сайдбар быть свернут
            const isCollapsed = localStorage.getItem('sidebarCollapsed') === 'true';
            if (isCollapsed) {
                // Добавляем класс 'sidebar-collapsed' ПРЯМО В HTML-СТРОКУ нового body
                // до того, как он будет вставлен на страницу.
                evt.detail.newContent = evt.detail.newContent.replace('<body', '<body class="sidebar-collapsed"');
            }
        }
    });

    document.body.addEventListener('htmx:afterSwap', () => {
        // После вставки нового body, просто запускаем инициализацию компонентов для этой страницы
        initializePageComponents();
    });
});