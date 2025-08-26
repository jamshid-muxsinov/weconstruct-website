// Enhanced Kanban Board Functionality
// Mobile-first approach with touch support and advanced filtering

// Global keyboard shortcuts
let keySequence = [];

document.addEventListener('keydown', (e) => {
    // Handle global shortcuts
    handleGlobalShortcuts(e);
    
    // Handle key sequences (like 'g k' for goto kanban)
    handleKeySequence(e);
});

function handleGlobalShortcuts(e) {
    // Don't trigger shortcuts when typing in input fields
    if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') {
        return;
    }
    
    switch(e.key) {
        case '?':
            e.preventDefault();
            showKeyboardShortcuts();
            break;
        case '/':
            e.preventDefault();
            focusSearch();
            break;
        case 'Escape':
            e.preventDefault();
            closeAllModals();
            break;
    }
}

function handleKeySequence(e) {
    if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') {
        return;
    }
    
    keySequence.push(e.key.toLowerCase());
    
    // Keep only last 2 keys
    if (keySequence.length > 2) {
        keySequence = keySequence.slice(-2);
    }
    
    const sequence = keySequence.join('');
    
    switch(sequence) {
        case 'gk':
            e.preventDefault();
            window.location.href = '/admin/kanban';
            break;
        case 'gd':
            e.preventDefault();
            window.location.href = '/admin/dashboard';
            break;
        case 'gl':
            e.preventDefault();
            window.location.href = '/admin/quoterequest/';
            break;
    }
    
    // Clear sequence after 1 second
    setTimeout(() => {
        keySequence = [];
    }, 1000);
}

function showKeyboardShortcuts() {
    fetch('/admin/htmx/keyboard-shortcuts')
        .then(response => response.text())
        .then(html => {
            document.getElementById('modal-body-content').innerHTML = html;
            document.getElementById('modal-overlay').classList.add('show');
        })
        .catch(error => {
            console.error('Error loading keyboard shortcuts:', error);
        });
}

function focusSearch() {
    const searchInput = document.querySelector('.search-box input');
    if (searchInput) {
        searchInput.focus();
    }
}

function closeAllModals() {
    document.getElementById('modal-overlay').classList.remove('show');
    document.getElementById('slide-over-overlay').classList.remove('show');
    
    // Clear bulk selection
    if (window.Alpine && window.Alpine.store) {
        const bulkStore = window.Alpine.store('bulkActions');
        if (bulkStore && bulkStore.clearSelection) {
            bulkStore.clearSelection();
        }
    }
}

