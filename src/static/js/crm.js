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

    // --- ENHANCED SIDEBAR LOGIC ---
    // *** НАЧАЛО ИЗМЕНЕНИЙ ***
    
    // Функция для применения сохраненной ширины сайдбара
    function applySidebarWidth() {
        const sidebar = document.getElementById('sidebar');
        // Применяем только на десктопе
        if (!sidebar || window.innerWidth <= 992) return;

        const savedWidth = localStorage.getItem('sidebarWidth');
        if (savedWidth) {
            sidebar.style.width = `${savedWidth}px`;
        }
    }
    
    function initSidebar() {
        const sidebar = document.getElementById('sidebar');
        const expandBtn = document.getElementById('sidebar-expand-btn');
        const body = document.body;

        if (!sidebar || !expandBtn) return;
        
        // Применяем ширину при первой загрузке страницы
        applySidebarWidth();

        expandBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            if (window.innerWidth <= 992) body.classList.toggle('sidebar-mobile-open');
        });
        document.addEventListener('click', (e) => {
            if (window.innerWidth <= 992 && body.classList.contains('sidebar-mobile-open') && !e.target.closest('#sidebar')) {
                body.classList.remove('sidebar-mobile-open');
            }
        });

        let isResizing = false;
        sidebar.addEventListener('mousedown', e => {
            if (Math.abs(sidebar.offsetWidth - e.offsetX) < 10) isResizing = true;
        });
        document.addEventListener('mousemove', e => {
            if (!isResizing || window.innerWidth <= 992) return;
            const newWidth = e.clientX;
            if (newWidth > 200 && newWidth < 500) {
                 sidebar.style.width = `${newWidth}px`;
            }
        });
        document.addEventListener('mouseup', () => {
            if(isResizing) {
                localStorage.setItem('sidebarWidth', sidebar.offsetWidth);
                isResizing = false;
            }
        });
    }
    
    function init() {
        setupHtmx();
        initPopups();
        initSidebar();
    }
    
    init();

    document.body.addEventListener('htmx:afterSwap', (event) => {
        if (event.detail.target.id === 'modal-body-content') document.getElementById('modal-overlay')?.classList.add('show');
        if (event.detail.target.id === 'slide-over-content') document.getElementById('slide-over-overlay')?.classList.add('show');
        
        applySidebarWidth();
    });
});