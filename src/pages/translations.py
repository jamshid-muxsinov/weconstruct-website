# src/pages/translations.py

# Словарь для всех строк интерфейса.
# Ключ - это идентификатор строки, а значение - словарь с переводами.
TRANSLATIONS = {
    # Общие слова
    'save': {'ru': 'Сохранить', 'uz': 'Saqlash'},
    'cancel': {'ru': 'Отмена', 'uz': 'Bekor qilish'},
    'delete': {'ru': 'Удалить', 'uz': 'Oʻchirish'},
    'edit': {'ru': 'Редактировать', 'uz': 'Tahrirlash'},
    'add': {'ru': 'Добавить', 'uz': 'Qoʻshish'},
    'search': {'ru': 'Поиск', 'uz': 'Qidiruv'},
    'apply': {'ru': 'Применить', 'uz': 'Qoʻllash'},
    'clear': {'ru': 'Очистить', 'uz': 'Tozalash'},
    'export': {'ru': 'Экспорт', 'uz': 'Eksport'},
    'status': {'ru': 'Статус', 'uz': 'Holati'},
    'actions': {'ru': 'Действия', 'uz': 'Harakatlar'},
    'selected': {'ru': 'Выбрано', 'uz': 'Tanlandi'},
    'selected_cards_count': {'ru': 'Выбрано: {count}', 'uz': 'Tanlandi: {count}'},
    'back_to_list': {'ru': 'К списку', 'uz': 'Roʻyxatga qaytish'},
    'lang_ru': {'ru': 'Русский', 'uz': 'Rus tili'},
    'lang_uz': {'ru': 'O\'zbekcha', 'uz': 'Oʻzbek tili'},

    # Шаблон base.html (меню и шапка)
    'admin_panel': {'ru': 'Панель управления', 'uz': 'Boshqaruv paneli'},
    'sidebar_kanban': {'ru': 'Канбан-доска', 'uz': 'Kanban-doska'},
    'sidebar_requests': {'ru': 'Заявки', 'uz': 'Arizalar'},
    'sidebar_contacts': {'ru': 'Контакты', 'uz': 'Kontaktlar'},
    'sidebar_statistics': {'ru': 'Статистика', 'uz': 'Statistika'},
    'sidebar_products': {'ru': 'Товары', 'uz': 'Mahsulotlar'},
    'sidebar_categories': {'ru': 'Категории', 'uz': 'Kategoriyalar'},
    'sidebar_import': {'ru': 'Импорт', 'uz': 'Import'},
    'sidebar_invites': {'ru': 'Приглашения', 'uz': 'Taklifnomalar'},
    'logout': {'ru': 'Выйти', 'uz': 'Chiqish'},
    'hello_user': {'ru': 'Привет, {username}!', 'uz': 'Salom, {username}!'},
    'profile': {'ru': 'Профиль', 'uz': 'Profil'},
    'notifications': {'ru': 'Уведомления', 'uz': 'Bildirishnomalar'},
    
    # Страница Канбан
    'sales_funnel': {'ru': 'Воронка продаж', 'uz': 'Sotuv voronkasi'},
    'show_archived': {'ru': 'Показать архивные', 'uz': 'Arxivdagilarni koʻrsatish'},
    'new_request': {'ru': 'Новая заявка', 'uz': 'Yangi ariza'},
    'search_placeholder': {'ru': 'Поиск по имени, телефону или ID...', 'uz': 'Ism, telefon yoki ID boʻyicha qidirish...'},
    'my_tasks': {'ru': 'Мои задачи', 'uz': 'Mening vazifalarim'},
    'assign_to': {'ru': 'Назначить...', 'uz': 'Tayinlash...'},
    'status_placeholder': {'ru': 'Статус...', 'uz': 'Holat...'},
    'cancel_selection': {'ru': 'Отменить выбор', 'uz': 'Tanlovni bekor qilish'},
    'loading_kanban': {'ru': 'Загрузка канбан-доски...', 'uz': 'Kanban-doska yuklanmoqda...'},
    'export_selected': {'ru': 'Экспорт выбранных', 'uz': 'Tanlanganlarni eksport qilish'},

    # CRUD (Списки и формы)
    'list_requests': {'ru': 'Заявки', 'uz': 'Arizalar'},
    'request_single': {'ru': 'Заявка', 'uz': 'Ariza'},
    'list_products': {'ru': 'Товары', 'uz': 'Mahsulotlar'},
    'product_single': {'ru': 'Товар', 'uz': 'Mahsulot'},
    'list_categories': {'ru': 'Категории', 'uz': 'Kategoriyalar'},
    'category_single': {'ru': 'Категория', 'uz': 'Kategoriya'},
    'list_contacts': {'ru': 'Контакты', 'uz': 'Kontaktlar'},
    'client_single': {'ru': 'Клиент', 'uz': 'Mijoz'},
    'add_button': {'ru': 'Добавить {entity}', 'uz': '{entity} qoʻshish'},
    'editing': {'ru': 'Редактирование', 'uz': 'Tahrirlash'},
    'adding': {'ru': 'Добавление', 'uz': 'Qoʻshish'},
    'page_title_stats': {'ru': 'Статистика и Обзор', 'uz': 'Statistika va Sharh'},
    'back_to_request_list': {'ru': 'К списку заявок', 'uz': 'Arizalar roʻyxatiga'},
    'general_settings': {'ru': 'Общие настройки', 'uz': 'Umumiy sozlamalar'},

    # Заголовки таблиц и списков
    'header_client': {'ru': 'Клиент', 'uz': 'Mijoz'},
    'header_phone': {'ru': 'Телефон', 'uz': 'Telefon'},
    'header_business_type': {'ru': 'Тип бизнеса', 'uz': 'Biznes turi'},
    'header_created_at': {'ru': 'Дата создания', 'uz': 'Yaratilgan sana'},
    'header_status': {'ru': 'Статус', 'uz': 'Holati'},
    'header_assignee': {'ru': 'Ответственный', 'uz': 'Masʼul'},
    'header_name': {'ru': 'Название', 'uz': 'Nomi'},
    'header_category': {'ru': 'Категория', 'uz': 'Kategoriya'},
    'header_price_from': {'ru': 'Цена от', 'uz': 'Narx (dan)'},
    'header_is_active': {'ru': 'Активен', 'uz': 'Aktiv'},
    'no_records_found': {'ru': 'Записей не найдено.', 'uz': 'Yozuvlar topilmadi.'},
    
    # Формы
    'client_info': {'ru': 'Информация от клиента', 'uz': 'Mijozdan maʼlumot'},
    'manager_info': {'ru': 'Информация от менеджера', 'uz': 'Menejerdan maʼlumot'},
    'search_client_placeholder': {'ru': 'Поиск клиента (по имени или телефону)', 'uz': 'Mijozni qidirish (ism yoki telefon boʻyicha)'},
    'new_client': {'ru': 'Новый клиент', 'uz': 'Yangi mijoz'},
    'delete_request': {'ru': 'Удалить заявку', 'uz': 'Arizani oʻchirish'},
    'contact_info': {'ru': 'Контактная информация', 'uz': 'Kontakt maʼlumotlari'},
    'delete_contact': {'ru': 'Удалить контакт', 'uz': 'Kontaktni oʻchirish'},
    'interaction_feed': {'ru': 'Лента взаимодействий', 'uz': 'Oʻzaro aloqalar lentasi'},
    'add_note_placeholder': {'ru': 'Добавить заметку о звонке или встрече...', 'uz': 'Qoʻngʻiroq yoki uchrashuv haqida eslatma qoʻshish...'},
    'add_note_button': {'ru': 'Добавить заметку', 'uz': 'Eslatma qoʻshish'},
    'delete_confirmation_title': {'ru': 'Удалить {entity}', 'uz': '{entity} oʻchirilsinmi'},
    'delete_confirmation_text': {'ru': 'Вы уверены, что хотите удалить "{item}"? Это действие необратимо.', 'uz': '"{item}"ni oʻchirishni xohlaysizmi? Bu amalni bekor qilib boʻlmaydi.'},
    'confirm_delete': {'ru': 'Да, я уверен', 'uz': 'Ha, aminman'},

    # Сообщения
    'contact_updated_success': {'ru': 'Данные клиента успешно обновлены!', 'uz': 'Mijoz maʼlumotlari muvaffaqiyatli yangilandi!'},
}