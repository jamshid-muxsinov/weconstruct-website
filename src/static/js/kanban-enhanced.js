/* --- src/static/js/kanban-enhanced.js --- */

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
                
                // Получаем новую колонку и её статус
                const newColumn = evt.to.closest('.kanban-column');
                const newStatus = newColumn.dataset.status;
                const oldStatus = evt.from.closest('.kanban-column').dataset.status;

                // Если статус не изменился, ничего не делаем
                if (newStatus === oldStatus) return;

                // Визуально меняем цвет полоски статуса сразу (для плавности)
                itemEl.classList.remove(`status-${oldStatus}`);
                itemEl.classList.add(`status-${newStatus}`);

                // Отправляем запрос на сервер
                fetch('/api/update-status', {
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
                        // Успех
                        const notyf = new Notyf({position: {x:'right', y:'top'}});
                        notyf.success('Статус обновлен');
                    } else {
                        // Ошибка сервера
                        throw new Error('Server error');
                    }
                })
                .catch(error => {
                    console.error('Error:', error);
                    const notyf = new Notyf({position: {x:'right', y:'top'}});
                    notyf.error('Ошибка сохранения. Возвращаем карточку.');
                    // Возвращаем карточку назад при ошибке
                    evt.from.appendChild(itemEl);
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