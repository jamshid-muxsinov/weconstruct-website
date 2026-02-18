/* --- START OF FILE modern-crm.js --- */

document.addEventListener('DOMContentLoaded', () => {
    // 1. Уведомления (Notyf)
    window.notyf = new Notyf({
        duration: 4000,
        position: { x: 'right', y: 'top' },
        ripple: false, 
        dismissible: true
    });

    // 2. Обработка событий HTMX
    const body = document.body;
    const csrfToken = document.querySelector('meta[name="csrf-token"]')?.content;
    
    body.addEventListener('htmx:configRequest', (evt) => {
        if(evt.detail.verb !== 'get') {
            evt.detail.headers['X-CSRFToken'] = csrfToken;
        }
        body.style.cursor = 'wait';
    });

    body.addEventListener('htmx:afterRequest', () => {
        body.style.cursor = 'default';
    });

    body.addEventListener('htmx:responseError', () => {
        window.notyf.error('Ошибка соединения с сервером');
    });

    // Обработка "Toast" уведомлений от сервера
    body.addEventListener('htmx:afterSwap', (evt) => {
        const trigger = evt.detail.xhr.getResponseHeader("HX-Trigger");
        if (trigger) {
            try {
                let data;
                try {
                    data = JSON.parse(trigger);
                } catch {
                    data = JSON.parse(decodeURIComponent(trigger));
                }
                if (data['show-toast']) {
                    const { message, type } = data['show-toast'];
                    window.notyf.open({ type: type || 'success', message });
                }
                if (data['closeSlideOver']) closeOverlay('slide-over-overlay');
                if (data['closeModal']) closeOverlay('modal-overlay');
                
                if (evt.detail.target.id === 'kanban-board-container' && window.initKanbanSortable) {
                    window.initKanbanSortable();
                }
            } catch (e) { console.error("Trigger parse error", e); }
        }
        
        if (evt.detail.target.id === 'slide-over-content') openOverlay('slide-over-overlay');
        if (evt.detail.target.id === 'modal-body-content') openOverlay('modal-overlay');
    });

    // 3. Логика Оверлеев (Modals/Slide-overs)
    window.openOverlay = (id) => document.getElementById(id)?.classList.add('active');
    window.closeOverlay = (id) => document.getElementById(id)?.classList.remove('active');

    document.querySelectorAll('.overlay').forEach(overlay => {
        overlay.addEventListener('click', (e) => {
            if (e.target === overlay) overlay.classList.remove('active');
        });
    });
    
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            document.querySelectorAll('.overlay.active').forEach(el => el.classList.remove('active'));
        }
    });

    // 4. Alpine.js Store
    document.addEventListener('alpine:init', () => {
        Alpine.store('erp', {
            selectedItems: new Set(),
            toggleSelection(id) {
                if (this.selectedItems.has(id)) this.selectedItems.delete(id);
                else this.selectedItems.add(id);
            },
            clearSelection() { this.selectedItems.clear(); },
            get count() { return this.selectedItems.size; }
        });
    });

    // 5. Инициализация мобильного меню
    initMobileSidebar();
});

/* --- ГЛОБАЛЬНАЯ ЛОГИКА ЧЕКБОКСОВ (Вне DOMContentLoaded) --- */
document.addEventListener('change', function(e) {
    if (e.target && e.target.id === 'select-all') {
        const isChecked = e.target.checked;
        const checkboxes = document.querySelectorAll('td input[type="checkbox"]');
        checkboxes.forEach(cb => {
            cb.checked = isChecked;
        });
    }
});

/* --- ФУНКЦИИ МОБИЛЬНОГО МЕНЮ --- */
function initMobileSidebar() {
    const sidebar = document.getElementById('sidebar');
    const sidebarToggle = document.getElementById('sidebar-toggle');
    
    if (!sidebar || !sidebarToggle) return;

    // Создаем затемнение, если нет
    let sidebarOverlay = document.querySelector('.sidebar-overlay');
    if (!sidebarOverlay) {
        sidebarOverlay = document.createElement('div');
        sidebarOverlay.className = 'sidebar-overlay';
        document.body.appendChild(sidebarOverlay);
    }

    function toggleSidebar() {
        sidebar.classList.toggle('open');
        sidebarOverlay.classList.toggle('active');
    }

    function closeSidebar() {
        sidebar.classList.remove('open');
        sidebarOverlay.classList.remove('active');
    }

    sidebarToggle.addEventListener('click', (e) => {
        e.stopPropagation();
        toggleSidebar();
    });

    sidebarOverlay.addEventListener('click', closeSidebar);

    // Закрываем меню при клике на ссылку (только на мобильных)
    const navLinks = document.querySelectorAll('.nav-link');
    navLinks.forEach(link => {
        link.addEventListener('click', () => {
            if (window.innerWidth <= 1024) {
                closeSidebar();
            }
        });
    });
}

function getSelectedIds() {
    const selected = [];
    document.querySelectorAll('td input[type="checkbox"]:checked').forEach(cb => {
        selected.push(cb.value);
    });
    return selected;
}
