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

    // --- POPUP (MODAL/SLIDE-OVER) LOGIC ---
    function initPopups() {
        const closePopup = (overlay) => {
            if (overlay && overlay.classList.contains('show')) {
                overlay.classList.remove('show');
            }
        };

        document.body.addEventListener('click', event => {
            const overlay = event.target.closest('.modal-overlay, .slide-over-overlay');
            if (event.target.closest('.modal-close, .slide-over-close')) {
                event.preventDefault();
                closePopup(overlay);
            } else if (overlay && event.target === overlay) {
                closePopup(overlay);
            }
        });

        document.addEventListener('keydown', e => {
            if (e.key === 'Escape') {
                document.querySelectorAll('.modal-overlay.show, .slide-over-overlay.show').forEach(closePopup);
            }
        });
        
        document.body.addEventListener('closeModal', () => closePopup(document.getElementById('modal-overlay')));
        document.body.addEventListener('closeSlideOver', () => closePopup(document.getElementById('slide-over-overlay')));
    }

    // --- SIDEBAR LOGIC ---
    function initSidebar() {
        const sidebar = document.getElementById('sidebar');
        if (!sidebar) return; // Guard clause

        const collapseBtn = document.getElementById('sidebar-collapse-btn');
        const expandBtn = document.getElementById('sidebar-expand-btn');
        const body = document.body;
        const contentWrapper = document.getElementById('content-wrapper');

        if (!collapseBtn || !expandBtn || !contentWrapper) return;
        
        const isDesktop = () => window.innerWidth > 992;

        const applySidebarState = () => {
            body.classList.remove('sidebar-collapsed-init');
            if (!isDesktop()) {
                body.classList.remove('sidebar-collapsed');
                return;
            }
            const isCollapsed = localStorage.getItem('sidebarCollapsed') === 'true';
            body.classList.toggle('sidebar-collapsed', isCollapsed);
        };
        
        collapseBtn.addEventListener('click', () => {
            if (isDesktop()) {
                const isCollapsed = body.classList.contains('sidebar-collapsed');
                localStorage.setItem('sidebarCollapsed', !isCollapsed);
                applySidebarState();
            }
        });
        
        expandBtn.addEventListener('click', () => {
            if (isDesktop()) {
                localStorage.setItem('sidebarCollapsed', false);
                applySidebarState();
            } else {
                body.classList.add('sidebar-mobile-open');
            }
        });
        
        contentWrapper.addEventListener('click', () => {
            if (body.classList.contains('sidebar-mobile-open')) {
                body.classList.remove('sidebar-mobile-open');
            }
        });
        
        window.addEventListener('resize', applySidebarState);
        // Initial call
        applySidebarState();
    }
    
    // --- KANBAN DRAG & DROP ---
    function initializeSortable() {
        const kanbanColumns = document.querySelectorAll('.kanban-column-body');
        if (kanbanColumns.length === 0) return; // Guard clause: only run on Kanban page

        kanbanColumns.forEach(column => {
            if (Sortable.get(column)) { Sortable.get(column).destroy(); }
            new Sortable(column, {
                group: 'kanban',
                animation: 150,
                ghostClass: 'kanban-card-ghost',
                onEnd: async (evt) => {
                    if (evt.from === evt.to && evt.oldIndex === evt.newIndex) return;
                    
                    const card = evt.item;
                    const quoteId = card.dataset.id;
                    const newStatus = evt.to.closest('.kanban-column').dataset.status;

                    try {
                        const response = await fetch('/admin/api/quoterequests/update-status', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken },
                            body: JSON.stringify({ id: parseInt(quoteId), status: newStatus })
                        });
                        if (!response.ok) throw new Error('Server response was not ok.');
                        htmx.trigger('#kanban-board-container', 'updateKanban');
                    } catch (error) {
                        evt.from.insertBefore(card, evt.from.children[evt.oldIndex]);
                        notyf.error('Не удалось обновить статус.');
                    }
                }
            });
        });
    }
    
    // --- EXPORT LOGIC ---
    function setupExportLogic() {
        const listContent = document.getElementById('list-content');
        const exportBtn = document.getElementById('export-selected-btn');
        if (!listContent || !exportBtn) return; // Guard clause: only run on quote list page

        const updateButtonState = () => {
            const selectedIds = Array.from(listContent.querySelectorAll('.row-checkbox:checked')).map(cb => cb.value);
            const count = selectedIds.length;
            const exportBtnText = document.getElementById('export-btn-text');
            exportBtn.disabled = count === 0;
            if(exportBtnText) exportBtnText.textContent = count > 0 ? `Экспорт выбранных (${count})` : 'Экспорт выбранных';
        };
        
        listContent.addEventListener('change', (e) => {
            if(e.target.id === 'select-all-checkbox') {
                listContent.querySelectorAll('.row-checkbox').forEach(cb => { cb.checked = e.target.checked; });
            }
            updateButtonState();
        });

        exportBtn.addEventListener('click', () => {
            const ids = Array.from(listContent.querySelectorAll('.row-checkbox:checked')).map(cb => cb.value).join(',');
            if (ids) window.location.href = `/admin/quoterequest/export/?ids=${ids}`;
        });
        
        updateButtonState();
    }


    // --- INITIALIZATION ---
    function init() {
        setupHtmx();
        initPopups();
        initSidebar();
        
        // --- ИСПРАВЛЕНИЕ ЗДЕСЬ ---
        // Вызываем функции только если мы на нужной странице
        initializeSortable();
        setupExportLogic();
    }

    init();

    // Re-initialize dynamic components after HTMX swaps
    document.body.addEventListener('htmx:afterSwap', (event) => {
        if (event.detail.target.id === 'modal-body-content') {
            const modal = document.getElementById('modal-overlay');
            if(modal) modal.classList.add('show');
        }
        if (event.detail.target.id === 'slide-over-content') {
            const slideOver = document.getElementById('slide-over-overlay');
            if(slideOver) slideOver.classList.add('show');
        }
        
        // --- ИСПРАВЛЕНИЕ ЗДЕСЬ ---
        // Повторяем те же проверки после подгрузки контента
        initializeSortable();
        setupExportLogic();
    });
});