// Alpine.js components for kanban functionality
document.addEventListener('alpine:init', () => {
    
    // Advanced filtering component
    Alpine.data('kanbanFilters', () => ({
        searchQuery: '',
        filters: {
            assignee: '',
            status: '',
            priority: ''
        },
        
        init() {
            this.loadFiltersFromURL();
        },
        
        toggleFilter(type, value) {
            if (this.filters[type] === value) {
                this.filters[type] = '';
            } else {
                this.filters[type] = value;
            }
            this.filterCards();
        },
        
        clearFilters() {
            this.filters = { assignee: '', status: '', priority: '' };
            this.searchQuery = '';
            this.filterCards();
        },
        
        hasActiveFilters() {
            return this.searchQuery || 
                   Object.values(this.filters).some(filter => filter !== '');
        },
        
        filterCards() {
            const cards = document.querySelectorAll('.kanban-card');
            
            cards.forEach(card => {
                const shouldShow = this.cardMatchesFilters(card);
                card.style.display = shouldShow ? 'block' : 'none';
                
                // Add fade animation
                if (shouldShow) {
                    card.style.opacity = '0';
                    setTimeout(() => {
                        card.style.opacity = '1';
                    }, 50);
                }
            });
            
            this.updateColumnCounts();
            this.updateURL();
        },
        
        cardMatchesFilters(card) {
            // Search query filter
            if (this.searchQuery) {
                const searchTerm = this.searchQuery.toLowerCase();
                const clientName = card.dataset.clientName || '';
                const phone = card.dataset.phone || '';
                const cardId = card.dataset.id || '';
                
                const matchesSearch = 
                    clientName.includes(searchTerm) ||
                    phone.includes(searchTerm) ||
                    cardId.includes(searchTerm);
                    
                if (!matchesSearch) return false;
            }
            
            // Status filter
            if (this.filters.status && card.dataset.status !== this.filters.status) {
                return false;
            }
            
            // Assignee filter
            if (this.filters.assignee === 'me') {
                const currentUserId = this.getCurrentUserId();
                if (card.dataset.assignee !== currentUserId) {
                    return false;
                }
            }
            
            return true;
        },
        
        updateColumnCounts() {
            document.querySelectorAll('.kanban-column').forEach(column => {
                const visibleCards = column.querySelectorAll('.kanban-card:not([style*="display: none"])');
                const countElement = column.querySelector('.kanban-count');
                if (countElement) {
                    countElement.textContent = visibleCards.length;
                }
            });
        },
        
        getCurrentUserId() {
            // Get current user ID from meta tag or global variable
            return document.querySelector('meta[name="current-user-id"]')?.content || '';
        },
        
        loadFiltersFromURL() {
            const params = new URLSearchParams(window.location.search);
            this.searchQuery = params.get('search') || '';
            this.filters.status = params.get('status') || '';
            this.filters.assignee = params.get('assignee') || '';
        },
        
        updateURL() {
            const params = new URLSearchParams();
            if (this.searchQuery) params.set('search', this.searchQuery);
            if (this.filters.status) params.set('status', this.filters.status);
            if (this.filters.assignee) params.set('assignee', this.filters.assignee);
            
            const newURL = `${window.location.pathname}${params.toString() ? '?' + params.toString() : ''}`;
            history.replaceState(null, '', newURL);
        }
    }));
    
    // Bulk operations component
    Alpine.data('bulkActions', () => ({
        selectedCards: [],
        
        init() {
            // Listen for card selection events
            document.addEventListener('card-selected', (e) => {
                this.handleCardSelection(e.detail.cardId, e.detail.selected);
            });
            
            // Keyboard shortcuts
            document.addEventListener('keydown', (e) => {
                if (e.ctrlKey || e.metaKey) {
                    switch(e.key) {
                        case 'a':
                            e.preventDefault();
                            this.selectAll();
                            break;
                        case 'd':
                            e.preventDefault();
                            this.clearSelection();
                            break;
                    }
                }
                
                if (e.key === 'Escape') {
                    this.clearSelection();
                }
            });
        },
        
        handleCardSelection(cardId, selected) {
            if (selected) {
                if (!this.selectedCards.includes(cardId)) {
                    this.selectedCards.push(cardId);
                }
            } else {
                this.selectedCards = this.selectedCards.filter(id => id !== cardId);
            }
        },
        
        selectAll() {
            const visibleCards = document.querySelectorAll('.kanban-card:not([style*="display: none"])');
            this.selectedCards = Array.from(visibleCards).map(card => card.dataset.id);
            
            // Update card states
            visibleCards.forEach(card => {
                const checkbox = card.querySelector('.kanban-card-checkbox');
                if (checkbox) {
                    checkbox.checked = true;
                    card.classList.add('selected');
                }
            });
        },
        
        clearSelection() {
            this.selectedCards = [];
            document.querySelectorAll('.kanban-card').forEach(card => {
                const checkbox = card.querySelector('.kanban-card-checkbox');
                if (checkbox) {
                    checkbox.checked = false;
                    card.classList.remove('selected');
                }
            });
        },
        
        async bulkAssign(userId) {
            if (!userId || this.selectedCards.length === 0) return;
            
            try {
                const response = await fetch('/admin/api/bulk-assign', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': this.getCSRFToken()
                    },
                    body: JSON.stringify({
                        card_ids: this.selectedCards,
                        user_id: userId
                    })
                });
                
                if (response.ok) {
                    this.showToast('Заявки успешно назначены');
                    this.refreshKanban();
                    this.clearSelection();
                }
            } catch (error) {
                this.showToast('Ошибка при назначении заявок', 'error');
            }
        },
        
        async bulkChangeStatus(status) {
            if (!status || this.selectedCards.length === 0) return;
            
            try {
                const response = await fetch('/admin/api/bulk-status', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': this.getCSRFToken()
                    },
                    body: JSON.stringify({
                        card_ids: this.selectedCards,
                        status: status
                    })
                });
                
                if (response.ok) {
                    this.showToast('Статус заявок обновлен');
                    this.refreshKanban();
                    this.clearSelection();
                }
            } catch (error) {
                this.showToast('Ошибка при обновлении статуса', 'error');
            }
        },
        
        exportSelected() {
            if (this.selectedCards.length === 0) return;
            
            const params = new URLSearchParams();
            params.set('card_ids', this.selectedCards.join(','));
            
            window.open(`/admin/api/export-requests?${params.toString()}`, '_blank');
        },
        
        getCSRFToken() {
            return document.querySelector('meta[name="csrf-token"]')?.content || '';
        },
        
        showToast(message, type = 'success') {
            if (window.notyf) {
                window.notyf[type](message);
            }
        },
        
        refreshKanban() {
            htmx.trigger('#kanban-board-container', 'updateKanban');
        }
    }));
    
    // Individual card component
    Alpine.data('kanbanCard', (cardId) => ({
        cardId: cardId,
        isSelected: false,
        
        toggleSelection() {
            this.isSelected = !this.isSelected;
            
            // Dispatch selection event for bulk operations
            document.dispatchEvent(new CustomEvent('card-selected', {
                detail: {
                    cardId: this.cardId,
                    selected: this.isSelected
                }
            }));
        },
        
        handleCardClick(event) {
            // Don't open slide-over if clicking checkbox
            if (event.target.type === 'checkbox') {
                return;
            }
            
            // Check if Ctrl/Cmd is held for multi-selection
            if (event.ctrlKey || event.metaKey) {
                event.preventDefault();
                this.toggleSelection();
                return;
            }
        }
    }));
});

