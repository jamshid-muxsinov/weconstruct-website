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
            if (!overlay) return;
            overlay.classList.remove('show');
        };

        document.body.addEventListener('click', event => {
            const overlay = event.target.closest('.modal-overlay, .slide-over-overlay');
            const closeButton = event.target.closest('.modal-close, .slide-over-close');
            if (closeButton) {
                event.preventDefault();
                closePopup(closeButton.closest('.modal-overlay, .slide-over-overlay'));
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
        const collapseBtn = document.getElementById('sidebar-collapse-btn');
        const expandBtn = document.getElementById('sidebar-expand-btn');
        const body = document.body;

        if (!sidebar || !collapseBtn || !expandBtn) return;
        
        const isDesktop = () => window.innerWidth > 992;

        const applySidebarState = () => {
            if (!isDesktop()) {
                // On mobile, remove desktop classes
                body.classList.remove('sidebar-collapsed');
                sidebar.classList.remove('collapsed');
                return;
            }
            // On desktop, apply saved state
            const isCollapsed = localStorage.getItem('sidebarCollapsed') === 'true';
            body.classList.toggle('sidebar-collapsed', isCollapsed);
            sidebar.classList.toggle('collapsed', isCollapsed);
        };
        
        // Desktop Toggle
        const toggleDesktop = () => {
            const isCollapsed = body.classList.contains('sidebar-collapsed');
            localStorage.setItem('sidebarCollapsed', !isCollapsed);
            applySidebarState();
        };

        // Mobile Toggle
        const openMobile = () => body.classList.add('sidebar-mobile-open');
        const closeMobile = () => body.classList.remove('sidebar-mobile-open');
        
        collapseBtn.addEventListener('click', toggleDesktop);
        
        expandBtn.addEventListener('click', (e) => {
            if (isDesktop()) {
                toggleDesktop();
            } else {
                openMobile();
            }
        });
        
        // Close mobile sidebar on overlay click
        const contentWrapper = document.getElementById('content-wrapper');
        if(contentWrapper) {
            contentWrapper.addEventListener('click', () => {
                if(body.classList.contains('sidebar-mobile-open')) {
                    closeMobile();
                }
            });
        }
        
        // Initial setup and on resize
        applySidebarState();
        window.addEventListener('resize', applySidebarState);
    }
    
    // --- KANBAN DRAG & DROP ---
    function initializeSortable() {
        document.querySelectorAll('.kanban-column-body').forEach(column => {
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
                        notyf.success('Статус обновлен!');
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
        if (!listContent || !document.getElementById('export-selected-btn')) return;

        const updateButtonState = () => {
            const selectedIds = Array.from(listContent.querySelectorAll('.row-checkbox:checked')).map(cb => cb.value);
            const count = selectedIds.length;
            const exportBtn = document.getElementById('export-selected-btn');
            const exportBtnText = document.getElementById('export-btn-text');
            if(exportBtn) exportBtn.disabled = count === 0;
            if(exportBtnText) exportBtnText.textContent = count > 0 ? `Экспорт выбранных (${count})` : 'Экспорт выбранных';
        };
        
        listContent.addEventListener('change', (e) => {
            if(e.target.id === 'select-all-checkbox') {
                listContent.querySelectorAll('.row-checkbox').forEach(cb => { cb.checked = e.target.checked; });
            }
            updateButtonState();
        });

        const exportBtn = document.getElementById('export-selected-btn');
        if (exportBtn) {
            exportBtn.addEventListener('click', () => {
                const ids = Array.from(listContent.querySelectorAll('.row-checkbox:checked')).map(cb => cb.value).join(',');
                if (ids) window.location.href = `/admin/quoterequest/export/?ids=${ids}`;
            });
        }
        
        updateButtonState();
    }


    // --- INITIALIZATION ---
    function init() {
        setupHtmx();
        initPopups();
        initSidebar();
        initializeSortable();
        setupExportLogic();
    }

    init();

    // Re-initialize dynamic components after HTMX swaps
    document.body.addEventListener('htmx:afterSwap', (event) => {
        if (event.detail.target.id === 'modal-body-content') {
            document.getElementById('modal-overlay')?.classList.add('show');
        }
        if (event.detail.target.id === 'slide-over-content') {
            document.getElementById('slide-over-overlay')?.classList.add('show');
        }
        
        // Re-run initializers for dynamic content
        initializeSortable();
        setupExportLogic();
    });
});