// src/static/js/kanban-enhanced.js

document.addEventListener('alpine:init', () => {
    if (!window.notyf) {
        window.notyf = new Notyf({
            duration: 3500,
            position: { x: 'right', y: 'top' },
            dismissible: true
        });
    }

    Alpine.store('kanbanManager', {
        selectedCards: new Set(),

        handleCardClick(cardElement, cardId, event) {
            if (event.ctrlKey || event.metaKey) {
                event.preventDefault();
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
                document.getElementById('slide-over-container').classList.add('open');
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
            
            const params = new URLSearchParams();
            this.selectedIds.forEach(id => params.append('card_ids', id));
            params.append('user_id', userId);

            htmx.ajax('POST', '/api/bulk-assign', {
                body: params,
                swap: 'none'
            }).then(() => {
                window.notyf.success(`Назначено ${this.selectedIds.length} заявок.`);
                this.clearSelection();
                htmx.trigger(document.body, 'updateKanban');
            });
        },
        
        bulkUpdateStatus(status) {
            if (!status || this.selectedIds.length === 0) return;
            
            const params = new URLSearchParams();
            this.selectedIds.forEach(id => params.append('card_ids', id));
            params.append('status', status);

            htmx.ajax('POST', '/api/bulk-status', {
                body: params,
                swap: 'none'
            }).then(() => {
                window.notyf.success(`Статус ${this.selectedIds.length} заявок обновлен.`);
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
                const newStatus = evt.to.closest('.kanban-column').dataset.status;

                if (!cardId || !newStatus) return;
                
                const params = new URLSearchParams({ card_id: cardId, status: newStatus });

                htmx.ajax('POST', '/api/update-status', {
                    body: params,
                    swap: 'none'
                }).then(data => {
                }).catch(() => {
                    evt.from.insertBefore(evt.item, evt.from.children[evt.oldIndex]);
                    window.notyf.error('Не удалось изменить статус.');
                });
            }
        });
    });
}

document.addEventListener('DOMContentLoaded', initializeKanban);
document.body.addEventListener('htmx:afterSwap', function(event) {
    if (event.detail.target.id === 'kanban-board-container') {
        initializeKanban();
    }
});