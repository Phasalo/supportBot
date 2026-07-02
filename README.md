<h1 align="center">Phasalo Support Bot</h1>
<p align="center">
Один бот — поддержка для всех проектов Phasalo. Красиво, как всегда.
</p>
<p align="center">
<img src="https://img.shields.io/badge/made%20by-CSSSensei,%20MaxMavr-439900">
<a href="https://github.com/Phasalo"><img src="https://img.shields.io/badge/Phasalo-84D300"></a>
</p>

Единый support-бот для проектов <b>Phasalo</b>. Пользователь приходит по deep-link `?start=<slug>`,
его обращение становится тикетом, а операторы ведут двусторонний диалог **прямо внутри бота**.

<h1></h1>

## Запуск

### 1. Зависимости
```bash
uv sync          # или: pip install -r requirements.txt
```

### 2. Настройте окружение
```bash
cp .env.example .env
```
> Минимум — `BOT_TOKEN` и `PASSWORD` (пароль-суперюзер для входа в админку).

### 3. Запуск
```bash
python main.py
```
> Таблицы создаются автоматически при первом старте.

## Как пользоваться

### Админ
Отправьте боту `PASSWORD` → станете администратором. Дальше:
```
/projects                        панель проектов: создать / редактировать
                                 (title, slug, ссылка), вкл/выкл, удалить,
                                 deep-link, история тикетов и переписки
/my_projects                     тоггл своих проектов (зона ответственности)
/add_operator <user_id> <slug>   назначить оператора
/remove_operator <user_id> <slug> снять оператора
/operators [slug]                кто на проекте (или везде)
```

### Оператор
- Новый тикет → пуш с кнопками **[Открыть] [Ответить]**.
- `/panel` — открытые обращения в вашей зоне.
- **Ответить** → режим ответа (любой контент уходит юзеру), **/done** — выйти, **Закрыть** — завершить тикет.

### Пользователь
- `t.me/<bot>?start=<slug>` (или `/start` → **[🆘 Обратиться]** → выбор проекта)
- Тикет создаётся **на первом сообщении** — мисклик по deep-link никого не дёргает
- В тикете постоянная кнопка **[✅ Закрыть тикет]** — юзер может закрыть сам

<p align="center">
  <img width="1872" height="888" alt="Phasalo" src="https://github.com/user-attachments/assets/1e33d343-33cb-4682-a172-c654fbcd24a7" />
</p>

<p align="center">
<b>Phasalo</b><br>
<i>Делаем красиво!</i><br><br>
2026
</p>
