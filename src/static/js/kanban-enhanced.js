// src/static/js/kanban-enhanced.js

/**
 * Глобальная инициализация Notyf для уведомлений.
 */
const notyf = new Notyf({
    duration: 3500,
    position: { x: 'right', y: 'top' },
    dismissible: true
});

/**
 * Инициализирует функционал канбан-доски.
 * Эта функция будет вызываться при первой загрузке и после каждого обновления доски через HTMX.
 */
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

/**
 * Обновляет числовые счетчики в заголовках колонок канбана.
 */
function updateColumnCounts() {
    document.querySelectorAll('.kanban-column').forEach(col => {
        const count = col.querySelectorAll('.kanban-card:not([style*="display: none"])').length;
        const countElement = col.querySelector('.kanban-count');
        if (countElement) {
            countElement.textContent = count;
        }
    });
}

/**
 * Инициализирует глобальное хранилище Alpine.js для управления состоянием канбан-доски.
 * Эта функция должна вызываться только один раз.
 */
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
                // <<< ИЗМЕНЕНИЕ ЗДЕСЬ: Обеспечиваем реактивность для Set >>>
                // 1. Создаем новую копию Set из текущего состояния.
                const newSelectedCards = new Set(this.selectedCards);
                
                // 2. Модифицируем эту новую копию.
                if (newSelectedCards.has(cardId)) {
                    newSelectedCards.delete(cardId);
                } else {
                    newSelectedCards.add(cardId);
                }
                
                // 3. Присваиваем новую копию обратно в store.
                //    Именно это действие Alpine.js гарантированно отследит.
                this.selectedCards = newSelectedCards;
                // <<< КОНЕЦ ИЗМЕНЕНИЯ >>>
            } 
            else if (!event.target.closest('a')) {
                htmx.trigger(cardElement, 'openDetails');
            }
        },
        
        get selectedIds() { 
            return Array.from(this.selectedCards); 
        },

        clearSelection() { 
            this.selectedCards = new Set(); // Также заменяем на новый пустой Set
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
}

/**
 * Основная точка входа.
 */
document.addEventListener('DOMContentLoaded', function () {
    if (typeof Alpine !== 'undefined') {
        initializeAlpineComponents();
    } else {
        console.error("Alpine.js is not loaded.");
    }
    
    initializeKanban();
});

/**
 * Слушатель событий HTMX для ре-инициализации Sortable.js.
 */
document.body.addEventListener('htmx:afterSwap', function(event) {
    if (event.detail.target.id === 'kanban-board-container') {
        initializeKanban();
    }
});