// Enhanced Drag & Drop with mobile support
document.addEventListener('DOMContentLoaded', function() {
    initializeDragDrop();
    initializeMobileSidebar();
    initializeTouchGestures();
    initializeThemeToggle();
    initializePWA();
});

function initializeThemeToggle() {
    const themeToggle = document.getElementById('theme-toggle');
    const themeIcon = document.getElementById('theme-icon');
    const body = document.body;
    
    // Load saved theme or default to dark
    const savedTheme = localStorage.getItem('theme') || 'dark';
    setTheme(savedTheme);
    
    if (themeToggle) {
        themeToggle.addEventListener('click', () => {
            const currentTheme = body.classList.contains('light') ? 'light' : 'dark';
            const newTheme = currentTheme === 'light' ? 'dark' : 'light';
            setTheme(newTheme);
            localStorage.setItem('theme', newTheme);
        });
    }
    
    function setTheme(theme) {
        if (theme === 'light') {
            body.classList.add('light');
            body.classList.remove('dark');
            if (themeIcon) {
                themeIcon.className = 'bx bx-sun';
            }
        } else {
            body.classList.add('dark');
            body.classList.remove('light');
            if (themeIcon) {
                themeIcon.className = 'bx bx-moon';
            }
        }
    }
}

function initializeDragDrop() {
    const kanbanColumns = document.querySelectorAll('.kanban-column-body');
    
    kanbanColumns.forEach(column => {
        if (window.Sortable) {
            new Sortable(column, {
                group: 'kanban',
                animation: 200,
                ghostClass: 'kanban-card-ghost',
                chosenClass: 'kanban-card-chosen',
                dragClass: 'kanban-card-drag',
                forceFallback: true, // Better mobile support
                fallbackTolerance: 3,
                
                onStart: function(evt) {
                    document.body.classList.add('dragging');
                    evt.item.classList.add('dragging');
                },
                
                onEnd: function(evt) {
                    document.body.classList.remove('dragging');
                    evt.item.classList.remove('dragging');
                    
                    if (evt.from !== evt.to) {
                        updateCardStatus(evt.item.dataset.id, evt.to.dataset.status);
                    }
                },
                
                onMove: function(evt) {
                    // Add visual feedback during drag
                    const draggedElement = evt.dragged;
                    const relatedElement = evt.related;
                    
                    if (relatedElement && relatedElement.classList.contains('kanban-card')) {
                        relatedElement.style.transform = 'translateY(10px)';
                        setTimeout(() => {
                            relatedElement.style.transform = '';
                        }, 200);
                    }
                }
            });
        }
    });
}

function initializeMobileSidebar() {
    const sidebar = document.getElementById('sidebar');
    const expandBtn = document.getElementById('sidebar-expand-btn');
    const overlay = document.querySelector('.mobile-sidebar-overlay') || createSidebarOverlay();
    
    if (expandBtn) {
        expandBtn.addEventListener('click', () => {
            sidebar.classList.add('open');
            overlay.classList.add('active');
            document.body.style.overflow = 'hidden';
        });
    }
    
    overlay.addEventListener('click', () => {
        closeMobileSidebar();
    });
    
    // Close sidebar on escape key
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && sidebar.classList.contains('open')) {
            closeMobileSidebar();
        }
    });
    
    function closeMobileSidebar() {
        sidebar.classList.remove('open');
        overlay.classList.remove('active');
        document.body.style.overflow = '';
    }
    
    function createSidebarOverlay() {
        const overlay = document.createElement('div');
        overlay.className = 'mobile-sidebar-overlay';
        document.body.appendChild(overlay);
        return overlay;
    }
}

