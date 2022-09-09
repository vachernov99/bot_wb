# bot_wb
Telegram бот для оповещения покупателя об изменении цены
# Установка
* Распаковываем и устанавливаем Geckodriver в папку проекта
* Создаем в базе три таблицы: links, prices, users

```sql
CREATE TABLE links(
		link_id SERIAL PRIMARY KEY,
		link_url CHARACTER VARYING(300) NOT NULL);
    
CREATE TABLE prices(
		link_id INT,
		price NUMERIC(20,2),
		date TIMESTAMP);	
		
CREATE TABLE users(
		user_id CHARACTER VARYING(15) NOT NULL,
		link_id INT);
```
* Параметры подключения в базе и токен бота записываем в файл config
---
Стек: Python, Selenium Webdriver, Aiogram, Asyncio, Psycopg2
