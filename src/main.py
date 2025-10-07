import asyncio
import logging
import os
import sqlite3
from aiogram import Bot, Dispatcher, F
from datetime import datetime, timezone, timedelta
from aiogram.filters import CommandStart, Command, BaseFilter
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

# Настройка логирования
logging.basicConfig(level=logging.INFO)

# Получаем токен бота
BOT_TOKEN = os.getenv('BOT_TOKEN')

# ID администраторов
ADMIN_IDS = [1946022501]

# ID забаненных участников
BAN_IDS = []

# Создаем объекты бота и диспетчера
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Московская таймзона UTC+3
MOSCOW_TZ = timezone(timedelta(hours=3))


# Кастомный фильтр для проверки админов
class IsAdmin(BaseFilter):
    async def __call__(self, message: Message) -> bool:
        return message.from_user.id in ADMIN_IDS


# Кастомный фильтр для проверки админов
class NotIsBan(BaseFilter):
    async def __call__(self, message: Message) -> bool:
        return message.from_user.id not in BAN_IDS


# Функция для получения московского времени
def get_moscow_time():
    """Возвращает текущее московское время"""
    return datetime.now(MOSCOW_TZ)


# Функция для инициализации базы данных
def init_db():
    """Создаем таблицу пользователей если её нет"""
    conn = sqlite3.connect('bot_users.db')
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            answer TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    conn.commit()
    conn.close()
    print("terminal: База данных инициализирована")


# Функция для добавления пользователя в БД
def add_user_to_db(user_id, username, first_name):
    """Добавляет нового пользователя в базу данных"""
    conn = sqlite3.connect('bot_users.db')
    cursor = conn.cursor()

    # Проверяем, есть ли уже такой пользователь
    cursor.execute('SELECT user_id FROM users WHERE user_id = ?', (user_id,))
    if cursor.fetchone() is None:
        moscow_time = get_moscow_time().strftime('%Y-%m-%d %H:%M:%S')
        cursor.execute('''
            INSERT INTO users (user_id, username, first_name, created_at) 
            VALUES (?, ?, ?, ?)
        ''', (user_id, username, first_name, moscow_time))
        conn.commit()
        print(f"terminal: Пользователь {user_id} добавлен в БД")

    conn.close()


# Функция для сохранения ответа пользователя
def save_user_answer(user_id, answer):
    """Сохраняет ответ пользователя в базу данных"""
    conn = sqlite3.connect('bot_users.db')
    cursor = conn.cursor()

    # Получаем московское время для времени ответа
    moscow_time = get_moscow_time().strftime('%Y-%m-%d %H:%M:%S')

    cursor.execute('''
            UPDATE users SET answer = ?, created_at = ? WHERE user_id = ?
        ''', (answer, moscow_time, user_id))

    conn.commit()
    conn.close()
    print(f"terminal: Ответ пользователя {user_id}: {answer}")


# Функция для создания inline клавиатуры с кнопками Да/Нет
def get_yes_no_keyboard():
    """Создает inline клавиатуру с кнопками Да и Нет"""
    kb = InlineKeyboardBuilder()
    kb.add(
        InlineKeyboardButton(text="Да", callback_data="answer_yes"),
        InlineKeyboardButton(text="Нет", callback_data="answer_no")
    )
    kb.adjust(2)  # 2 кнопки в один ряд
    return kb.as_markup()


# Хэндлер команды /start
@dp.message(CommandStart(), NotIsBan())
async def cmd_start(message: Message):

    # Добавляем пользователя в БД
    add_user_to_db(
            user_id=message.from_user.id,
            username=message.from_user.username,
            first_name=message.from_user.first_name)

    # Задаем вопрос с inline кнопками
    await message.answer(
        f"Привет! Я тут задумался и захотел задать вопрос каждому студенту ЦУ.\n"
            f"Ты бы хотел видеть квест в цу на подобии 'Цикады 3301', 'Mr. Robot' и тому подобные?",
            reply_markup=get_yes_no_keyboard())


# Хэндлер для обработки нажатий на inline кнопки
@dp.callback_query(F.data == "answer_yes")
async def process_yes_answer(callback: CallbackQuery):
    # Сохраняем ответ в БД
    save_user_answer(callback.from_user.id, "Да")

    # Отвечаем пользователю
    await callback.answer("Ты выбрал: Да")

    # Редактируем сообщение
    await callback.message.edit_text("Хорошо, твой ответ записан. Спасибо за участие в опросе!")


@dp.callback_query(F.data == "answer_no")
async def process_no_answer(callback: CallbackQuery):
    # Сохраняем ответ в БД
    save_user_answer(callback.from_user.id, "Нет")

    # Отвечаем пользователю
    await callback.answer("Ты выбрал: Нет")

    # Редактируем сообщение
    await callback.message.edit_text("Хорошо, твой ответ записан. Спасибо за участие в опросе!")


@dp.message(Command('help'), NotIsBan())
async def cmd_help(message: Message):
    await message.answer("Пока что здесь ничего нет, так как мы ждем результаты опроса.")


@dp.message(Command('stats'), IsAdmin())
async def cmd_stats(message: Message):
    """Показывает статистику ответов из БД"""
    conn = sqlite3.connect('bot_users.db')
    cursor = conn.cursor()

    # Считаем ответы
    cursor.execute('SELECT answer, COUNT(*) FROM users WHERE answer IS NOT NULL GROUP BY answer')
    results = cursor.fetchall()

    cursor.execute('SELECT COUNT(*) FROM users')
    total_users = cursor.fetchone()[0]

    conn.close()

    # Формируем статистику
    stats_text = f"Статистика ответов:\n\n"
    stats_text += f"Всего пользователей: {total_users}\n\n"

    if results:
        for answer, count in results:
            stats_text += f"{'✅' if answer == 'Да' else '❌'} {answer}: {count}\n"
    else:
        stats_text += "Пока нет ответов"

    await message.answer(stats_text)


# Хэндлер для всех остальных сообщений
@dp.message()
async def echo_message(message: Message):
    await message.answer("Неизвестная команда.")


# Главная функция
async def main():
    init_db()
    await dp.start_polling(bot, skip_updates=True)

if __name__ == '__main__':
    print("terminal: Бот запустился")
    asyncio.run(main())
