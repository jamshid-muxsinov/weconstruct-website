// src/static/js/kanban-enhanced.js

const notyf = new Notyf({
    duration: 3500,
    position: { x: 'right', y: 'top' },
    dismissible: true
});

function initializeKanban() {
    const kanbanColumns = document.querySelectorAll('.kanban-column-body');
    if (kanbanColumns.length === 0) return;

    kanbanColumns.forEach(column => {
        if (column.sortableInstance) {
            column.sortableInstance.destroy();
        }
        
        column.sortableInstance = new Sortable(column, {
            group: 'kanban',
            animation: 150,
            ghostClass: 'kanban-card-ghost',
            chosenClass: 'kanban-card-chosen',
            dragClass: 'kanban-card-drag',
            onEnd: function (evt) {
                const cardId = evt.item.dataset.id;
                const newStatus = evt.to.parentElement.dataset.status;

                if (!cardId || !newStatus) {
                    console.error('Card ID or new status is missing.');
                    return;
                }
                
                htmx.ajax('POST', '/api/update-status', {
                    values: { card_id: parseInt(cardId), status: newStatus },
                    swap: 'none'
                }).then(() => {
                    notyf.success('Статус заявки обновлен');
                    updateColumnCounts();
                }).catch(() => {
                    notyf.error('Ошибка при обновлении статуса');
                });
            }
        });
    });
}

function updateColumnCounts() {
    document.querySelectorAll('.kanban-column').forEach(col => {
        const count = col.querySelectorAll('.kanban-card:not([style*="display: none"])').length;
        const countElement = col.querySelector('.kanban-count');
        if (countElement) {
            countElement.textContent = count;
        }
    });
}

function initializeAlpineComponents() {
    if (window.Alpine && Alpine.store('kanbanManager')) {
        return;
    }

    Alpine.store('kanbanManager', {
        searchQuery: '',
        activeFilters: { assignee: null },
        selectedCards: new Set(),

        applyFilters() {
            const currentUserId = document.querySelector('meta[name="current-user-id"]')?.content;
            document.querySelectorAll('.kanban-card').forEach(card => {
                const searchMatch = !this.searchQuery || 
                                    (card.dataset.clientName + card.dataset.phone + card.dataset.id)
                                    .toLowerCase().includes(this.searchQuery.toLowerCase());
                                    
                const assigneeMatch = !this.activeFilters.assignee || 
                                      (this.activeFilters.assignee === 'me' && card.dataset.assignee === currentUserId);
                                      
                card.style.display = searchMatch && assigneeMatch ? '' : 'none';
            });
            updateColumnCounts();
        },

        handleCardClick(cardElement, cardId, event) {
            if (event.ctrlKey || event.metaKey) {
                const newSelectedCards = new Set(this.selectedCards);
                if (newSelectedCards.has(cardId)) {
                    newSelectedCards.delete(cardId);
                } else {
                    newSelectedCards.add(cardId);
                }
                this.selectedCards = newSelectedCards;
            } 
            else if (!event.target.closest('a')) {
                htmx.trigger(cardElement, 'openDetails');
            }
        },
        
        get selectedIds() { 
            return Array.from(this.selectedCards); 
        },

        clearSelection() { 
            this.selectedCards = new Set();
        },

        bulkAssign(userId) {
            if (!userId || this.selectedCards.size === 0) return;
            htmx.ajax('POST', '/api/bulk-assign', {
                values: { card_ids: this.selectedIds, user_id: parseInt(userId) },
                swap: 'none'
            }).then(() => {
                notyf.success(`Назначено ${this.selectedCards.size} заявок.`);
                this.clearSelection();
                htmx.trigger(document.body, 'updateKanban');
            });
        },
        
        bulkUpdateStatus(status) {
            if (!status || this.selectedCards.size === 0) return;
             htmx.ajax('POST', '/api/bulk-status', {
                values: { card_ids: this.selectedIds, status: status },
                swap: 'none'
            }).then(() => {
                notyf.success(`Статус ${this.selectedCards.size} заявок обновлен.`);
                this.clearSelection();
                htmx.trigger(document.body, 'updateKanban');
            });
        }
    });

    // --- НОВОЕ: Автоматический "наблюдатель" за фильтрами ---
    // Эта функция будет сама запускать applyFilters(), когда searchQuery или activeFilters изменятся.
    Alpine.effect(() => {
        const store = Alpine.store('kanbanManager');
        // Просто обращаемся к переменным, чтобы Alpine "узнал", что за ними нужно следить
        const query = store.searchQuery;
        const assignee = store.activeFilters.assignee;
        
        // Запускаем фильтрацию
        store.applyFilters();
    });
}

document.addEventListener('DOMContentLoaded', function () {
    if (typeof Alpine !== 'undefined') {
        initializeAlpineComponents();
    } else {
        console.error("Alpine.js is not loaded.");
    }
    
    initializeKanban();
});

document.body.addEventListener('htmx:afterSwap', function(event) {
    if (event.detail.target.id === 'kanban-board-container') {
        initializeKanban();
    }
});