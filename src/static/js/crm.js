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

    // --- SIDEBAR LOGIC (SIMPLE & FINAL VERSION) ---
    function initSidebar() {
        const sidebar = document.getElementById('sidebar');
        const collapseBtn = document.getElementById('sidebar-collapse-btn');
        const expandBtn = document.getElementById('sidebar-expand-btn');
        const body = document.body;
        const contentWrapper = document.getElementById('content-wrapper');

        if (!sidebar || !collapseBtn || !expandBtn || !contentWrapper) return;
        
        const isDesktop = () => window.innerWidth > 992;

        // Initialize sidebar width persistence
        const initSidebarWidth = () => {
            const savedWidth = localStorage.getItem('sidebarWidth');
            if (savedWidth && !body.classList.contains('sidebar-collapsed') && sidebar) {
                sidebar.style.setProperty('--sidebar-width', `${savedWidth}px`);
                sidebar.style.width = `${savedWidth}px`;
            }
            
            // Add resize observer to save new width when user resizes
            if (window.ResizeObserver && sidebar) {
                const resizeObserver = new ResizeObserver(entries => {
                    for (let entry of entries) {
                        const newWidth = Math.round(entry.contentRect.width);
                        if (newWidth >= 200 && newWidth <= 400 && !body.classList.contains('sidebar-collapsed') && sidebar) {
                            localStorage.setItem('sidebarWidth', newWidth.toString());
                            sidebar.style.setProperty('--sidebar-width', `${newWidth}px`);
                        }
                    }
                });
                resizeObserver.observe(sidebar);
            }
        };

        const applySidebarState = () => {
            // Remove init class after first run
            body.classList.remove('sidebar-collapsed-init');

            if (!isDesktop()) {
                // On mobile, ensure desktop classes are removed
                body.classList.remove('sidebar-collapsed');
                if (sidebar) sidebar.classList.remove('collapsed');
                return;
            }
            // On desktop, apply saved state
            const isCollapsed = localStorage.getItem('sidebarCollapsed') === 'true';
            body.classList.toggle('sidebar-collapsed', isCollapsed);
            if (sidebar) sidebar.classList.toggle('collapsed', isCollapsed);
            
            // Apply saved width if not collapsed
            if (!isCollapsed && sidebar) {
                const savedWidth = localStorage.getItem('sidebarWidth');
                if (savedWidth) {
                    sidebar.style.setProperty('--sidebar-width', `${savedWidth}px`);
                    sidebar.style.width = `${savedWidth}px`;
                }
            }
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
        
        // Initialize width management on load
        initSidebarWidth();
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
        
        initializeSortable();
        setupExportLogic();
    });
});