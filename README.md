# Telegram MikroTik Address List Bot

RU: Telegram-бот для управления MikroTik firewall `address-list` по SSH.  
EN: Telegram bot for managing MikroTik firewall `address-list` entries over SSH.

## Overview / Описание

RU:
- Бот работает в button-first режиме: основной сценарий идет через inline-кнопки.
- Telegram menu button содержит только `/start` и служит безопасным возвратом в главное меню.
- Бот сначала предлагает выбрать MikroTik, а затем действия для выбранного роутера.
- Админы видят все MikroTik, обычные пользователи видят только назначенные им.
- Бот умеет добавлять IP-адреса и CIDR-подсети в существующий или новый `address-list`.
- Для нового `address-list` бот автоматически создает `mangle`-правило, отправляющее трафик через `VPN_Table`.
- Бот отдельно показывает добавленные адреса, дубликаты, невалидные значения и ошибки MikroTik.
- Полное удаление `address-list` выполняется только после явного подтверждения и удаляет связанное `mangle`-правило.
- Список существующих `address-list` доступен отдельной кнопкой, оттуда можно выбрать список для удаления.

EN:
- The bot uses a button-first UX: main flows are driven by inline keyboards.
- The Telegram menu button contains only `/start` and acts as the safe way back to the main menu.
- The bot asks the user to choose a MikroTik router first and only then shows router-specific actions.
- Admins can see all MikroTik routers, while regular users can only see routers assigned to them.
- The bot can add IP addresses and CIDR subnets to an existing or new `address-list`.
- For a new `address-list`, the bot automatically creates a `mangle` rule that routes traffic through `VPN_Table`.
- The bot reports added entries, duplicates, invalid values, and MikroTik-side errors separately.
- Full `address-list` deletion requires explicit confirmation and removes the matching `mangle` rule.
- Existing `address-list` names are shown from a dedicated button, with delete actions available from that menu.

## Features / Возможности

- RU: inline-кнопки для основных сценариев  
  EN: inline keyboards for the main flows
- RU: сначала выбор MikroTik, затем работа внутри выбранного роутера  
  EN: router-first navigation before add/delete actions
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
- RU: просмотр существующих `address-list` перед удалением
  EN: review existing `address-list` names before deletion
- RU: allowlist по Telegram user ID  
  EN: allowlist by Telegram user ID
- RU: админы управляют всеми MikroTik, обычные пользователи только своими  
  EN: admins manage all MikroTik routers, regular users only their assigned routers
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
- `ADMIN_TELEGRAM_USER_IDS`

Per-router required variables / Обязательные переменные для каждого MikroTik:

- `MIKROTIK_1_NAME`
- `MIKROTIK_1_HOST`
- `MIKROTIK_1_PORT`
- `MIKROTIK_1_USERNAME`
- `MIKROTIK_1_PASSWORD`
- `MIKROTIK_1_TELEGRAM_USER_IDS`

RU: Добавляйте следующие MikroTik как `MIKROTIK_2_*`, `MIKROTIK_3_*` и так далее без пропусков.  
EN: Add the next routers as `MIKROTIK_2_*`, `MIKROTIK_3_*`, and so on without gaps.

Optional / Необязательные переменные:

- `LOG_LEVEL` — defaults to `INFO` / по умолчанию `INFO`

RU: `ALLOWED_TELEGRAM_USER_IDS` больше не нужен. Бот собирает доступ автоматически из `ADMIN_TELEGRAM_USER_IDS` и `MIKROTIK_N_TELEGRAM_USER_IDS`.  
EN: `ALLOWED_TELEGRAM_USER_IDS` is no longer needed. The bot builds access automatically from `ADMIN_TELEGRAM_USER_IDS` and `MIKROTIK_N_TELEGRAM_USER_IDS`.

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

### Router Selection / Выбор MikroTik

RU:
1. Отправьте `/start`.
2. Выберите доступный MikroTik.
3. Бот покажет действия для выбранного роутера.

EN:
1. Send `/start`.
2. Choose an accessible MikroTik router.
3. The bot will show actions for the selected router.

### Add Flow / Добавление адресов

RU:
1. Выберите MikroTik.
2. Нажмите `Добавить IP`.
3. Выберите существующий `address-list` или нажмите `Создать новый address-list`.
4. Если создается новый список, отправьте его имя.
5. Бот попросит ввести IP-адреса или CIDR-подсети для выбранного списка.
6. Бот покажет подтверждение.
7. После подтверждения бот добавит адреса и покажет результат.

