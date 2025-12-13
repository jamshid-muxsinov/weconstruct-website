/* --- START OF FILE modern-crm.js --- */

document.addEventListener('DOMContentLoaded', () => {
    // 1. Уведомления (Notyf)
    const notyf = new Notyf({
        duration: 4000,
        position: { x: 'right', y: 'top' },
        ripple: false, // Отключаем для производительности
        dismissible: true
    });

    // 2. Обработка событий HTMX
    const body = document.body;
    
    // Передаем CSRF токен
    const csrfToken = document.querySelector('meta[name="csrf-token"]')?.content;
    body.addEventListener('htmx:configRequest', (evt) => {
        if(evt.detail.verb !== 'get') {
            evt.detail.headers['X-CSRFToken'] = csrfToken;
        }
        // Индикатор загрузки в стиле NProgress можно добавить здесь
        body.style.cursor = 'wait';
    });

    body.addEventListener('htmx:afterRequest', () => {
        body.style.cursor = 'default';
    });

    body.addEventListener('htmx:responseError', () => {
        notyf.error('Ошибка соединения с сервером');
    });

    // Обработка "Toast" уведомлений от сервера
    body.addEventListener('htmx:afterSwap', (evt) => {
        const trigger = evt.detail.xhr.getResponseHeader("HX-Trigger");
        if (trigger) {
            try {
                const data = JSON.parse(trigger);
                if (data['show-toast']) {
                    const { message, type } = data['show-toast'];
                    notyf.open({ type: type || 'success', message });
                }
                // Автоматическое закрытие модалок если пришел сигнал
                if (data['closeSlideOver']) closeOverlay('slide-over-overlay');
                if (data['closeModal']) closeOverlay('modal-overlay');
                
                // Реинициализация скриптов если контент обновился
                if (evt.detail.target.id === 'kanban-board-container') {
                    initKanbanSortable(); // Функция из kanban-enhanced.js
                }
            } catch (e) { console.error("Trigger parse error", e); }
        }
        
        // Авто-открытие оверлеев при загрузке контента в них
        if (evt.detail.target.id === 'slide-over-content') {
            openOverlay('slide-over-overlay');
        }
        if (evt.detail.target.id === 'modal-body-content') {
            openOverlay('modal-overlay');
        }
    });

    // 3. Управление Sidebar (Мобильная версия)
    const toggleBtn = document.getElementById('sidebar-toggle');
    const appShell = document.getElementById('app-shell');
    
    if (toggleBtn) {
        toggleBtn.addEventListener('click', () => {
            appShell.classList.toggle('sidebar-open');
        });
    }

    // 4. Логика Оверлеев (Modals/Slide-overs)
    window.openOverlay = (id) => document.getElementById(id)?.classList.add('active');
    window.closeOverlay = (id) => document.getElementById(id)?.classList.remove('active');

    // Закрытие по клику вне контента или ESC
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

    // 5. Alpine.js Store для Kanban (если используется)
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
});

document.addEventListener('change', function(e) {
    if (e.target && e.target.id === 'select-all') {
        const isChecked = e.target.checked;
        const checkboxes = document.querySelectorAll('td input[type="checkbox"]');
        checkboxes.forEach(cb => {
            cb.checked = isChecked;
        });
    }

    /* --- MOBILE SIDEBAR LOGIC --- */
    const sidebar = document.getElementById('sidebar');
    const sidebarToggle = document.getElementById('sidebar-toggle');
    const appShell = document.getElementById('app-shell');

    // Создаем затемнение (backdrop) динамически, если его нет
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

    if (sidebarToggle) {
        sidebarToggle.addEventListener('click', (e) => {
            e.stopPropagation(); // Чтобы клик не ушел дальше
            toggleSidebar();
        });
    }

    // Закрываем при клике на затемнение
    sidebarOverlay.addEventListener('click', closeSidebar);

    // Закрываем при клике на любую ссылку в меню (чтобы перейти на страницу)
    const navLinks = document.querySelectorAll('.nav-link');
    navLinks.forEach(link => {
        link.addEventListener('click', () => {
            // Закрываем только на мобильных (если экран меньше 1024)
            if (window.innerWidth <= 1024) {
                closeSidebar();
            }
        });
    });
});

function getSelectedIds() {
    const selected = [];
    document.querySelectorAll('td input[type="checkbox"]:checked').forEach(cb => {
        selected.push(cb.value);
    });
    return selected;
}

