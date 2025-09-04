// src/static/js/kanban-enhanced.js

document.addEventListener('DOMContentLoaded', function () {
    initializeKanban();
});

document.body.addEventListener('htmx:afterSwap', function(event) {
    // Re-initialize kanban after the container is swapped
    if (event.detail.target.id === 'kanban-board-container') {
        initializeKanban();
    }
});

function initializeKanban() {
    const kanbanColumns = document.querySelectorAll('.kanban-column-body');
    if (kanbanColumns.length === 0) return;

    kanbanColumns.forEach(column => {
        new Sortable(column, {
            group: 'kanban',
            animation: 150,
            ghostClass: 'kanban-card-ghost',
            chosenClass: 'kanban-card-chosen',
            dragClass: 'kanban-card-drag',
            onEnd: function (evt) {
                const card = evt.item;
                const toColumn = evt.to;
                const newStatus = toColumn.parentElement.dataset.status;
                const cardId = card.dataset.id;

                if (!cardId || !newStatus) {
                    console.error('Card ID or new status is missing!');
                    return;
                }
                
                // Используем HTMX для отправки запроса на обновление статуса
                htmx.ajax('POST', '/api/update-status', {
                    values: {
                        card_id: parseInt(cardId),
                        status: newStatus
                    },
                    swap: 'none' // Нам не нужно ничего обновлять в ответ
                }).then(data => {
                    // Показываем уведомление об успехе
                    notyf.success('Статус заявки обновлен!');
                    // Обновляем счетчики в колонках
                    updateColumnCounts();
                }).catch(error => {
                    notyf.error('Ошибка при обновлении статуса.');
                    // В случае ошибки, можно вернуть карточку обратно (опционально)
                    console.error("Error updating card status:", error);
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

// Alpine.js data for filters and bulk actions
document.addEventListener('alpine:init', () => {
    Alpine.data('kanbanManager', () => ({
        searchQuery: '',
        activeFilters: {
            assignee: null
        },
        selectedCards: new Set(),

        init() {
            this.$watch('searchQuery', () => this.applyFilters());
            this.$watch('activeFilters', () => this.applyFilters(), { deep: true });
        },

        toggleFilter(type, value) {
            this.activeFilters[type] = this.activeFilters[type] === value ? null : value;
        },

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

        toggleSelection(cardId, event) {
            if (event.ctrlKey || event.metaKey) {
                if (this.selectedCards.has(cardId)) {
                    this.selectedCards.delete(cardId);
                } else {
                    this.selectedCards.add(cardId);
                }
            } else if (!event.target.closest('a')) { // Не перехватываем клики по ссылкам
                 htmx.trigger(event.currentTarget, 'click');
            }
        },
        
        get selectedIds() {
            return Array.from(this.selectedCards);
        },

        clearSelection() {
            this.selectedCards.clear();
        },

        // Bulk actions would go here
        bulkAssign(userId) {
            if (!userId || this.selectedIds.length === 0) return;
            htmx.ajax('POST', '/admin/bulk-assign', {
                values: { card_ids: this.selectedIds, user_id: parseInt(userId) },
                target: '#kanban-board-container',
                swap: 'innerHTML'
            }).then(() => {
                notyf.success(`Назначено ${this.selectedIds.length} заявок.`);
                this.clearSelection();
            });
        },
        
        bulkUpdateStatus(status) {
            if (!status || this.selectedIds.length === 0) return;
             htmx.ajax('POST', '/admin/bulk-status', {
                values: { card_ids: this.selectedIds, status: status },
                target: '#kanban-board-container',
                swap: 'innerHTML'
            }).then(() => {
                notyf.success(`Статус ${this.selectedIds.length} заявок обновлен.`);
                this.clearSelection();
            });
        }
    }));
});