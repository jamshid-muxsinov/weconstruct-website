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
        
        document.body.addEventListener('htmx:responseError', (event) => {
            console.error('HTMX Response Error:', event.detail);
            const status = event.detail.xhr?.status;
            let message = 'Произошла ошибка сети. Попробуйте обновить страницу.';
            
            if (status === 401) {
                message = 'Сессия истекла. Перезагрузите страницу для входа.';
                // Redirect to login after a delay
                setTimeout(() => {
                    window.location.href = '/admin/login';
                }, 3000);
            } else if (status === 403) {
                message = 'Недостаточно прав для выполнения этого действия.';
            } else if (status >= 500) {
                message = 'Ошибка сервера. Попробуйте позже.';
            }
            
            notyf.error(message);
        });
        
        document.body.addEventListener('htmx:timeout', () => {
            notyf.error('Запрос занял слишком много времени. Попробуйте еще раз.');
        });
        
        document.body.addEventListener('htmx:sendError', () => {
            notyf.error('Не удалось отправить запрос. Проверьте подключение к интернету.');
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
        const collapseBtn = document.getElementById('sidebar-collapse-btn');
        const expandBtn = document.getElementById('sidebar-expand-btn');
        const body = document.body;
        const contentWrapper = document.getElementById('content-wrapper');

        if (!sidebar || !collapseBtn || !expandBtn || !contentWrapper) {
            console.warn('Sidebar elements not found');
            return;
        }
        
        const isDesktop = () => window.innerWidth > 992;
        const MIN_WIDTH = 200;
        const MAX_WIDTH = 400;
        const DEFAULT_WIDTH = 260;
        
        let resizeObserver = null;
        let isResizing = false;

        // Safe localStorage operations
        const getStoredValue = (key, defaultValue) => {
            try {
                return localStorage.getItem(key) || defaultValue;
            } catch (e) {
                console.warn('localStorage access failed:', e);
                return defaultValue;
            }
        };

        const setStoredValue = (key, value) => {
            try {
                localStorage.setItem(key, value);
            } catch (e) {
                console.warn('localStorage write failed:', e);
            }
        };

        // Initialize sidebar width persistence with proper error handling
        const initSidebarWidth = () => {
            if (!sidebar) return;
            
            const savedWidth = getStoredValue('sidebarWidth', DEFAULT_WIDTH.toString());
            const width = Math.max(MIN_WIDTH, Math.min(MAX_WIDTH, parseInt(savedWidth) || DEFAULT_WIDTH));
            
            // Only apply width if not collapsed
            if (!body.classList.contains('sidebar-collapsed')) {
                sidebar.style.setProperty('--sidebar-width', `${width}px`);
                sidebar.style.width = `${width}px`;
            }
            
            // Setup resize observer with proper error handling
            if (window.ResizeObserver) {
                try {
                    resizeObserver = new ResizeObserver(entries => {
                        if (isResizing || !entries || entries.length === 0) return;
                        
                        const entry = entries[0];
                        if (!entry || !entry.contentRect) return;
                        
                        const newWidth = Math.round(entry.contentRect.width);
                        
                        // Only save width if it's within valid range and sidebar is not collapsed
                        if (newWidth >= MIN_WIDTH && 
                            newWidth <= MAX_WIDTH && 
                            !body.classList.contains('sidebar-collapsed') &&
                            isDesktop()) {
                            setStoredValue('sidebarWidth', newWidth.toString());
                            sidebar.style.setProperty('--sidebar-width', `${newWidth}px`);
                        }
                    });
                    
                    resizeObserver.observe(sidebar);
                } catch (e) {
                    console.warn('ResizeObserver initialization failed:', e);
                }
            }
        };

        // Apply sidebar state with improved logic
        const applySidebarState = () => {
            if (!sidebar) return;
            
            // Remove init class after first run
            body.classList.remove('sidebar-collapsed-init');

            if (!isDesktop()) {
                // On mobile, ensure desktop classes are removed
                body.classList.remove('sidebar-collapsed');
                sidebar.classList.remove('collapsed');
                
                // Reset sidebar properties for mobile without triggering transitions
                sidebar.style.width = '';
                sidebar.style.removeProperty('--sidebar-width');
                
                // Ensure mobile sidebar is not in open state unless intended
                if (!body.classList.contains('sidebar-mobile-open')) {
                    // Make sure sidebar is properly hidden on mobile
                    sidebar.style.transform = '';
                }
                return;
            }
            
            // On desktop, apply saved state
            const isCollapsed = getStoredValue('sidebarCollapsed', 'false') === 'true';
            
            isResizing = true;
            body.classList.toggle('sidebar-collapsed', isCollapsed);
            sidebar.classList.toggle('collapsed', isCollapsed);
            
            if (!isCollapsed) {
                // Apply saved width when expanded
                const savedWidth = getStoredValue('sidebarWidth', DEFAULT_WIDTH.toString());
                const width = Math.max(MIN_WIDTH, Math.min(MAX_WIDTH, parseInt(savedWidth) || DEFAULT_WIDTH));
                sidebar.style.setProperty('--sidebar-width', `${width}px`);
                sidebar.style.width = `${width}px`;
            } else {
                // Reset inline styles when collapsed to let CSS take over
                sidebar.style.width = '';
            }
            
            // Allow resize observer to work again after a brief delay
            setTimeout(() => { isResizing = false; }, 100);
        };
        
        // Enhanced collapse button handler
        collapseBtn.addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation();
            
            if (isDesktop()) {
                const isCollapsed = body.classList.contains('sidebar-collapsed');
                setStoredValue('sidebarCollapsed', (!isCollapsed).toString());
                applySidebarState();
            }
        });
        
        // Enhanced expand button handler
        expandBtn.addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation();
            
            try {
                if (isDesktop()) {
                    setStoredValue('sidebarCollapsed', 'false');
                    applySidebarState();
                } else {
                    // Mobile sidebar toggle
                    body.classList.add('sidebar-mobile-open');
                }
            } catch (error) {
                console.warn('Error in expand button handler:', error);
                // Fallback behavior
                if (isDesktop()) {
                    body.classList.remove('sidebar-collapsed');
                    sidebar.classList.remove('collapsed');
                }
            }
        });
        
        // Close mobile sidebar when clicking content
        contentWrapper.addEventListener('click', () => {
            if (body.classList.contains('sidebar-mobile-open')) {
                body.classList.remove('sidebar-mobile-open');
            }
        });
        
        // Handle window resize with debouncing and transition disabling
        let resizeTimeout;
        let isResizeActive = false;
        
        const disableTransitions = () => {
            if (!isResizeActive) {
                isResizeActive = true;
                document.body.classList.add('no-transition');
            }
        };
        
        const enableTransitions = () => {
            if (isResizeActive) {
                isResizeActive = false;
                setTimeout(() => {
                    document.body.classList.remove('no-transition');
                }, 50);
            }
        };
        
        const handleResize = () => {
            disableTransitions();
            clearTimeout(resizeTimeout);
            resizeTimeout = setTimeout(() => {
                applySidebarState();
                // Re-enable transitions after state is applied
                setTimeout(enableTransitions, 100);
            }, 150);
        };
        
        window.addEventListener('resize', handleResize);
        
        // Handle orientation changes on mobile devices
        if (window.screen && window.screen.orientation) {
            window.screen.orientation.addEventListener('change', () => {
                disableTransitions();
                setTimeout(() => {
                    applySidebarState();
                    setTimeout(enableTransitions, 150);
                }, 100);
            });
        }
        
        // Fallback for older browsers
        window.addEventListener('orientationchange', () => {
            disableTransitions();
            setTimeout(() => {
                applySidebarState();
                setTimeout(enableTransitions, 150);
            }, 100);
        });
        
        // Initialize on load
        applySidebarState();
        initSidebarWidth();
        
        // Cleanup function for potential future use
        return () => {
            if (resizeObserver) {
                resizeObserver.disconnect();
            }
            window.removeEventListener('resize', handleResize);
            window.removeEventListener('orientationchange', handleResize);
            if (window.screen && window.screen.orientation) {
                window.screen.orientation.removeEventListener('change', handleResize);
            }
        };
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
                    const oldColumn = evt.from;
                    const oldIndex = evt.oldIndex;

                    // Show loading state
                    card.style.opacity = '0.5';
                    card.style.pointerEvents = 'none';

                    try {
                        const response = await fetch('/admin/api/quoterequests/update-status', {
                            method: 'POST',
                            headers: { 
                                'Content-Type': 'application/json', 
                                'X-CSRFToken': csrfToken 
                            },
                            body: JSON.stringify({ 
                                id: parseInt(quoteId), 
                                status: newStatus 
                            })
                        });
                        
                        if (!response.ok) {
                            throw new Error(`Server returned ${response.status}: ${response.statusText}`);
                        }
                        
                        const result = await response.json();
                        if (result.status !== 'ok') {
                            throw new Error('Server returned error status');
                        }
                        
                        notyf.success('Статус обновлен!');
                        htmx.trigger('#kanban-board-container', 'updateKanban');
                        
                    } catch (error) {
                        console.error('Kanban update error:', error);
                        
                        // Revert the move
                        oldColumn.insertBefore(card, oldColumn.children[oldIndex] || null);
                        
                        let errorMessage = 'Не удалось обновить статус.';
                        if (error.message.includes('401')) {
                            errorMessage = 'Сессия истекла. Обновите страницу.';
                        } else if (error.message.includes('403')) {
                            errorMessage = 'Недостаточно прав.';
                        }
                        
                        notyf.error(errorMessage);
                    } finally {
                        // Restore card appearance
                        card.style.opacity = '';
                        card.style.pointerEvents = '';
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