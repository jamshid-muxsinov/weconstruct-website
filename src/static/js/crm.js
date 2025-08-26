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
            // Remove the class after animations should have completed
            setTimeout(() => {
                document.body.classList.remove('navigating');
            }, 500);
        }
    };
    document.body.addEventListener('htmx:beforeRequest', stabilizeNavigation);
    
    // --- HTMX SETUP ---
    function setupHtmx() {
        const csrfToken = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') || '';
        document.body.addEventListener('htmx:configRequest', (event) => {
            if (event.detail.verb !== 'get') {
                event.detail.headers['X-CSRFToken'] = csrfToken;
            }
        });

        document.body.addEventListener('htmx:responseError', (event) => {
            notyf.error('Ошибка сети или сервера.');
        });
        
        document.body.addEventListener('htmx:afterSwap', (event) => {
            const triggerHeader = event.detail.xhr.getResponseHeader("HX-Trigger");
            if (triggerHeader) {
                try {
                    const triggers = JSON.parse(triggerHeader);
                    if (triggers['show-toast']) {
                        const toast = triggers['show-toast'];
                        notyf.open({
                            type: toast.type || 'success',
                            message: toast.message
                        });
                    }
                } catch (e) { console.error("Could not parse HX-Trigger", e); }
            }
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

    // --- ENHANCED SIDEBAR LOGIC ---
    function initSidebar() {
        const sidebar = document.getElementById('sidebar');
        const expandBtn = document.getElementById('sidebar-expand-btn');
        const body = document.body;

        if (!sidebar || !expandBtn) return;
        
        const isDesktop = () => window.innerWidth > 992;

        // Restore sidebar width from localStorage on desktop
        const savedWidth = localStorage.getItem('sidebarWidth');
        if (isDesktop() && savedWidth) {
            sidebar.style.width = `${savedWidth}px`;
        }

        // Handle expand button click for mobile
        expandBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            if (!isDesktop()) {
                body.classList.toggle('sidebar-mobile-open');
            }
        });

        // Close mobile sidebar when clicking outside
        document.addEventListener('click', (e) => {
            if (!isDesktop() && body.classList.contains('sidebar-mobile-open') && !e.target.closest('#sidebar')) {
                body.classList.remove('sidebar-mobile-open');
            }
        });

        // Save sidebar width on resize (desktop only)
        let isResizing = false;
        sidebar.addEventListener('mousedown', e => {
            if (Math.abs(sidebar.offsetWidth - e.offsetX) < 10) {
                 isResizing = true;
            }
        });
        document.addEventListener('mousemove', e => {
            if (!isResizing || !isDesktop()) return;
            const newWidth = e.clientX;
            sidebar.style.width = `${newWidth}px`;
        });
        document.addEventListener('mouseup', () => {
            if(isResizing) {
                localStorage.setItem('sidebarWidth', sidebar.offsetWidth);
                isResizing = false;
            }
        });
    }
    
    // --- INITIALIZATION ---
    function init() {
        setupHtmx();
        initPopups();
        initSidebar();
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
    });
});