function initializeTouchGestures() {
    let startX, startY, currentCard;
    
    document.addEventListener('touchstart', (e) => {
        const card = e.target.closest('.kanban-card');
        if (!card) return;
        
        currentCard = card;
        startX = e.touches[0].clientX;
        startY = e.touches[0].clientY;
    });
    
    document.addEventListener('touchmove', (e) => {
        if (!currentCard) return;
        
        const touchX = e.touches[0].clientX;
        const touchY = e.touches[0].clientY;
        const deltaX = touchX - startX;
        const deltaY = touchY - startY;
        
        // Only handle horizontal swipes
        if (Math.abs(deltaX) > Math.abs(deltaY) && Math.abs(deltaX) > 30) {
            e.preventDefault();
            
            if (deltaX > 0) {
                currentCard.classList.add('swipe-right');
                currentCard.classList.remove('swipe-left');
            } else {
                currentCard.classList.add('swipe-left');
                currentCard.classList.remove('swipe-right');
            }
        }
    });
    
    document.addEventListener('touchend', (e) => {
        if (!currentCard) return;
        
        const deltaX = e.changedTouches[0].clientX - startX;
        
        if (Math.abs(deltaX) > 100) {
            // Trigger action based on swipe direction
            if (deltaX > 0) {
                // Swipe right - quick assign or mark complete
                handleSwipeAction(currentCard, 'right');
            } else {
                // Swipe left - quick delete or archive
                handleSwipeAction(currentCard, 'left');
            }
        }
        
        // Reset card position
        currentCard.classList.remove('swipe-left', 'swipe-right');
        currentCard = null;
    });
}

function handleSwipeAction(card, direction) {
    const cardId = card.dataset.id;
    
    if (direction === 'right') {
        // Quick complete action
        updateCardStatus(cardId, 'completed');
    } else {
        // Quick archive action
        updateCardStatus(cardId, 'cancelled');
    }
}

async function updateCardStatus(cardId, newStatus) {
    try {
        const response = await fetch(`/admin/api/update-status`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': document.querySelector('meta[name="csrf-token"]')?.content || ''
            },
            body: JSON.stringify({
                card_id: cardId,
                status: newStatus
            })
        });
        
        if (response.ok) {
            // Show success toast
            if (window.notyf) {
                window.notyf.success('Статус обновлен');
            }
            
            // Trigger kanban refresh
            htmx.trigger('#kanban-board-container', 'updateKanban');
        }
    } catch (error) {
        console.error('Error updating card status:', error);
        if (window.notyf) {
            window.notyf.error('Ошибка при обновлении статуса');
        }
    }
}

// Utility functions
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

// Performance optimization for mobile
if ('serviceWorker' in navigator) {
    window.addEventListener('load', () => {
        navigator.serviceWorker.register('/static/sw.js')
            .then(registration => {
                console.log('SW registered: ', registration);
            })
            .catch(registrationError => {
                console.log('SW registration failed: ', registrationError);
            });
    });
}

function initializePWA() {
    let deferredPrompt;
    
    // Listen for the beforeinstallprompt event
    window.addEventListener('beforeinstallprompt', (e) => {
        // Prevent the mini-infobar from appearing on mobile
        e.preventDefault();
        // Store the event so it can be triggered later
        deferredPrompt = e;
        
        // Show install button if not already installed
        if (!window.navigator.standalone && !window.matchMedia('(display-mode: standalone)').matches) {
            showInstallButton();
        }
    });
    
    // Check if app is already installed
    window.addEventListener('appinstalled', (e) => {
        hideInstallButton();
        if (window.notyf) {
            window.notyf.success('Приложение успешно установлено!');
        }
    });
    
    function showInstallButton() {
        // Create install button if it doesn't exist
        if (!document.getElementById('pwa-install-btn')) {
            const installBtn = document.createElement('button');
            installBtn.id = 'pwa-install-btn';
            installBtn.className = 'btn btn-sm btn-secondary';
            installBtn.style.cssText = `
                position: fixed;
                bottom: 20px;
                right: 20px;
                z-index: 1000;
                border-radius: 50px;
                padding: 12px 20px;
                box-shadow: var(--shadow-lg);
                display: flex;
                align-items: center;
                gap: 8px;
            `;
            installBtn.innerHTML = '<i class="bx bx-download"></i><span>Установить</span>';
            
            installBtn.addEventListener('click', async () => {
                if (deferredPrompt) {
                    deferredPrompt.prompt();
                    const { outcome } = await deferredPrompt.userChoice;
                    
                    if (outcome === 'accepted') {
                        if (window.notyf) {
                            window.notyf.success('Приложение устанавливается...');
                        }
                    }
                    
                    deferredPrompt = null;
                    hideInstallButton();
                }
            });
            
            document.body.appendChild(installBtn);
            
            // Auto-hide after 10 seconds
            setTimeout(() => {
                if (document.getElementById('pwa-install-btn')) {
                    hideInstallButton();
                }
            }, 10000);
        }
    }
    
    function hideInstallButton() {
        const installBtn = document.getElementById('pwa-install-btn');
        if (installBtn) {
            installBtn.style.opacity = '0';
            setTimeout(() => {
                installBtn.remove();
            }, 300);
        }
    }
}