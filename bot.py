import asyncio
import logging
from datetime import datetime, time, timedelta
from typing import Dict
import pytzhttps://github.com/qwertyqwerty1234568/bot/blob/main/bot.py#L17C13-L17C59

from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils.keyboard import ReplyKeyboardBuilder

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Токен вашего бота (замените на свой)
API_TOKEN = '!'

# Инициализация бота и диспетчера
bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# Хранение данных пользователей
user_data: Dict[int, Dict] = {}
# Часовой пояс Москвы
timezone = pytz.timezone('Europe/Moscow')


# Клавиатура с кнопкой подтверждения для утра
def get_morning_confirmation_keyboard():
    builder = ReplyKeyboardBuilder()
    builder.add(KeyboardButton(text="да выпила я, отъебись"))
    return builder.as_markup(resize_keyboard=True)


# Клавиатура с кнопкой подтверждения для вечера
def get_evening_confirmation_keyboard():
    builder = ReplyKeyboardBuilder()
    builder.add(KeyboardButton(text="да выпила я, отъебись"))
    return builder.as_markup(resize_keyboard=True)


@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    """Обработчик команды /start"""
    user_id = message.from_user.id

    if user_id not in user_data:
        user_data[user_id] = {
            'morning_pending': False,  # Ожидает подтверждения утренний приём
            'evening_pending': False,  # Ожидает подтверждения вечерний приём
            'morning_task': None,  # Задача для повторных утренних напоминаний
            'evening_task': None,  # Задача для повторных вечерних напоминаний
            'morning_confirmed': False,  # Подтверждён ли утренний приём сегодня
            'evening_confirmed': False,  # Подтверждён ли вечерний приём сегодня
            'last_reset_date': None  # Дата последнего сброса
        }

    await message.answer(
        "привет, котёнок. сделал это для тебя чтобы ты не забывала пить колёсики",
        reply_markup=types.ReplyKeyboardRemove()
    )


@dp.message(lambda message: message.text == "да выпила я, отъебись")
async def handle_confirmation(message: types.Message):
    """Обработка подтверждения приёма таблеток (утро и вечер)"""
    user_id = message.from_user.id

    if user_id not in user_data:
        return

    now = datetime.now(timezone)
    current_time = now.time()

    # Определяем, какое подтверждение - утреннее или вечернее
    # Если время с 0:00 до 12:00 - считаем утренним, иначе - вечерним
    if current_time.hour < 12:
        # Утреннее подтверждение
        user_data[user_id]['morning_confirmed'] = True
        user_data[user_id]['morning_pending'] = False

        # Отменяем задачу повторных утренних напоминаний
        if user_data[user_id]['morning_task']:
            user_data[user_id]['morning_task'].cancel()
            user_data[user_id]['morning_task'] = None

        await message.answer(
            "✅ Ты ж моя умница, до вечера\n"
            "Следующее напоминание будет вечером в 17:45.",
            reply_markup=types.ReplyKeyboardRemove()
        )
    else:
        # Вечернее подтверждение
        user_data[user_id]['evening_confirmed'] = True
        user_data[user_id]['evening_pending'] = False

        # Отменяем задачу повторных вечерних напоминаний
        if user_data[user_id]['evening_task']:
            user_data[user_id]['evening_task'].cancel()
            user_data[user_id]['evening_task'] = None

        await message.answer(
            "✅ Моя ж ты умница \n"
            "Следующее напоминание будет завтра утром в 6:00.",
            reply_markup=types.ReplyKeyboardRemove()
        )


async def reset_daily_status():
    """Сброс статуса подтверждений в полночь"""
    while True:
        now = datetime.now(timezone)
        current_time = now.time()
        current_date = now.date()

        # Проверяем, наступила ли полночь (00:00)
        if current_time.hour == 0 and current_time.minute == 0:
            for user_id in list(user_data.keys()):
                if user_id in user_data:
                    # Проверяем, что мы ещё не сбрасывали сегодня
                    if user_data[user_id].get('last_reset_date') != current_date:
                        user_data[user_id]['morning_confirmed'] = False
                        user_data[user_id]['evening_confirmed'] = False
                        user_data[user_id]['morning_pending'] = False
                        user_data[user_id]['evening_pending'] = False
                        user_data[user_id]['last_reset_date'] = current_date

                        # Отменяем все активные задачи
                        if user_data[user_id]['morning_task']:
                            user_data[user_id]['morning_task'].cancel()
                            user_data[user_id]['morning_task'] = None
                        if user_data[user_id]['evening_task']:
                            user_data[user_id]['evening_task'].cancel()
                            user_data[user_id]['evening_task'] = None

                        try:
                            await bot.send_message(
                                user_id,
                                "🔄 Статус сброшен. Завтра снова буду напоминать!"
                            )
                        except:
                            pass

        # Ждём 1 минуту перед следующей проверкой
        await asyncio.sleep(60)


