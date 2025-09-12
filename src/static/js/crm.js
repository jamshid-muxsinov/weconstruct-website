document.addEventListener('DOMContentLoaded', function() {
    const notyf = new Notyf({
        duration: 3000,
        position: { x: 'right', y: 'top' },
        dismissible: true
    });

    // --- TRANSITION CONTROL FOR SMOOTH NAVIGATION ---
    const stabilizeNavigation = () => {
        if (!document.body.classList.contains('navigating')) {
            document.body.classList.add('navigating');
            setTimeout(() => document.body.classList.remove('navigating'), 500);
        }
    };
    document.body.addEventListener('htmx:beforeRequest', stabilizeNavigation);
    
    // --- HTMX SETUP ---
    function setupHtmx() {
        const csrfToken = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') || '';
        document.body.addEventListener('htmx:configRequest', (event) => {
            if (event.detail.verb !== 'get') event.detail.headers['X-CSRFToken'] = csrfToken;
        });
        document.body.addEventListener('htmx:responseError', () => notyf.error('Ошибка сети или сервера.'));
        document.body.addEventListener('htmx:afterSwap', (event) => {
            const triggerHeader = event.detail.xhr.getResponseHeader("HX-Trigger");
            if (triggerHeader) {
                try {
                    const triggers = JSON.parse(triggerHeader);
                    if (triggers['show-toast']) {
                        notyf.open({ type: triggers['show-toast'].type || 'success', message: triggers['show-toast'].message });
                    }
                } catch (e) { console.error("Could not parse HX-Trigger", e); }
            }
        });
    }

    // --- POPUP (MODAL/SLIDE-OVER) LOGIC ---
    function initPopups() {
        const closePopup = (overlay) => overlay?.classList.remove('show');
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
            if (e.key === 'Escape') document.querySelectorAll('.modal-overlay.show, .slide-over-overlay.show').forEach(closePopup);
        });
        document.body.addEventListener('closeModal', () => closePopup(document.getElementById('modal-overlay')));
        document.body.addEventListener('closeSlideOver', () => closePopup(document.getElementById('slide-over-overlay')));
    }

    // --- LANGUAGE SWITCHER LOGIC ---
    function initLangSwitcher() {
    const switcher = document.getElementById('lang-switcher');
    if (!switcher) return;

    const button = switcher.querySelector('.lang-switcher-btn');
    const menu = switcher.querySelector('.lang-switcher-menu');

    button.addEventListener('click', function (event) {
        event.stopPropagation();
        const isExpanded = button.getAttribute('aria-expanded') === 'true';
        button.setAttribute('aria-expanded', !isExpanded);
        menu.classList.toggle('show');
    });

    // Закрываем меню, если клик был вне его
    document.addEventListener('click', function (e) {
        if (!switcher.contains(e.target)) {
            if (button.getAttribute('aria-expanded') === 'true') {
                button.setAttribute('aria-expanded', 'false');
                menu.classList.remove('show');
            }
        }
    });
}

    // --- ENHANCED SIDEBAR LOGIC ---
    function initSidebar() {
        const sidebar = document.getElementById('sidebar');
        const expandBtn = document.getElementById('sidebar-expand-btn');
        const body = document.body;

        if (!sidebar || !expandBtn) return;
        
        // Применяем ширину при первой загрузке страницы
        const savedWidth = localStorage.getItem('sidebarWidth');
        if (window.innerWidth > 992 && savedWidth) {
            sidebar.style.width = `${savedWidth}px`;
        }

        // Логика для мобильного меню
        expandBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            if (window.innerWidth <= 992) body.classList.toggle('sidebar-mobile-open');
        });
        document.addEventListener('click', (e) => {
            if (window.innerWidth <= 992 && body.classList.contains('sidebar-mobile-open') && !e.target.closest('#sidebar')) {
                body.classList.remove('sidebar-mobile-open');
            }
        });

        // Логика изменения размера и сохранения ширины
        let isResizing = false;
        sidebar.addEventListener('mousedown', e => {
            if (Math.abs(sidebar.offsetWidth - e.offsetX) < 10) isResizing = true;
        });
        document.addEventListener('mousemove', e => {
            if (!isResizing || window.innerWidth <= 992) return;
            const newWidth = e.clientX;
            if (newWidth > 200 && newWidth < 500) sidebar.style.width = `${newWidth}px`;
        });
        document.addEventListener('mouseup', () => {
            if(isResizing) {
                localStorage.setItem('sidebarWidth', sidebar.offsetWidth);
                isResizing = false;
            }
        });
    }
    function updateActiveNavLink(path) {
        const navContainer = document.getElementById('sidebar-nav');
        if (!navContainer) return;
        
        const links = navContainer.querySelectorAll('.nav-link');
        let bestMatch = null;

        links.forEach(link => {
            link.classList.remove('active');
            const linkPath = new URL(link.href).pathname;
            
            // Находим наиболее точное совпадение
            if (path.startsWith(linkPath)) {
                if (!bestMatch || linkPath.length > new URL(bestMatch.href).pathname.length) {
                    bestMatch = link;
                }
            }
        });
        
        // Особый случай для главной страницы
        if (path === '/admin/' || path === '/admin/kanban') {
            const kanbanLink = navContainer.querySelector('a[href*="/admin/kanban"]');
            kanbanLink?.classList.add('active');
        } else if (bestMatch) {
            bestMatch.classList.add('active');
        }
    }
    // *** КОНЕЦ ИЗМЕНЕНИЙ ***
    
    // --- INITIALIZATION ---
    function init() {
        setupHtmx();
        initPopups();
        initLangSwitcher();
        initSidebar();
    }
    
    init();

    // Re-initialize dynamic components after HTMX swaps
    document.body.addEventListener('htmx:afterSwap', (event) => {
        if (event.detail.target.id === 'modal-body-content') document.getElementById('modal-overlay')?.classList.add('show');
        if (event.detail.target.id === 'slide-over-content') document.getElementById('slide-over-overlay')?.classList.add('show');
    });

    // *** ИЗМЕНЕНИЕ: Обновляем активную ссылку после навигации ***
    document.body.addEventListener('htmx:pushedIntoHistory', (event) => {
        const path = event.detail.path;
        updateActiveNavLink(path);
    });

});