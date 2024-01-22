import telebot
from telebot import types
import sqlite3
import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
import requests
import base64

# Ваши настройки телеграм-бота
TOKEN = ''
ADMIN_USER_IDS = ['428167246']

# Ваши настройки для отправки почты
EMAIL_HOST = 'mail.yarbroiler.ru'
EMAIL_PORT = 25
EMAIL_USERNAME = ''
EMAIL_PASSWORD = ''
RECIPIENT_EMAIL = 'kmv@yarbroiler.ru'

logging.basicConfig(filename='bot.log', filemode='a', format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.DEBUG)

bot = telebot.TeleBot(TOKEN)

class DatabaseManager:
    def __init__(self, database_path):
        self.database_path = database_path

    def __enter__(self):
        self.connection = sqlite3.connect(self.database_path)
        return self.connection.cursor()

    def __exit__(self, exc_type, exc_value, traceback):
        try:
            if hasattr(self, 'connection') and not self.connection.closed:
                self.connection.commit()
        except Exception as commit_error:
            logging.error(f"Ошибка при коммите транзакции: {commit_error}")

        try:
            if hasattr(self, 'connection'):
                self.connection.close()
        except Exception as close_error:
            logging.error(f"Ошибка при закрытии соединения: {close_error}")

# Создаем базу данных для отзывов
with sqlite3.connect('reviews.db') as connection:
    cursor = connection.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            user_name TEXT,
            review_text TEXT
        )
    ''')

# Создаем базу данных для фотографий
with sqlite3.connect('photos.db') as connection:
    cursor = connection.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS photos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            user_name TEXT,
            photo_id TEXT
        )
    ''')

@bot.message_handler(commands=['start'])
def handle_start(message):
    try:
        markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
        item_review = telebot.types.KeyboardButton("Отзыв")
        item_help = telebot.types.KeyboardButton("Помощь")
        item_send_photo = telebot.types.KeyboardButton("Отправить фото")
        item_settings = telebot.types.KeyboardButton("Настройки")
        item_stat = telebot.types.KeyboardButton("Статистика")
        markup.add(item_review, item_help, item_send_photo, item_settings, item_stat)

        bot.reply_to(message, "Привет! Я бот для сбора отзывов. Выберите действие:", reply_markup=markup)
    except Exception as e:
        logging.error(f"Ошибка при обработке команды start: {e}")

@bot.message_handler(func=lambda message: True, content_types=['text', 'photo'])
def handle_messages(message):
    try:
        if message.text == "Отзыв":
            bot.reply_to(message, "Пожалуйста, отправьте свой отзыв.")
        elif message.text == "Помощь":
            bot.reply_to(message, "Здесь вы можете оставить отзыв или узнать о боте.")
        elif message.text == "Отправить фото":
            bot.reply_to(message, "Пожалуйста, отправьте вашу фотографию.")
        elif message.text == "Настройки":
            show_settings(message)
        elif message.text == "Статистика":
            show_statistics(message)
        elif message.text == "Назад":
            handle_start(message)  # Вернуться в начальное меню
        elif message.text == "/reply":
            reply_buttons = types.InlineKeyboardMarkup()
            reply_buttons.add(types.InlineKeyboardButton(text="Ответить", switch_inline_query_current_chat=""))
            bot.send_message(message.from_user.id, "Выберите команду:", reply_markup=reply_buttons)
        else:
            save_to_database_and_notify_admin(message)
            bot.reply_to(message, "Спасибо за ваше сообщение!")
    except Exception as e:
        logging.error(f"Ошибка при обработке сообщения: {e}")

@bot.message_handler(func=lambda message: message.text == "Настройки")
def show_settings(message):
    try:
        markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
        item_location = telebot.types.KeyboardButton("Отправить местоположение", request_location=True)
        item_back = telebot.types.KeyboardButton("Назад")
        markup.add(item_location, item_back)

        bot.reply_to(message, "Настройки:", reply_markup=markup)
    except Exception as e:
        logging.error(f"Ошибка при отображении настроек: {e}")

@bot.message_handler(func=lambda message: message.text == "Отправить местоположение")
def send_location(message):
    try:
        markup = telebot.types.ReplyKeyboardRemove(selective=False)
        bot.reply_to(message, "Пожалуйста, отправьте своё местоположение.", reply_markup=markup)
    except Exception as e:
        logging.error(f"Ошибка при запросе местоположения: {e}")