async def send_morning_reminder(user_id: int):
    """Отправка утреннего напоминания в 6:00"""
    if user_id in user_data and not user_data[user_id]['morning_confirmed']:
        user_data[user_id]['morning_pending'] = True

        try:
            await bot.send_message(
                user_id,
                "Котёнок, выпей колёсики",
                reply_markup=get_morning_confirmation_keyboard()
            )
        except Exception as e:
            logger.error(f"Ошибка при отправке утреннего напоминания: {e}")
            user_data[user_id]['morning_pending'] = False
            return

        # Запускаем повторные напоминания каждые 15 минут
        if user_data[user_id]['morning_task']:
            user_data[user_id]['morning_task'].cancel()

        user_data[user_id]['morning_task'] = asyncio.create_task(
            send_repeated_morning_reminders(user_id)
        )


async def send_evening_reminder(user_id: int):
    """Отправка вечернего напоминания в 17:45"""
    if user_id in user_data and not user_data[user_id]['evening_confirmed']:
        user_data[user_id]['evening_pending'] = True

        try:
            await bot.send_message(
                user_id,
                "Котёнок, выпей колёсики",
                reply_markup=get_evening_confirmation_keyboard()
            )
        except Exception as e:
            logger.error(f"Ошибка при отправке вечернего напоминания: {e}")
            user_data[user_id]['evening_pending'] = False
            return

        # Запускаем повторные напоминания каждые 15 минут
        if user_data[user_id]['evening_task']:
            user_data[user_id]['evening_task'].cancel()

        user_data[user_id]['evening_task'] = asyncio.create_task(
            send_repeated_evening_reminders(user_id)
        )


async def send_repeated_morning_reminders(user_id: int):
    """Отправка повторных утренних напоминаний каждые 15 минут"""
    reminder_count = 0
    max_reminders = 32  # Максимум 8 часов (с 6:00 до 14:00)

    while (reminder_count < max_reminders and
           user_id in user_data and
           user_data[user_id]['morning_pending'] and
           not user_data[user_id]['morning_confirmed']):

        await asyncio.sleep(900)  # Ждём 15 минут (900 секунд)

        # Проверяем, нужно ли ещё отправлять напоминания
        if (user_id not in user_data or
                not user_data[user_id]['morning_pending'] or
                user_data[user_id]['morning_confirmed']):
            break

        try:
            await bot.send_message(
                user_id,
                "Котёнок, выпей колёсики",
                reply_markup=get_morning_confirmation_keyboard()
            )
            reminder_count += 1
        except Exception as e:
            logger.error(f"Ошибка при отправке повторного утреннего напоминания: {e}")
            break


async def send_repeated_evening_reminders(user_id: int):
    """Отправка повторных вечерних напоминаний каждые 15 минут"""
    reminder_count = 0
    max_reminders = 32  # Максимум 8 часов (с 17:45 до 1:45)

    while (reminder_count < max_reminders and
           user_id in user_data and
           user_data[user_id]['evening_pending'] and
           not user_data[user_id]['evening_confirmed']):

        await asyncio.sleep(900)  # Ждём 15 минут (900 секунд)

        # Проверяем, нужно ли ещё отправлять напоминания
        if (user_id not in user_data or
                not user_data[user_id]['evening_pending'] or
                user_data[user_id]['evening_confirmed']):
            break

        try:
            await bot.send_message(
                user_id,
                "Котёнок, выпей колёсики",
                reply_markup=get_evening_confirmation_keyboard()
            )
            reminder_count += 1
        except Exception as e:
            logger.error(f"Ошибка при отправке повторного вечернего напоминания: {e}")
            break


async def check_and_send_reminders():
    """Проверка времени и отправка напоминаний"""
    while True:
        now = datetime.now(timezone)
        current_time = now.time()
        current_date = now.date()

        # Для каждого пользователя
        for user_id in list(user_data.keys()):
            try:
                # Проверяем, нужно ли сбросить статус за день
                if user_data[user_id].get('last_reset_date') != current_date:
                    user_data[user_id]['morning_confirmed'] = False
                    user_data[user_id]['evening_confirmed'] = False
                    user_data[user_id]['morning_pending'] = False
                    user_data[user_id]['evening_pending'] = False
                    user_data[user_id]['last_reset_date'] = current_date

                # Утреннее напоминание в 6:00
                if (current_time.hour == 6 and current_time.minute == 0 and
                        not user_data[user_id]['morning_confirmed'] and
                        not user_data[user_id]['morning_pending']):
                    await send_morning_reminder(user_id)

                # Вечернее напоминание в 17:45
                elif (current_time.hour == 17 and current_time.minute == 45 and
                      not user_data[user_id]['evening_confirmed'] and
                      not user_data[user_id]['evening_pending']):
                    await send_evening_reminder(user_id)

            except Exception as e:
                logger.error(f"Ошибка при проверке напоминаний для пользователя {user_id}: {e}")

        # Ждём 1 минуту перед следующей проверкой
        await asyncio.sleep(60)


async def on_startup():
    """Действия при запуске бота"""
    logger.info("Бот запущен!")
    # Запускаем фоновые задачи
    asyncio.create_task(check_and_send_reminders())
    asyncio.create_task(reset_daily_status())


async def main():
    """Основная функция"""
    dp.startup.register(on_startup)

    # Запуск бота
    await dp.start_polling(bot)


if __name__ == '__main__':

    asyncio.run(main())
