// Enhanced Kanban Board Functionality
document.addEventListener('alpine:init', () => {
    Alpine.data('kanbanFilters', () => ({
        searchQuery: '',
        filters: { assignee: '', status: '', priority: '' },
        toggleFilter(type, value) { this.filters[type] = this.filters[type] === value ? '' : value; this.filterCards(); },
        clearFilters() { this.filters = { assignee: '', status: '', priority: '' }; this.searchQuery = ''; this.filterCards(); },
        hasActiveFilters() { return this.searchQuery || Object.values(this.filters).some(f => f); },
        filterCards() {
            document.querySelectorAll('.kanban-card').forEach(card => {
                const searchMatch = !this.searchQuery || (card.dataset.clientName + card.dataset.phone + card.dataset.id).toLowerCase().includes(this.searchQuery.toLowerCase());
                const statusMatch = !this.filters.status || card.dataset.status === this.filters.status;
                const assigneeMatch = this.filters.assignee !== 'me' || card.dataset.assignee === document.querySelector('meta[name="current-user-id"]')?.content;
                card.style.display = searchMatch && statusMatch && assigneeMatch ? '' : 'none';
            });
            this.updateColumnCounts();
        },
        updateColumnCounts() {
            document.querySelectorAll('.kanban-column').forEach(col => {
                const count = col.querySelectorAll('.kanban-card:not([style*="display: none"])').length;
                col.querySelector('.kanban-count').textContent = count;
            });
        }
    }));
    Alpine.data('bulkActions', () => ({
        selectedCards: [],
        init() { this.$watch('selectedCards', () => this.updateCardStyles()); },
        toggleSelection(cardId) {
            const index = this.selectedCards.indexOf(cardId);
            if (index > -1) this.selectedCards.splice(index, 1);
            else this.selectedCards.push(cardId);
        },
        updateCardStyles() {
            document.querySelectorAll('.kanban-card').forEach(card => {
                if (this.selectedCards.includes(card.dataset.id)) card.classList.add('selected');
                else card.classList.remove('selected');
            });
        },
        clearSelection() { this.selectedCards = []; }
    }));
    Alpine.data('kanbanCard', (id) => ({
        cardId: id,
        handleCardClick(event, bulkActions) {
            if (event.ctrlKey || event.metaKey) {
                event.preventDefault();
                bulkActions.toggleSelection(this.cardId);
            } else {
                htmx.trigger(event.currentTarget, 'click');
            }
        }
    }));
});

// --- KEYBOARD SHORTCUTS & PWA ---
function showKeyboardShortcuts() {
    htmx.ajax('GET', '/admin/htmx/keyboard-shortcuts', { target: '#modal-body-content' })
        .then(() => document.getElementById('modal-overlay').classList.add('show'));
}

document.addEventListener('keydown', (e) => {
    if (document.activeElement.tagName === 'INPUT' || document.activeElement.tagName === 'TEXTAREA') return;
    if (e.key === '?') { e.preventDefault(); showKeyboardShortcuts(); }
    if (e.key === '/') { e.preventDefault(); document.querySelector('.search-box input')?.focus(); }
});

function initializeThemeToggle() {
    const themeToggle = document.getElementById('theme-toggle');
    const themeIcon = document.getElementById('theme-icon');
    const body = document.body;
    const setTheme = (theme) => {
        body.classList.toggle('light', theme === 'light');
        themeIcon.className = theme === 'light' ? 'bx bx-sun' : 'bx bx-moon';
        localStorage.setItem('theme', theme);
    };
    setTheme(localStorage.getItem('theme') || 'dark');
    themeToggle.addEventListener('click', () => setTheme(body.classList.contains('light') ? 'dark' : 'light'));
}

function initializePWA() {
    if ('serviceWorker' in navigator) {
        navigator.serviceWorker.register('/static/sw.js').catch(err => console.error('Service Worker registration failed:', err));
    }
}

document.addEventListener('DOMContentLoaded', () => {
    initializeThemeToggle();
    initializePWA();
});