# Telegram MikroTik Address List Bot

RU: Telegram-бот для управления MikroTik firewall `address-list` по SSH.  
EN: Telegram bot for managing MikroTik firewall `address-list` entries over SSH.

## Overview / Описание

RU:
- Бот работает в button-first режиме: основной сценарий идет через inline-кнопки.
- Telegram menu button содержит только `/start` и служит безопасным возвратом в главное меню.
- Бот умеет добавлять IP-адреса и CIDR-подсети в существующий или новый `address-list`.
- Бот отдельно показывает добавленные адреса, дубликаты, невалидные значения и ошибки MikroTik.
- Полное удаление `address-list` выполняется только после явного подтверждения.

EN:
- The bot uses a button-first UX: main flows are driven by inline keyboards.
- The Telegram menu button contains only `/start` and acts as the safe way back to the main menu.
- The bot can add IP addresses and CIDR subnets to an existing or new `address-list`.
- The bot reports added entries, duplicates, invalid values, and MikroTik-side errors separately.
- Full `address-list` deletion requires explicit confirmation.

## Features / Возможности

- RU: inline-кнопки для основных сценариев  
  EN: inline keyboards for the main flows
- RU: добавление IP-адресов и CIDR-подсетей  
  EN: add IP addresses and CIDR subnets
- RU: выбор существующего `address-list` до ввода IP  
  EN: choose the target `address-list` before entering IPs
- RU: создание нового `address-list` с проверкой имени  
  EN: create a new `address-list` with name validation
- RU: запрет кириллицы в имени нового `address-list`  
  EN: reject Cyrillic characters in new `address-list` names
- RU: защита от устаревших кнопок и неверных шагов сценария  
  EN: reject stale buttons and wrong-step actions
- RU: allowlist по Telegram user ID  
  EN: allowlist by Telegram user ID
- RU: Docker и публикация в GHCR  
  EN: Docker support and GHCR publishing

## Stack / Стек

- Python 3.12
- `aiogram`
- `asyncssh`
- Docker / Docker Compose

## Configuration / Конфигурация

RU: Скопируйте `.env.example` в `.env` и заполните значения.  
EN: Copy `.env.example` to `.env` and fill in the values.

Required / Обязательные переменные:

- `TG_BOT_TOKEN`
- `ALLOWED_TELEGRAM_USER_IDS`
- `MIKROTIK_HOST`
- `MIKROTIK_PORT`
- `MIKROTIK_USERNAME`
- `MIKROTIK_PASSWORD`

Optional / Необязательные переменные:

- `LOG_LEVEL` — defaults to `INFO` / по умолчанию `INFO`

RU: Используйте отдельного пользователя MikroTik для бота.  
EN: Use a dedicated MikroTik user for the bot.

## Local Run / Локальный запуск

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
cp .env.example .env
python -m tgbot_manage_addresslist
```

## Docker Run / Запуск через Docker

```bash
cp .env.example .env
docker compose up --build -d
docker compose logs -f tgbot_mikrotik
```

RU: Имя образа уже зафиксировано в [compose.yaml](/opt/projects/bot_add_ip_mikrotik/compose.yaml).  
EN: The image name is already fixed in [compose.yaml](/opt/projects/bot_add_ip_mikrotik/compose.yaml).

## Bot Flow / Сценарий работы

### Add Flow / Добавление адресов

RU:
1. Нажмите `Добавить IP`.
2. Выберите существующий `address-list` или нажмите `Создать новый address-list`.
3. Если создается новый список, отправьте его имя.
4. Бот попросит ввести IP-адреса или CIDR-подсети для выбранного списка.
5. Бот покажет подтверждение.
6. После подтверждения бот добавит адреса и покажет результат.

EN:
1. Press `Добавить IP`.
2. Choose an existing `address-list` or press `Создать новый address-list`.
3. If creating a new list, send its name.
4. The bot will ask for IP addresses or CIDR subnets for the selected list.
5. The bot will show a confirmation step.
6. After confirmation, the bot will add the entries and show the result.

### Delete Flow / Удаление списка

RU:
1. Нажмите `Удалить address-list`.
2. Выберите список.
3. Подтвердите удаление.

EN:
1. Press `Удалить address-list`.
2. Choose a list.
3. Confirm the deletion.

## Validation Rules / Правила валидации

RU:
- Бот принимает одиночные IP-адреса и CIDR-подсети.
- Имя нового `address-list` не должно быть пустым.
- Имя нового `address-list` не должно содержать кириллицу.
- Если вместо имени нового списка отправить IP, бот попросит ввести именно имя.

EN:
- The bot accepts single IP addresses and CIDR subnets.
- A new `address-list` name must not be empty.
- A new `address-list` name must not contain Cyrillic characters.
- If an IP is sent where a new list name is expected, the bot asks for a name instead.

## Manual Verification / Ручная проверка

- RU: убедиться, что Telegram menu button содержит только `/start`  
  EN: confirm the Telegram menu button contains only `/start`
- RU: отправить `/start` и убедиться, что бот сбрасывает активный сценарий и открывает главное меню  
  EN: send `/start` and confirm the bot resets any active flow and opens the main menu
- RU: пройти сценарий `Добавить IP` для существующего списка  
  EN: complete the `Добавить IP` flow for an existing list
- RU: пройти сценарий `Создать новый address-list` и затем добавить IP  
  EN: complete the `Создать новый address-list` flow and then add IPs
- RU: проверить, что CIDR-подсети принимаются  
  EN: verify that CIDR subnets are accepted
- RU: проверить, что дубликаты корректно попадают в блок `Дубликаты`  
  EN: verify that duplicates are reported under `Дубликаты`
- RU: проверить, что имя нового списка с кириллицей отклоняется  
  EN: verify that a new list name containing Cyrillic is rejected
- RU: нажать старую кнопку из истории и убедиться, что бот сообщает о неактуальном меню  
  EN: press an old button from history and confirm the bot reports that the menu is stale
- RU: убедиться, что удаление `address-list` требует явного подтверждения  
  EN: confirm that deleting an `address-list` requires explicit confirmation

## Supported Commands / Поддерживаемые команды

- `/start` — RU: открыть главное меню; EN: open the main menu
- `/delete_list` — RU: открыть сценарий удаления списка; EN: open the list deletion flow
- `/cancel` — RU: отменить текущий сценарий; EN: cancel the current flow
- `/help` — RU: показать краткую помощь; EN: show short help

## RouterOS Commands Used / Используемые команды RouterOS

- list address-lists: `/ip firewall address-list print terse without-paging`
- add entry: `/ip firewall address-list add list="NAME" address="IP"`
- delete full list: `/ip firewall address-list remove [find list="NAME"]`

## Security Notes / Замечания по безопасности

- RU: не коммитьте `.env` и реальные секреты  
  EN: do not commit `.env` or real secrets
- RU: используйте отдельного пользователя MikroTik для бота  
  EN: use a dedicated MikroTik user for the bot
- RU: выдавайте этому пользователю только нужные права на `address-list`  
  EN: grant that user only the permissions required for `address-list`
