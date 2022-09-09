import asyncio

from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.common.by import By
import time
import re
import psycopg2
from aiogram import Bot, Dispatcher, executor, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.dispatcher import FSMContext
import config


bot = Bot(token = config.token)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)


### ПАРСИНГ КАРТОЧКИ ТОВАРА
def parse_wb(url):
    opts = Options()
    opts.headless = True
    driver = webdriver.Firefox(executable_path='C:\\Users\\vache\\PycharmProjects\\parser_selenium\\firefoxdriver\\geckodriver.exe', options=opts)
    try:
        driver.get(url = url)
        time.sleep(3)
        driver.get_screenshot_as_file('test.png')
    except Exception as ex:
        print(ex)
    else:
        # получаем наименование
        search_name = driver.find_element(By.CLASS_NAME, 'product-page__header')
        result_name = search_name.text
        try:
            # получаем цену
            search_price = driver.find_elements(By.CLASS_NAME, 'price-block__final-price')
            count_price = re.sub(r'\D', '', search_price[1].text)
        except:
            # если цену не получили, проверка наличия товара
            search_out_element = driver.find_element(By.CLASS_NAME, 'sold-out-product__text')
            count_price = 'Нет в наличии'
        result = [result_name, count_price]
    finally:
        driver.close()
        driver.quit()
    print(result)
    return result


### ЗАПИСЬ ССЫЛОК И ЦЕНЫ ТОВАРА В БАЗУ
def write_data(productlink, price, user_id):
    try:
        conn = psycopg2.connect(dbname=config.dbname, user=config.user,
                    password=config.password, host=config.host)
    except:
        print('ошибка подключения')
    else:
        cursor = conn.cursor()
        # вставляем ссылку в таблицу links, если ее нет
        # postgres_insert_query
        cursor.execute("""INSERT INTO links (link_url) 
                                       SELECT ''%s'' WHERE NOT EXISTS (SELECT 1 FROM links WHERE link_url = ''%s'')""",
                       (productlink, productlink,))
        conn.commit()
        cursor.execute("""SELECT link_id FROM links WHERE link_url = ''%s'' LIMIT 1""",
                       (productlink,))
        link_id = cursor.fetchone()[0]
        #print(link_id)

        # запись цену
        cursor.execute("""INSERT INTO prices (link_id, price, date) SELECT %s, %s, now()""",
                              (link_id, price,))
        conn.commit()
        #add user
        cursor.execute("""INSERT INTO users (user_id, link_id) SELECT %s, %s""",
                       (user_id, link_id))
        conn.commit()
        cursor.close()
        conn.close()

### ДОБАВЛЕНИЕ ССЫЛКИ
def add_link(url, user_id):
    result_parse = parse_wb(url)
    if result_parse[1] == 'Нет в наличии':
        return 0, result_parse[0]
    else:
        return 1, result_parse[0]

### БОТ
class Form(StatesGroup):
    url = State()

### start
@dp.message_handler(commands=['start', 'help'])
async def start_command(message: types.Message):
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    button1 = types.KeyboardButton(text = 'Добавить товар')
    keyboard.add(button1)
    await message.answer('Привет) Этот бот поможет тебе следить за снижением цены на понравившийся тебе товар на wildberries.')
    time.sleep(1)
    await message.answer('Нажми на кнопку Добавить товар)', reply_markup=keyboard)


### Кнопка добавить товар
@dp.message_handler(lambda message: message.text == 'Добавить товар')
async def button_url(message: types.Message):
    await Form.url.set()
    await message.answer('Пришлите ссылку на товар')

### Ожидание ввода ссылки
### Подтврждение записи
@dp.message_handler(state=Form.url)
async def parser_url(message: types.Message, state: FSMContext):
    async with state.proxy() as data:
        get_message = message.text
        if 'wildberries' not in get_message:
            answer = 2
        else:
            url = get_message[get_message.find('https'):]
            user_id = message.chat.id
            print(url, user_id)
            answer = add_link(url, user_id)
    await Form.next()
    if answer == 2:
        await message.answer('Проверьте ссылку')
    elif answer[0] == 1:
        await message.answer('Ура! Вы подписались на товар')
        await message.answer('Теперь, когда цена измениться, Вам придет уведомление')
    elif answer[0] == 0:
        await message.answer('Товара ' + answer[1] + ' нет в наличии. Выберите другой товар.')

### Сообщение пользователю
def send_message(user_id, last_price, new_price, ProductLink, name_product):
    if new_price < last_price:
        text1 = 'Цена снизилась. Пока покупать)'
        text2 = name_product + '\n' +last_price + ' -> ' + new_price + '\n' + ProductLink
    else:
        text1 = 'Цена выросла.'
        text2 = name_product + '\n' +last_price + ' -> ' + new_price + '\n' + ProductLink
    asyncio.create_task(bot.send_message(chat_id=user_id, text=text1))
    time.sleep(1)
    asyncio.create_task(bot.send_message(chat_id=user_id, text=text2))


### ОБНОВЛЕНИЕ ЦЕН В БАЗЕ
async def update_price(wait_for):
    while True:
        await asyncio.sleep(wait_for)

        conn = psycopg2.connect(dbname=config.dbname, user=config.user,
                        password=config.password, host=config.host)
        cursor_links = conn.cursor()
        cursor_links.execute("""SELECT link_id, link_url FROM links""")
        rows_url = cursor_links.fetchall()
        cursor_links.close()
        if len(rows_url) > 0:
            for row in rows_url:
                print(row)
                link_id = row[0]
                ProductLink = row[1].replace('\'', '')
                update_Float = parse_wb(ProductLink)
                new_price = update_Float[1]
                name_product = update_Float[0]

                # если товара нет в наличии
                if new_price == 'Нет в наличии':
                    print('Нет в наличии')
                    #time.sleep(1)
                    continue

                # если есть в наличии
                else:
                    conn = psycopg2.connect(dbname=config.dbname, user=config.user,
                                            password=config.password, host=config.host)
                    cursor_prices = conn.cursor()
                    cursor_prices.execute("""SELECT price FROM prices WHERE link_id = %s ORDER BY date DESC LIMIT 1""",
                                          (link_id,))
                    if cursor_prices.rowcount > 0:
                        last_price = float(cursor_prices.fetchone()[0])
                    else:
                        last_price = 0
                    new_price = float(new_price)
                    # если цена изменилась, записываем новую цену и отправляем уведомление в чат
                    if last_price != new_price:
                        print('Старая цена ', last_price, 'Новая цена ', new_price)
                        cursor_prices.execute("""INSERT INTO prices(link_id, price, date) SELECT %s, %s, now()""",
                                              (link_id, new_price))
                        conn.commit()
                        cursor_prices.execute("""SELECT user_id FROM users WHERE link_id = %s""",
                                              (link_id,))
                        if cursor_prices.rowcount > 0:
                            rows_users_id = cursor_prices.fetchall()
                            conn.close()
                            print(rows_users_id)
                            for user_id in rows_users_id:
                                send_message(int(user_id[0]), str(last_price), str(new_price), ProductLink, name_product)
                    cursor_prices.close()
                time.sleep(1)
        time.sleep(1)


if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.create_task((update_price(240.0)))
    executor.start_polling(dp, skip_updates=True)

