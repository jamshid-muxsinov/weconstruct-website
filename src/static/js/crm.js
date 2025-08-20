document.addEventListener('DOMContentLoaded', function() {

    const csrfToken = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') || '';
    const notyf = new Notyf({
        duration: 3000,
        position: { x: 'right', y: 'top' },
        dismissible: true
    });

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
    
    function applySidebarState() {
        const body = document.body;
        if (!body) return;

        const isDesktop = () => window.innerWidth > 992;
        if (!isDesktop()) {
            body.classList.remove('sidebar-collapsed', 'sidebar-collapsed-init');
            return;
        }

        const isCollapsed = localStorage.getItem('sidebarCollapsed') === 'true';
        body.classList.toggle('sidebar-collapsed', isCollapsed);

        if (body.classList.contains('sidebar-collapsed-init')) {
            body.classList.remove('sidebar-collapsed-init');
        }
    }

    function enableSidebarTransitions() {
        document.body.classList.add('sidebar-transitions-enabled');
    }

    function initSidebarBehavior() {
        const isDesktop = () => window.innerWidth > 992;
        
        document.body.addEventListener('click', function(event) {
            const collapseBtn = event.target.closest('#sidebar-collapse-btn');
            const expandBtn = event.target.closest('#sidebar-expand-btn');
            const contentWrapper = event.target.closest('#content-wrapper');

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
            } else if (contentWrapper && document.body.classList.contains('sidebar-mobile-open')) {
                 document.body.classList.remove('sidebar-mobile-open');
            }
        });

        window.addEventListener('resize', applySidebarState);
    }-
    function initializeSortable() {
        document.querySelectorAll('.kanban-column-body').forEach(column => {
            const existingSortable = Sortable.get(column);
            if (existingSortable) { 
                existingSortable.destroy(); 
            }
            
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
                            headers: { 
                                'Content-Type': 'application/json', 
                                'X-CSRFToken': csrfToken 
                            },
                            body: JSON.stringify({ 
                                id: parseInt(quoteId, 10), 
                                status: newStatus 
                            })
                        });
                        
                        if (!response.ok) {
                            const errorData = await response.json().catch(() => ({}));
                            throw new Error(errorData.message || 'Server response was not ok.');
                        }
                        
                        notyf.success('Статус обновлен!');
                        htmx.trigger('#kanban-board-container', 'updateKanban');
                    } catch (error) {
                        console.error('Kanban update error:', error);
                        evt.from.insertBefore(card, evt.from.children[evt.oldIndex]);
                        notyf.error('Не удалось обновить статус.');
                    }
                }
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
            
            if (exportBtn) {
                exportBtn.disabled = count === 0;
                exportBtn.setAttribute('aria-disabled', count === 0);
            }
            
            if (exportBtnText) {
                exportBtnText.textContent = count > 0 ? `Экспорт выбранных (${count})` : 'Экспорт выбранных';
            }
        };
        
        listContent.addEventListener('change', (e) => {
            if (e.target.matches('#select-all-checkbox')) {
                const isChecked = e.target.checked;
                listContent.querySelectorAll('.row-checkbox').forEach(cb => { 
                    cb.checked = isChecked; 
                });
                updateButtonState();
            } else if (e.target.matches('.row-checkbox')) {
                updateButtonState();
            }
        });

        const exportBtn = document.getElementById('export-selected-btn');
        if (exportBtn) {
            exportBtn.addEventListener('click', () => {
                const ids = Array.from(listContent.querySelectorAll('.row-checkbox:checked'))
                    .map(cb => encodeURIComponent(cb.value))
                    .join(',');
                if (ids) {
                    window.location.href = `/admin/quoterequest/export/?ids=${ids}`;
                }
            });
        }
        
        updateButtonState();
    }
    function init() {
        setupHtmx();
        initPopups();
        initSidebarBehavior();
        
        applySidebarState();
        setTimeout(enableSidebarTransitions, 50);
        
        initializeSortable();
        setupExportLogic();
    }

    init();

    document.body.addEventListener('htmx:afterSwap', (event) => {
        applySidebarState();
        setTimeout(enableSidebarTransitions, 50);

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