@bot.message_handler(content_types=['location'])
def handle_location(message):
    try:
        user_id = message.from_user.id
        user_name = message.from_user.username
        location = message.location
        bot.reply_to(message, f"Спасибо, {user_name}! Ваше местоположение принято.")
    except Exception as e:
        logging.error(f"Ошибка при обработке местоположения: {e}")

@bot.message_handler(content_types=['photo'])
def handle_photo(message):
    try:
        user_id = message.from_user.id
        user_name = message.from_user.username
        photo_id = message.photo[-1].file_id

        with DatabaseManager('photos.db') as db:
            db.execute('INSERT INTO photos (user_id, user_name, photo_id) VALUES (?, ?, ?)',
                       (user_id, user_name, photo_id))

        bot.reply_to(message, f"Спасибо, {user_name}! Ваша фотография принята.")
    except Exception as e:
        logging.error(f"Ошибка при обработке фотографии: {e}")

@bot.message_handler(func=lambda message: message.text == "Статистика")
def show_statistics(message):
    try:
        with DatabaseManager('reviews.db') as db:
            db.execute('SELECT COUNT(*) FROM reviews')
            reviews_count = db.fetchone()[0]
        bot.reply_to(message, f"Общее количество отзывов: {reviews_count}")
    except Exception as e:
        logging.error(f"Ошибка при отображении статистики: {e}")

def save_to_database_and_notify_admin(message):
    try:
        user_id = message.from_user.id
        user_name = message.from_user.username
        review_text = message.text

        with DatabaseManager('reviews.db') as db:
            db.execute('INSERT INTO reviews (user_id, user_name, review_text) VALUES (?, ?, ?)',
                       (user_id, user_name, review_text))

        send_to_admin_and_email_notification(message)

    except Exception as e:
        logging.error(f"Ошибка при сохранении в базу данных: {e}")

def send_to_admin_and_email_notification(message):
    try:
        user_id = message.from_user.id
        user_name = message.from_user.username

        # Отправляем уведомление в телеграм
        for admin_id in ADMIN_USER_IDS:
            try:
                bot.send_message(admin_id, f"Новый отзыв от {user_name} (ID: {user_id}): {message.text}")
                if message.photo:
                    # Если есть фото, отправляем и его
                    bot.send_photo(admin_id, message.photo[-1].file_id)
            except Exception as telegram_error:
                logging.error(f"Ошибка при отправке уведомления в Телеграм: {telegram_error}")
                logging.error(f"Admin ID: {admin_id}")
                logging.error(f"User ID: {user_id}")
                logging.error(f"User Name: {user_name}")

        # Отправляем уведомление на электронную почту
        email_subject = f"Новый отзыв от {user_name} (ID: {user_id})"
        email_body = f"Текст отзыва: {message.text}"

        # Проверяем, есть ли фото в сообщении
        if message.photo:
            photo_file_id = message.photo[-1].file_id
            send_email(email_subject, email_body, photo_file_id)
        else:
            send_email(email_subject, email_body)

    except Exception as e:
        logging.error(f"Ошибка при отправке уведомления: {e}")

def send_email(subject, body, photo_file_id=None):
    try:
        # Устанавливаем соединение с почтовым сервером
        server = smtplib.SMTP(EMAIL_HOST, EMAIL_PORT)
        server.starttls()
        server.login(EMAIL_USERNAME, EMAIL_PASSWORD)

        # Создаем сообщение
        message = MIMEMultipart()
        message['From'] = EMAIL_USERNAME
        message['To'] = RECIPIENT_EMAIL
        message['Subject'] = subject
        message.attach(MIMEText(body, 'plain'))

        if photo_file_id:
            # Если есть фото, добавляем его в сообщение
            photo_url = f"https://api.telegram.org/bot{TOKEN}/getFile?file_id={photo_file_id}"
            photo_path = download_file(photo_url)
            with open(photo_path, 'rb') as photo_file:
                image = MIMEImage(photo_file.read())
                message.attach(image)

        # Отправляем письмо
        server.sendmail(EMAIL_USERNAME, RECIPIENT_EMAIL, message.as_string())

        # Закрываем соединение
        server.quit()

    except Exception as e:
        logging.error(f"Ошибка при отправке электронной почты: {e}")
        logging.error(f"Subject: {subject}")
        logging.error(f"Body: {body}")

# Функция для загрузки файла по URL
def download_file(url):
    response = requests.get(url)
    filename = url.split("/")[-1]
    with open(filename, 'wb') as file:
        file.write(response.content)
    return filename

if __name__ == "__main__":
    bot.polling(none_stop=True)
