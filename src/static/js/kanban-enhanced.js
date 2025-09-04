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
        // Если на колонке уже есть экземпляр Sortable, уничтожаем его перед новой инициализацией.
        // Это предотвращает дублирование обработчиков событий.
        if (column.sortableInstance) {
            column.sortableInstance.destroy();
        }
        
        // Создаем новый экземпляр Sortable.js для каждой колонки.
        column.sortableInstance = new Sortable(column, {
            group: 'kanban', // Позволяет перетаскивать карточки между колонками с этой же группой.
            animation: 150,
            ghostClass: 'kanban-card-ghost', // Класс для "тени" карточки при перетаскивании.
            chosenClass: 'kanban-card-chosen', // Класс для самой карточки, которую перетаскивают.
            dragClass: 'kanban-card-drag',
            onEnd: function (evt) {
                // Срабатывает после того, как карточку "бросили".
                const cardId = evt.item.dataset.id;
                const newStatus = evt.to.parentElement.dataset.status;

                if (!cardId || !newStatus) {
                    console.error('Card ID or new status is missing.');
                    return;
                }
                
                // Отправляем HTMX-запрос для обновления статуса на сервере.
                htmx.ajax('POST', '/api/update-status', {
                    values: { card_id: parseInt(cardId), status: newStatus },
                    swap: 'none' // Нам не нужно обновлять HTML в ответ на этот запрос.
                }).then(() => {
                    notyf.success('Статус заявки обновлен');
                    updateColumnCounts(); // Обновляем счетчики в колонках.
                }).catch(() => {
                    notyf.error('Ошибка при обновлении статуса');
                    // В случае ошибки можно было бы вернуть карточку на место, но для простоты просто покажем уведомление.
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
        // Считаем только видимые карточки, чтобы фильтрация работала корректно.
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
    // Предотвращаем повторную инициализацию, если Alpine.store уже существует.
    if (window.Alpine && Alpine.store('kanbanManager')) {
        return;
    }

    Alpine.store('kanbanManager', {
        searchQuery: '',
        activeFilters: { assignee: null },
        selectedCards: new Set(),

        /**
         * Применяет фильтры к карточкам на доске.
         */
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

        /**
         * --- КЛЮЧЕВАЯ ИСПРАВЛЕННАЯ ЛОГИКА ---
         * Обрабатывает клики на карточках, разделяя логику выделения и открытия деталей.
         * @param {HTMLElement} cardElement - DOM-элемент карточки, на которую кликнули.
         * @param {string} cardId - ID заявки.
         * @param {MouseEvent} event - Объект события клика.
         */
        handleCardClick(cardElement, cardId, event) {
            // 1. Если нажат Ctrl или Cmd (для Mac), работаем ТОЛЬКО с выделением.
            // HTMX-запрос на открытие деталей НЕ отправляется.
            if (event.ctrlKey || event.metaKey) {
                this.selectedCards.has(cardId) 
                    ? this.selectedCards.delete(cardId) 
                    : this.selectedCards.add(cardId);
            } 
            // 2. Если это обычный клик, и он НЕ был по ссылке внутри карточки...
            else if (!event.target.closest('a')) {
                // ...мы вручную даем команду HTMX сработать, вызывая кастомное событие 'openDetails'.
                // HTMX-атрибуты на карточке (hx-trigger="openDetails") "поймают" это событие.
                htmx.trigger(cardElement, 'openDetails');
            }
            // 3. Если кликнули по ссылке (<a>), ничего не делаем, позволяя ссылке сработать штатно.
        },
        
        // Геттер для удобного получения ID выделенных карточек в виде массива.
        get selectedIds() { 
            return Array.from(this.selectedCards); 
        },

        clearSelection() { 
            this.selectedCards.clear(); 
        },

        /**
         * Массовое назначение ответственного.
         * @param {string} userId - ID пользователя для назначения.
         */
        bulkAssign(userId) {
            if (!userId || this.selectedCards.size === 0) return;
            htmx.ajax('POST', '/api/bulk-assign', {
                values: { card_ids: this.selectedIds, user_id: parseInt(userId) },
                swap: 'none'
            }).then(() => {
                notyf.success(`Назначено ${this.selectedCards.size} заявок.`);
                this.clearSelection();
                // Запускаем событие, чтобы HTMX обновил канбан-доску с новыми данными.
                htmx.trigger(document.body, 'updateKanban');
            });
        },
        
        /**
         * Массовое изменение статуса.
         * @param {string} status - Новый статус для заявок.
         */
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
 * Используем DOMContentLoaded, чтобы скрипт выполнился после полной загрузки HTML.
 */
document.addEventListener('DOMContentLoaded', function () {
    // Инициализируем Alpine.js компоненты один раз при загрузке страницы.
    if (typeof Alpine !== 'undefined') {
        initializeAlpineComponents();
    } else {
        console.error("Alpine.js is not loaded.");
    }
    
    // Выполняем первую инициализацию канбан-доски.
    initializeKanban();
});

/**
 * Слушатель событий HTMX.
 * После того как HTMX заменяет какой-либо HTML-блок (afterSwap),
 * мы проверяем, не была ли это наша канбан-доска. Если да, то
 * повторно инициализируем Sortable.js на новых элементах.
 */
document.body.addEventListener('htmx:afterSwap', function(event) {
    if (event.detail.target.id === 'kanban-board-container') {
        initializeKanban();
    }
});