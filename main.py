#импорты
import threading
from selenium import webdriver
from selenium_stealth import stealth
from selenium.webdriver.chrome.service import Service
import time
from bs4 import BeautifulSoup

import telebot

#переменные
options = webdriver.ChromeOptions()
options.add_argument("-headless")
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")


API = '8360749794:AAEviD5YYzT4piehoxUG4eSCcrBsREfAUy4'
bot = telebot.TeleBot(API)

user_data = {}

#парсинг с озона
def init_webdriver_ozon(url):
    service = Service()

    driver = webdriver.Chrome(service=service, options=options)

    stealth(driver,
            languages=["ru-RU", "ru", "en-US", "en"],
            vendor="Google Inc.",
            platform="Win32",
            webgl_vendor="Intel Inc.",
            renderer="Intel Iris OpenGL Engine",
            fix_hairline=True)
    try:
        driver.maximize_window()
        driver.get(url)
        time.sleep(5)
    
        soup = BeautifulSoup(driver.page_source, "html.parser")
        price_tag = soup.find("span", {"class": "tsHeadline600Large"})
    
        raw_tag = price_tag.text

        clean_price = "".join(filter(str.isdigit, raw_tag))
    
        return int(clean_price)
    finally:
        driver.quit()

#парсинг с вб
def init_webdriver_wb(url):
    service = Service()

    driver = webdriver.Chrome(service=service, options=options)

    stealth(driver,
            languages=["ru-RU", "ru", "en-US", "en"],
            vendor="Google Inc.",
            platform="Win32",
            webgl_vendor="Intel Inc.",
            renderer="Intel Iris OpenGL Engine",
            fix_hairline=True)
    try:
        driver.maximize_window()
        driver.get(url)
        time.sleep(5)
    
        soup = BeautifulSoup(driver.page_source, "html.parser")
        price_tag = soup.find("ins") or soup.find(class_=lambda x: x and 'price' in x.lower())

        if not price_tag:
            raise Exception("Не удалось найти элемент цены на странице")
        
        raw_tag = price_tag.text

        clean_price = "".join(filter(str.isdigit, raw_tag))
    
        return int(clean_price)
    finally:
        driver.quit()

#старт
@bot.message_handler(commands=['start'])
def send_start(message):
    user_data[message.chat.id] = {}
    text = "🤖Привет!\nЯ — бот для отслеживания цен на Ozon и Wildberries."
    bot.reply_to(message, text)
    bot.send_message(message.chat.id, "🙏Отправьте мне cсылку на товар")
    bot.register_next_step_handler(message, get_url)

#получаем ссылку
def get_url(message):
    url_str = message.text
    if "start" in url_str:
        bot.register_next_step_handler(message, send_start)
    elif "continue" in url_str:
        bot.register_next_step_handler(message, continue_command)
    elif 'https' in url_str:
        user_data[message.chat.id]['url'] = url_str
        bot.send_message(message.chat.id, "✅Отлично!")
        bot.send_message(message.chat.id, "🕐Введите интервал проверок в секундах (больше 5)")
        bot.register_next_step_handler(message, get_interval)
    else:
        bot.send_message(message.chat.id, "❌Неверный Формат.\nОтправьте мне корректную ссылку")
        bot.register_next_step_handler(message, get_url)

#получаем интервал
def get_interval(message):
    try:
        interval = int(message.text)
        if interval < 5:
            raise ValueError
        user_data[message.chat.id]["interval"] = interval
        bot.send_message(message.chat.id, "🔢Введите количество проверок товара (минимум 2)")
        bot.register_next_step_handler(message, get_total_checks)
    except ValueError:
        bot.send_message(message.chat.id, "🕐Введите целое число проверок в секундах (больше 5)")
        bot.register_next_step_handler(message, get_interval)

#получаем кол-во проверок
def get_total_checks(message):
    try:
        total_checks = int(message.text)
        if total_checks < 2:
            bot.send_message(message.chat.id, "❗Установленно минимальное кол-во проверок: 2")
            total_checks = 2
        
        user_data[message.chat.id]["total_checks"] = total_checks

        threading.Thread(target=async_parsing_task, args=(message.chat.id,)).start()

    except ValueError:
        bot.send_message(message.chat.id, "🔢Введите количество проверок товара (минимум 2)")
        bot.register_next_step_handler(message.chat.id, get_total_checks)
            

@bot.message_handler(commands=['continue'])
def continue_command(message):
    bot.send_message(message.chat.id, "✅Отлично, запускаю процесс проверки заново")
    bot.send_message(message.chat.id, "🙏Отправьте мне cсылку на товар")
    bot.register_next_step_handler(message, get_url)


#определяем маркетплейс, проводим цикл проверок и парсинга
def async_parsing_task(chat_id):
    data = user_data.get(chat_id)
    if not data:
        return
    
    url_str = data['url']
    interval = data['interval']
    total_checks = data['total_checks']


    if "wildberries" in url_str or "wb.ru" in url_str:
        parse_function = init_webdriver_wb
    elif "ozon" in url_str:
        parse_function = init_webdriver_ozon
    else:
        bot.send_message(chat_id, "❌Не удалось определить маркетплейс по ссылке")
        return

    first_price = None

    for i in range(total_checks):
        bot.send_message(chat_id, f"❗Проверка {i + 1} из {total_checks}... \n")
        try:
            current_price = parse_function(url_str)
        except Exception as e:
            bot.send_message(chat_id, f"❌Ошибка на проверке {i + 1} : {e} \n")
            if i < total_checks - 1:
                time.sleep(interval)
            continue

        if i == 0:
            first_price = current_price
            bot.send_message(chat_id, f"1️⃣Начальная цена: {first_price} руб.\n")

        else:
            price_check = current_price - first_price

            if price_check < 0:
                bot.send_message(chat_id, f"⬇️✅Подешевело на {abs(price_check)} руб.\nТекущая цена: {current_price} руб.")
            elif price_check > 0:
                bot.send_message(chat_id, f"⬆️✅Подарожало на {(price_check)} руб.\nТекущая цена: {current_price} руб.")
            else:
                bot.send_message(chat_id, f"✅🥱Цена не изменилась\n")

        if i < total_checks -1:
            time.sleep(interval)

    bot.send_message(chat_id, "✅Проверка завершена!")
    bot.send_message(chat_id, "🤖Хотите продолжить?\nВведите комманду /continue!")

if __name__ == '__main__':
    bot.infinity_polling()
