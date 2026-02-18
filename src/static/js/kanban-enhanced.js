/* --- src/static/js/kanban-enhanced.js --- */

const pendingStatusUpdates = new Set();

function initKanbanSortable() {
    const columns = document.querySelectorAll('.kanban-column-body');
    const csrfToken = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content');

    columns.forEach(col => {
        // Уничтожаем старый инстанс, если был, чтобы не дублировать события
        if (col.sortable) col.sortable.destroy();

        col.sortable = new Sortable(col, {
            group: 'kanban', // Разрешает перетаскивание между колонками
            animation: 150,
            ghostClass: 'kanban-card-ghost',
            delay: 100, // Небольшая задержка, чтобы не путать с кликом
            delayOnTouchOnly: true,
            onEnd: function (evt) {
                const itemEl = evt.item;
                const cardId = itemEl.dataset.id;
                const oldNextSibling = evt.oldIndex < evt.from.children.length ? evt.from.children[evt.oldIndex] : null;
                
                // Получаем новую колонку и её статус
                const newColumn = evt.to.closest('.kanban-column');
                const newStatus = newColumn.dataset.status;
                const oldStatus = evt.from.closest('.kanban-column').dataset.status;

                // Если статус не изменился, ничего не делаем
                if (newStatus === oldStatus) return;
                if (!csrfToken) {
                    const notyfNoToken = window.notyf || new Notyf({ position: { x: 'right', y: 'top' } });
                    notyfNoToken.error('CSRF токен не найден. Обновите страницу.');
                    if (oldNextSibling) evt.from.insertBefore(itemEl, oldNextSibling);
                    else evt.from.appendChild(itemEl);
                    return;
                }
                if (pendingStatusUpdates.has(cardId)) {
                    const notyfPending = window.notyf || new Notyf({ position: { x: 'right', y: 'top' } });
                    notyfPending.error('Подождите, предыдущее обновление еще выполняется.');
                    if (oldNextSibling) evt.from.insertBefore(itemEl, oldNextSibling);
                    else evt.from.appendChild(itemEl);
                    return;
                }

                // Визуально меняем цвет полоски статуса сразу (для плавности)
                itemEl.classList.remove(`status-${oldStatus}`);
                itemEl.classList.add(`status-${newStatus}`);
                pendingStatusUpdates.add(cardId);

                // Отправляем запрос на сервер
                const requestFn = window.adminApiFetch || fetch;
                requestFn('/api/update-status', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': csrfToken // Обязательно для защиты
                    },
                    body: JSON.stringify({
                        id: parseInt(cardId),
                        status: newStatus
                    })
                })
                .then(response => {
                    if (response.ok) {
                        const notyf = window.notyf || new Notyf({ position: { x: 'right', y: 'top' } });
                        notyf.success('Статус обновлен');
                    } else {
                        throw new Error(`Server error: ${response.status}`);
                    }
                })
                .catch(error => {
                    console.error('Error:', error);
                    const notyf = window.notyf || new Notyf({ position: { x: 'right', y: 'top' } });
                    notyf.error('Ошибка сохранения. Возвращаем карточку.');
                    // Возвращаем карточку назад при ошибке
                    itemEl.classList.remove(`status-${newStatus}`);
                    itemEl.classList.add(`status-${oldStatus}`);
                    if (oldNextSibling) evt.from.insertBefore(itemEl, oldNextSibling);
                    else evt.from.appendChild(itemEl);
                })
                .finally(() => {
                    pendingStatusUpdates.delete(cardId);
                });
            }
        });
    });
}

// Инициализация при загрузке страницы
document.addEventListener('DOMContentLoaded', initKanbanSortable);

// Инициализация после обновлений HTMX (например, фильтрации)
document.body.addEventListener('htmx:afterSwap', (evt) => {
    if (evt.detail.target.id === 'kanban-board-container') {
        initKanbanSortable();
    }
});
