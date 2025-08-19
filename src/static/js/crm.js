document.addEventListener('DOMContentLoaded', function() {

    // --- Глобальная инициализация ---
    const csrfToken = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') || '';
    const notyf = new Notyf({
        duration: 3000,
        position: { x: 'right', y: 'top' },
        dismissible: true
    });

    // --- Настройка HTMX ---
    document.body.addEventListener('htmx:configRequest', (event) => {
        if (event.detail.verb !== 'get') {
            event.detail.headers['X-CSRFToken'] = csrfToken;
        }
    });
    document.body.addEventListener('htmx:responseError', () => {
        notyf.error('Произошла ошибка. Попробуйте обновить страницу.');
    });
    
    // --- Управление модальными окнами и сайд-оверами ---
    function initPopups() {
        const closePopup = (overlay) => {
            if (!overlay) return;
            overlay.classList.remove('show');
            setTimeout(() => {
                const content = overlay.querySelector('#modal-body-content, #slide-over-content');
                if (content) {
                    content.innerHTML = `<div class="modal-loading-placeholder"><i class='bx bx-loader-alt bx-spin'></i><span>Загрузка...</span></div>`;
                }
            }, 300);
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

    // --- Логика канбан-доски ---
    function initializeSortable() {
        document.querySelectorAll('.kanban-column-body').forEach(column => {
            if (Sortable.get(column)) { Sortable.get(column).destroy(); }
            new Sortable(column, {
                group: 'kanban',
                animation: 150,
                ghostClass: 'kanban-card-ghost',
                onEnd: async (evt) => {
                    if (evt.from === evt.to) return;

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
                        console.error('Failed to update status:', error);
                        // IMPORTANT: Revert move on error
                        evt.from.insertBefore(card, evt.from.children[evt.oldIndex]);
                        notyf.error('Не удалось обновить статус.');
                    }
                }
            });
        });
    }

    // --- ИСПРАВЛЕННАЯ ЛОГИКА САЙДБАРА ---
    function initSidebar() {
        const sidebar = document.getElementById('sidebar');
        if (!sidebar) return;

        const collapseBtn = document.getElementById('sidebar-collapse-btn');
        const expandBtn = document.getElementById('sidebar-expand-btn');
        const contentWrapper = document.getElementById('content-wrapper');

        // Logic for desktop (collapsing)
        const toggleDesktopSidebar = () => {
            const isCollapsed = document.body.classList.contains('sidebar-collapsed');
            localStorage.setItem('sidebarCollapsed', !isCollapsed);
            document.body.classList.toggle('sidebar-collapsed');
            sidebar.classList.toggle('collapsed');
        };

        // Logic for mobile (slide-out)
        const openMobileMenu = () => document.body.classList.add('sidebar-mobile-open');
        const closeMobileMenu = () => document.body.classList.remove('sidebar-mobile-open');
        
        // Apply initial state for desktop
        if (window.innerWidth > 992) {
            const isCollapsed = localStorage.getItem('sidebarCollapsed') === 'true';
            if (isCollapsed) {
                document.body.classList.add('sidebar-collapsed');
                sidebar.classList.add('collapsed');
            }
        }

        if (collapseBtn) {
            collapseBtn.addEventListener('click', toggleDesktopSidebar);
        }
        if (expandBtn) {
            expandBtn.addEventListener('click', (e) => {
                if (window.innerWidth > 992) {
                    toggleDesktopSidebar();
                } else {
                    e.stopPropagation();
                    openMobileMenu();
                }
            });
        }
        if (contentWrapper) {
             contentWrapper.addEventListener('click', (e) => {
                if(document.body.classList.contains('sidebar-mobile-open')) {
                    closeMobileMenu();
                }
            });
        }
    }
    
    // --- Логика экспорта ---
    function setupExportLogic() {
        const listContent = document.getElementById('list-content');
        if (!listContent || !document.getElementById('export-selected-btn')) return;

        const selectAllCheckbox = document.getElementById('select-all-checkbox');
        const exportBtn = document.getElementById('export-selected-btn');
        const exportBtnText = document.getElementById('export-btn-text');
        
        const getSelectedIds = () => Array.from(listContent.querySelectorAll('.row-checkbox:checked')).map(cb => cb.value);
        
        const updateButtonState = () => {
            const count = getSelectedIds().length;
            if (exportBtn) exportBtn.disabled = count === 0;
            if (exportBtnText) exportBtnText.textContent = count > 0 ? `Экспорт выбранных (${count})` : 'Экспорт выбранных';
        };
        
        listContent.addEventListener('change', (event) => {
            if (event.target.matches('.row-checkbox, #select-all-checkbox')) {
                if (event.target.id === 'select-all-checkbox') {
                    listContent.querySelectorAll('.row-checkbox').forEach(cb => { cb.checked = event.target.checked; });
                }
                updateButtonState();
            }
        });
        
        if (exportBtn) {
            exportBtn.addEventListener('click', () => {
                const ids = getSelectedIds().join(',');
                if (ids) window.location.href = `/admin/quoterequest/export/?ids=${ids}`;
            });
        }
        
        updateButtonState();
    }

    // --- Централизованная инициализация ---
    function initializePageComponents() {
        initializeSortable();
        setupExportLogic();
    }
    
    // --- Запуск ---
    initSidebar();
    initPopups();
    initializePageComponents();

    document.body.addEventListener('htmx:afterSwap', (event) => {
        if (event.detail.target.id === 'modal-body-content') {
            document.getElementById('modal-overlay')?.classList.add('show');
        }
        if (event.detail.target.id === 'slide-over-content') {
            document.getElementById('slide-over-overlay')?.classList.add('show');
        }
        initializePageComponents();
    });
});