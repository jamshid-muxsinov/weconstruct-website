// src/static/js/kanban-enhanced.js

document.addEventListener('DOMContentLoaded', function () {
    initializeKanban();
});

document.body.addEventListener('htmx:afterSwap', function(event) {
    if (event.detail.target.id === 'kanban-board-container') {
        initializeKanban();
    }
});

// Инициализируем Alpine.js компоненты один раз
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
    if (Alpine.store('kanbanManager')) return; // Предотвращаем повторную инициализацию

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

        // <<< КЛЮЧЕВОЕ ИСПРАВЛЕНИЕ ЗДЕСЬ >>>
        handleCardClick(event, cardId) {
            // Если нажат Ctrl или Cmd (для Mac), работаем с выделением
            if (event.ctrlKey || event.metaKey) {
                // ПРЕДОТВРАЩАЕМ стандартное поведение клика (и для HTMX, и для браузера)
                event.preventDefault();
                event.stopPropagation();
                
                this.selectedCards.has(cardId) ? this.selectedCards.delete(cardId) : this.selectedCards.add(cardId);
            } 
            // Если кликнули по ссылке, позволяем ей сработать
            else if (event.target.closest('a')) {
                event.stopPropagation();
            }
            // Иначе - это обычный клик, и мы ничего не делаем,
            // позволяя сработать стандартному триггеру hx-trigger="click"
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