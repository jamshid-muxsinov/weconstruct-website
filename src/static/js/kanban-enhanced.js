
document.addEventListener('DOMContentLoaded', function () {
    initializeKanban();
});

document.body.addEventListener('htmx:afterSwap', function(event) {
    if (event.detail.target.id === 'kanban-board-container') {
        initializeKanban();
    }
});

if (typeof Alpine !== 'undefined') {
    initializeAlpineComponents();
}

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

                if (!cardId || !newStatus) return;
                
                htmx.ajax('POST', '/api/update-status', {
                    values: { card_id: parseInt(cardId), status: newStatus },
                    swap: 'none'
                }).then(() => {
                    notyf.success('Статус обновлен');
                    updateColumnCounts();
                }).catch(() => notyf.error('Ошибка обновления'));
            }
        });
    });
}

function updateColumnCounts() {
    document.querySelectorAll('.kanban-column').forEach(col => {
        const count = col.querySelectorAll('.kanban-card:not([style*="display: none"])').length;
        const countElement = col.querySelector('.kanban-count');
        if (countElement) countElement.textContent = count;
    });
}

function initializeAlpineComponents() {
    if (Alpine.store('kanbanManager')) return;

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

        // <<< ФИНАЛЬНОЕ ИСПРАВЛЕНИЕ ЛОГИКИ КЛИКА >>>
        handleCardClick(cardElement, cardId, event) {
            // Если нажат Ctrl или Cmd (для Mac), работаем ТОЛЬКО с выделением
            if (event.ctrlKey || event.metaKey) {
                this.selectedCards.has(cardId) ? this.selectedCards.delete(cardId) : this.selectedCards.add(cardId);
            } 
            // Если это обычный клик и он НЕ был по ссылке внутри карточки
            else if (!event.target.closest('a')) {
                // Мы вручную даем команду HTMX сработать по кастомному событию
                htmx.trigger(cardElement, 'openDetails');
            }
            // Если кликнули по ссылке, ничего не делаем, даем ссылке сработать
        },
        
        get selectedIds() { return Array.from(this.selectedCards); },
        clearSelection() { this.selectedCards.clear(); },

        bulkAssign(userId) {
            if (!userId || this.selectedIds.size === 0) return;
            htmx.ajax('POST', '/api/bulk-assign', {
                values: { card_ids: this.selectedIds, user_id: parseInt(userId) },
                swap: 'none'
            }).then(() => {
                notyf.success(`Назначено ${this.selectedIds.size} заявок.`);
                this.clearSelection();
                htmx.trigger('#kanban-board-container', 'updateKanban');
            });
        },
        
        bulkUpdateStatus(status) {
            if (!status || this.selectedIds.size === 0) return;
             htmx.ajax('POST', '/api/bulk-status', {
                values: { card_ids: this.selectedIds, status: status },
                swap: 'none'
            }).then(() => {
                notyf.success(`Статус ${this.selectedIds.size} заявок обновлен.`);
                this.clearSelection();
                htmx.trigger('#kanban-board-container', 'updateKanban');
            });
        }
    });
}