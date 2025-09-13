// src/static/js/kanban-enhanced.js

// Мы выносим всю логику инициализации внутрь этого слушателя.
// Он сработает в нужный момент жизненного цикла Alpine.js.
document.addEventListener('alpine:init', () => {

    const notyf = new Notyf({
        duration: 3500,
        position: { x: 'right', y: 'top' },
        dismissible: true
    });

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
            // !!! ИСПРАВЛЕНИЕ 1: Добавлен слэш в начало пути !!!
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
             // !!! ИСПРАВЛЕНИЕ 2: Добавлен слэш в начало пути !!!
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

    // Автоматический "наблюдатель" за фильтрами
    Alpine.effect(() => {
        const store = Alpine.store('kanbanManager');
        const query = store.searchQuery;
        const assignee = store.activeFilters.assignee;
        store.applyFilters();
    });

});


// Эти функции остаются за пределами `alpine:init`, так как они вызываются независимо.
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
                
                // !!! ИСПРАВЛЕНИЕ 3: Добавлен слэш в начало пути !!!
                htmx.ajax('POST', '/api/update-status', {
                    values: { card_id: parseInt(cardId), status: newStatus },
                    swap: 'none'
                }).then(() => {
                    // Используем Notyf, который теперь доступен
                    const notyf = new Notyf({ duration: 3500, position: { x: 'right', y: 'top' }, dismissible: true });
                    notyf.success('Статус заявки обновлен');
                    updateColumnCounts();
                }).catch(() => {
                    const notyf = new Notyf({ duration: 3500, position: { x: 'right', y: 'top' }, dismissible: true });
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

// Этот слушатель инициализирует Sortable.js при первой загрузке
document.addEventListener('DOMContentLoaded', function () {
    initializeKanban();
});

// Этот слушатель ре-инициализирует Sortable.js после обновлений от HTMX
document.body.addEventListener('htmx:afterSwap', function(event) {
    if (event.detail.target.id === 'kanban-board-container') {
        initializeKanban();
        // После загрузки контента доски, запускаем фильтрацию на случай, если
        // в поле поиска или фильтрах уже есть значения.
        if (window.Alpine && Alpine.store('kanbanManager')) {
            Alpine.store('kanbanManager').applyFilters();
        }
    }
});