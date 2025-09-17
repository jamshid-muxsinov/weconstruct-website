// src/static/js/kanban-enhanced.js

document.addEventListener('alpine:init', () => {

    const notyf = new Notyf({
        duration: 3500,
        position: { x: 'right', y: 'top' },
        dismissible: true
    });

    Alpine.store('kanbanManager', {
        selectedCards: new Set(),

        // Логика клика остается, она нужна для множественного выбора
        handleCardClick(cardElement, cardId, event) {
            if (event.ctrlKey || event.metaKey) {
                // Используем новый синтаксис для обновления, чтобы Alpine реагировал
                const newSet = new Set(this.selectedCards);
                if (newSet.has(cardId)) {
                    newSet.delete(cardId);
                } else {
                    newSet.add(cardId);
                }
                this.selectedCards = newSet;
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
            if (!userId || this.selectedIds.length === 0) return;
            htmx.ajax('POST', '/api/bulk-assign', {
                values: { card_ids: this.selectedIds, user_id: parseInt(userId) },
                swap: 'none'
            }).then(() => {
                notyf.success(`Назначено ${this.selectedIds.length} заявок.`);
                this.clearSelection();
                htmx.trigger(document.body, 'updateKanban');
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
                htmx.trigger(document.body, 'updateKanban');
            });
        }
    });
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
                    const notyf = new Notyf({ duration: 3500, position: { x: 'right', y: 'top' }, dismissible: true });
                    notyf.success('Статус заявки обновлен');
                });
            }
        });
    });
}


// Этот слушатель инициализирует Sortable.js при первой загрузке
document.addEventListener('DOMContentLoaded', () => initializeKanban());

// Этот слушатель ре-инициализирует Sortable.js и сбрасывает выбор
// после каждого обновления доски от HTMX
document.body.addEventListener('htmx:afterSwap', function(event) {
    if (event.detail.target.id === 'kanban-board-container') {
        initializeKanban();
        // Сбрасываем выделение, так как карточки были полностью перерисованы
        if (window.Alpine && Alpine.store('kanbanManager')) {
            Alpine.store('kanbanManager').clearSelection();
        }
    }
});