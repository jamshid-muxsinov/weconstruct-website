// src/static/js/crm.js

document.addEventListener('DOMContentLoaded', function() {

    // --- Глобальная инициализация ---
    const csrfToken = getCsrfToken();
    const notyf = new Notyf({
        duration: 3000,
        position: { x: 'right', y: 'top' },
        dismissible: true
    });

    // --- Утилиты ---
    function getCsrfToken() {
        return document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') || '';
    }

    // --- Настройка HTMX ---
    function setupHtmx() {
        document.body.addEventListener('htmx:configRequest', (event) => {
            if (event.detail.verb !== 'get') {
                event.detail.headers['X-CSRFToken'] = csrfToken;
            }
        });
        
        document.body.addEventListener('htmx:responseError', (event) => {
            if (event.detail.xhr.status === 401) { 
                notyf.error('Сессия истекла. Перезагрузка страницы...');
                setTimeout(() => window.location.reload(), 1500);
            }
        });
    }
    
    // --- Обработчик выхода ---
    document.body.addEventListener('click', function(event) {
        if (event.target.closest('.logout-trigger')) {
            event.preventDefault();
            window.location.href = event.target.closest('.logout-trigger').href;
        }
    });

    // --- Управление модальными окнами и сайд-оверами ---
    function initPopups() {
        const closeModal = (overlay) => {
            overlay.classList.remove('show');
            const content = overlay.querySelector('#modal-body-content, #slide-over-content');
            if (content) {
                content.innerHTML = `<div class="modal-loading-placeholder"><i class='bx bx-loader-alt bx-spin'></i><span>Загрузка...</span></div>`;
            }
        };

        document.querySelectorAll('.modal-overlay, .slide-over-overlay').forEach(overlay => {
            overlay.addEventListener('click', e => { if (e.target === overlay) closeModal(overlay); });
        });

        document.addEventListener('keydown', e => { 
            if (e.key === 'Escape') {
                document.querySelectorAll('.modal-overlay.show, .slide-over-overlay.show').forEach(closeModal);
            } 
        });

        document.body.addEventListener('click', event => {
            const closeButton = event.target.closest('.modal-close, .slide-over-close');
            if (closeButton) {
                event.preventDefault();
                closeModal(closeButton.closest('.modal-overlay, .slide-over-overlay'));
            }
        });
        
        document.body.addEventListener('closeModal', () => {
            const modal = document.getElementById('modal-overlay');
            if (modal) closeModal(modal);
        });
        document.body.addEventListener('closeSlideOver', () => {
            const slideOver = document.getElementById('slide-over-overlay');
            if (slideOver) closeModal(slideOver);
        });
    }

    // --- Логика канбан-доски ---
    function initializeSortable() {
        document.querySelectorAll('.kanban-column-body').forEach(column => {
            if (Sortable.get(column)) { Sortable.get(column).destroy(); }
            new Sortable(column, {
                group: 'kanban',
                animation: 150,
                ghostClass: 'kanban-card-ghost',
                onEnd: handleKanbanDrop
            });
        });
    }

    async function handleKanbanDrop(evt) {
        if (evt.from === evt.to) return;

        const card = evt.item;
        const quoteId = parseInt(card.dataset.id);
        const newStatus = evt.to.closest('.kanban-column').dataset.status;

        try {
            const response = await fetch('/admin/api/quoterequests/update-status', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken
                },
                body: JSON.stringify({ id: quoteId, status: newStatus })
            });

            if (!response.ok) {
                throw new Error(`Server error: ${response.status}`);
            }
            
            notyf.success('Статус обновлен!');
            
            const kanbanContainer = document.getElementById('kanban-board-container');
            if (kanbanContainer) {
                htmx.trigger(kanbanContainer, 'updateKanban');
            }

        } catch (error) {
            console.error('Failed to update status:', error);
            evt.from.insertBefore(card, evt.from.children[evt.oldIndex]);
            notyf.error('Не удалось обновить статус.');
        }
    }

    // --- Логика сайдбара ---
    function initSidebar() {
        const sidebar = document.getElementById('sidebar');
        if (!sidebar) return;

        // Логика для десктопа (сворачивание)
        const collapseBtn = document.getElementById('sidebar-collapse-btn');
        const expandBtnDesktop = document.getElementById('sidebar-expand-btn'); // Кнопка на контенте
        
        if(collapseBtn && expandBtnDesktop) {
            document.documentElement.classList.remove('sidebar-collapsed-init');
            
            const applyDesktopState = (isCollapsed) => {
                document.body.classList.toggle('sidebar-collapsed', isCollapsed);
                sidebar.classList.toggle('collapsed', isCollapsed);
            };
            
            const toggleDesktop = () => {
                const isCollapsed = localStorage.getItem('sidebarCollapsed') === 'true';
                localStorage.setItem('sidebarCollapsed', !isCollapsed);
                applyDesktopState(!isCollapsed);
            };

            applyDesktopState(localStorage.getItem('sidebarCollapsed') === 'true');
            collapseBtn.addEventListener('click', toggleDesktop);
            expandBtnDesktop.addEventListener('click', toggleDesktop);
        }

        // --- НОВАЯ ЛОГИКА ДЛЯ МОБИЛЬНЫХ УСТРОЙСТВ ---
        const mobileToggleBtn = document.getElementById('sidebar-expand-btn'); // Гамбургер
        
        if (mobileToggleBtn) {
            mobileToggleBtn.addEventListener('click', (e) => {
                // Предотвращаем срабатывание десктопной логики, если она тоже на этой кнопке
                if (window.innerWidth <= 768) {
                    e.stopPropagation();
                    document.body.classList.toggle('sidebar-mobile-open');
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
        
        const getSelectedIds = () => {
            return Array.from(listContent.querySelectorAll('.row-checkbox:checked'))
                .map(cb => cb.value);
        };
        
        const updateButtonState = () => {
            const selectedIds = getSelectedIds();
            const count = selectedIds.length;

            exportBtn.disabled = count === 0;
            
            if (exportBtnText) {
                exportBtnText.textContent = count > 0 
                    ? `Экспорт выбранных (${count})` 
                    : 'Экспорт выбранных';
            }

            const allRowCheckboxes = listContent.querySelectorAll('.row-checkbox');
            if (selectAllCheckbox) {
                selectAllCheckbox.checked = allRowCheckboxes.length > 0 && 
                                           count === allRowCheckboxes.length;
            }
        };
        
        // Используем MutationObserver чтобы отслеживать изменения в таблице (пагинация)
        const observer = new MutationObserver(() => {
            updateButtonState();
        });
        observer.observe(listContent, { childList: true, subtree: true });

        listContent.addEventListener('change', (event) => {
            const target = event.target;
            
            if (target.matches('.row-checkbox')) {
                updateButtonState();
            } else if (target.matches('#select-all-checkbox')) {
                listContent.querySelectorAll('.row-checkbox').forEach(checkbox => {
                    checkbox.checked = target.checked;
                });
                updateButtonState();
            }
        });
        
        exportBtn.addEventListener('click', () => {
            const ids = getSelectedIds().join(',');
            if (ids) {
                window.location.href = `/admin/quoterequest/export/?ids=${ids}`;
            }
        });
        
        updateButtonState();
    }

    // --- Централизованная инициализация ---
    function initializePageComponents() {
        initSidebar();
        initializeSortable();
        setupExportLogic();
    }
    
    setupHtmx();
    initPopups();
    initializePageComponents();

    document.body.addEventListener('htmx:afterSwap', function (event) {
        if (event.detail.target.id === 'modal-body-content') {
            document.getElementById('modal-overlay')?.classList.add('show');
        }
        if (event.detail.target.id === 'slide-over-content') {
            document.getElementById('slide-over-overlay')?.classList.add('show');
        }
        
        // Переинициализируем компоненты, которые могли быть заменены через HTMX
        initializePageComponents();
    });
});