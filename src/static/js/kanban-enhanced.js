// src/static/js/kanban-enhanced.js

document.addEventListener('DOMContentLoaded', function () {
    initializeKanban();
    // Инициализируем Alpine.js компоненты здесь, чтобы они были доступны сразу
    if (typeof Alpine !== 'undefined') {
        initializeAlpineComponents();
    }
});

document.body.addEventListener('htmx:afterSwap', function(event) {
    // Переинициализируем канбан-доску после того, как ее содержимое было обновлено
    if (event.detail.target.id === 'kanban-board-container') {
        initializeKanban();
    }
});

function initializeKanban() {
    const kanbanColumns = document.querySelectorAll('.kanban-column-body');
    if (kanbanColumns.length === 0) return;

    kanbanColumns.forEach(column => {
        // Избегаем повторной инициализации, уничтожая старый экземпляр
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
                const card = evt.item;
                const toColumn = evt.to;
                const newStatus = toColumn.parentElement.dataset.status;
                const cardId = card.dataset.id;

                if (!cardId || !newStatus) {
                    console.error('Card ID or new status is missing!');
                    return;
                }
                
                htmx.ajax('POST', '/api/update-status', {
                    values: { card_id: parseInt(cardId), status: newStatus },
                    swap: 'none'
                }).then(() => {
                    notyf.success('Статус обновлен');
                    updateColumnCounts();
                }).catch(error => {
                    notyf.error('Ошибка обновления');
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
        if (countElement) countElement.textContent = count;
    });
}

// Инициализация компонентов Alpine.js
function initializeAlpineComponents() {
    if (typeof Alpine.data('kanbanManager') !== 'undefined') return;

    Alpine.data('kanbanManager', () => ({
        searchQuery: '',
        activeFilters: { assignee: null },
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

        // <<< КЛЮЧЕВОЕ ИСПРАВЛЕНИЕ ЗДЕСЬ >>>
        handleCardClick(cardElement, cardId, event) {
            // Если нажат Ctrl или Cmd (для Mac), работаем с выделением
            if (event.ctrlKey || event.metaKey) {
                event.preventDefault(); // Запрещаем HTMX реагировать
                this.selectedCards.has(cardId) ? this.selectedCards.delete(cardId) : this.selectedCards.add(cardId);
            } 
            // Если это обычный клик и он не был по ссылке внутри карточки
            else if (!event.target.closest('a')) {
                // Мы вручную даем команду HTMX открыть окно
                htmx.trigger(cardElement, 'openDetails');
            }
            // Если кликнули по ссылке, ничего не делаем, даем ссылке сработать
        },
        
        get selectedIds() { return Array.from(this.selectedCards); },
        clearSelection() { this.selectedCards.clear(); },

        // Массовые действия теперь триггерят обновление доски
        bulkAssign(userId) {
            if (!userId || this.selectedIds.length === 0) return;
            htmx.ajax('POST', '/api/bulk-assign', {
                values: { card_ids: this.selectedIds, user_id: parseInt(userId) },
                swap: 'none'
            }).then(() => {
                notyf.success(`Назначено ${this.selectedIds.length} заявок.`);
                this.clearSelection();
                htmx.trigger('#kanban-board-container', 'updateKanban');
            });
        },
        
        bulkUpdateStatus(status) {
            if (!status || this.selectedIds.length === 0) return;
             htmx.ajax('POST', '/api/bulk-status', {
                values: { card_ids: this.selectedIds, status: status },
                swap: 'none'
            }).then(() => {
                notyf.success(`Статус ${this.selectedIds.length} заявок обновлен.`);
                this.clearSelection();
                htmx.trigger('#kanban-board-container', 'updateKanban');
            });
        }
    }));
}