EN:
1. Choose a MikroTik router.
2. Press `Добавить IP`.
3. Choose an existing `address-list` or press `Создать новый address-list`.
4. If creating a new list, send its name.
5. The bot will ask for IP addresses or CIDR subnets for the selected list.
6. The bot will show a confirmation step.
7. After confirmation, the bot will add the entries and show the result.

### List And Delete Flow / Просмотр и удаление списка

RU:
1. Выберите MikroTik.
2. Нажмите `Список address-list`.
3. Проверьте список существующих `address-list`.
4. Нажмите `Удалить <имя списка>`.
5. Подтвердите удаление.

EN:
1. Choose a MikroTik router.
2. Press `Список address-list`.
3. Review the existing `address-list` names.
4. Press `Удалить <list name>`.
5. Confirm the deletion.

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
- RU: отправить `/start` и убедиться, что бот сбрасывает активный сценарий и открывает выбор MikroTik  
  EN: send `/start` and confirm the bot resets any active flow and opens MikroTik selection
- RU: проверить, что админ видит все MikroTik в первом меню  
  EN: verify that an admin can see all MikroTik routers in the first menu
- RU: проверить, что обычный пользователь видит только назначенные ему MikroTik  
  EN: verify that a regular user sees only assigned MikroTik routers
- RU: выбрать MikroTik и убедиться, что бот показывает действия именно для него  
  EN: choose a MikroTik router and confirm the bot shows router-specific actions
- RU: пройти сценарий `Добавить IP` для существующего списка на выбранном MikroTik  
  EN: complete the `Добавить IP` flow for an existing list on the selected MikroTik
- RU: пройти сценарий `Создать новый address-list` и затем добавить IP  
  EN: complete the `Создать новый address-list` flow and then add IPs
- RU: проверить, что CIDR-подсети принимаются  
  EN: verify that CIDR subnets are accepted
- RU: проверить, что дубликаты корректно попадают в блок `Дубликаты`  
  EN: verify that duplicates are reported under `Дубликаты`
- RU: проверить, что имя нового списка с кириллицей отклоняется  
  EN: verify that a new list name containing Cyrillic is rejected
- RU: нажать старую кнопку выбора MikroTik или старую action-кнопку и убедиться, что бот сообщает о неактуальном меню  
  EN: press an old MikroTik-selection or old action button and confirm the bot reports that the menu is stale
- RU: нажать `Список address-list` и убедиться, что бот показывает существующие списки с кнопками удаления
  EN: press `Список address-list` and confirm the bot shows existing lists with delete buttons
- RU: убедиться, что удаление `address-list` требует явного подтверждения и удаляет список только на выбранном MikroTik  
  EN: confirm that deleting an `address-list` requires explicit confirmation and only affects the selected MikroTik

## Supported Commands / Поддерживаемые команды

- `/start` — RU: открыть главное меню; EN: open the main menu
- `/delete_list` — RU: открыть сценарий удаления списка на выбранном MikroTik; EN: open the list deletion flow for the selected MikroTik
- `/cancel` — RU: отменить текущий сценарий; EN: cancel the current flow
- `/help` — RU: показать краткую помощь; EN: show short help

## RouterOS Commands Used / Используемые команды RouterOS

- list address-lists: `/ip firewall address-list print terse without-paging`
- add entry: `/ip firewall address-list add list="NAME" address="IP"`
- delete full list: `/ip firewall address-list remove [find list="NAME"]`
- add VPN routing mangle rule for new list at the top of mangle rules: `/ip firewall mangle add chain=prerouting dst-address-list="NAME" action=mark-routing new-routing-mark="VPN_Table" passthrough=yes place-before=0 comment="tgbot_manage_addresslist: route NAME via VPN_Table"`
- delete VPN routing mangle rule: `/ip firewall mangle remove [find comment="tgbot_manage_addresslist: route NAME via VPN_Table"]`

## Security Notes / Замечания по безопасности

- RU: не коммитьте `.env` и реальные секреты  
  EN: do not commit `.env` or real secrets
- RU: используйте отдельного пользователя MikroTik для бота  
  EN: use a dedicated MikroTik user for the bot
- RU: выдавайте этому пользователю только нужные права на `address-list` и `mangle`
  EN: grant that user only the permissions required for `address-list` and `mangle`
