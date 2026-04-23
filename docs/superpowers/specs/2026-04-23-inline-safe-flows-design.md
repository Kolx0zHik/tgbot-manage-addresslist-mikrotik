# Inline Safe Flows Design

## Goal

Translate the Telegram bot into a button-first interface where users enter text only for IP addresses and a new address-list name, while guarding against stale buttons, mixed flows, invalid step transitions, and accidental destructive actions.

## User Experience

- The bot exposes a main inline menu with `Добавить IP`, `Удалить address-list`, `Помощь`, and `Отмена`.
- Adding IPs becomes a strict flow: open add flow, enter IPs, choose existing list or create a new one, review the target list, confirm the add operation.
- Deleting a list becomes a strict flow: open delete flow, choose a list, review the destructive warning, confirm deletion.
- Every screen offers an escape route with `Назад`, `В меню`, or `Отмена`.
- Invalid user actions never trigger implicit transitions. The bot responds with a short explicit warning and keeps the current flow unchanged.

## Safety Model

- Each inline keyboard is tied to a generated flow session id stored in FSM data.
- Every callback verifies authorization, the current flow type, the current step, and the active session id before doing any work.
- If the callback belongs to an old message or another flow, the bot answers with a short warning such as `Это меню уже неактуально. Откройте его заново.`
- Destructive deletion requires a dedicated confirmation callback that includes both the active session id and the chosen list index.
- Double taps and repeated callbacks are idempotent from the bot perspective: stale or repeated callbacks are rejected with a short warning instead of being replayed.

## State Model

FSM data tracks:

- `flow_type`: `menu`, `add`, or `delete`
- `flow_session_id`: unique id for the active keyboard session
- `step`: current screen name inside the flow
- `address_lists`: fetched MikroTik lists for the current flow
- `valid_ips` and `invalid_tokens` for the add flow
- `selected_list_name` for the currently selected add or delete target

## Error Handling

- Text sent during the wrong step produces a short reply describing what the bot expects now.
- Empty or malformed inputs stay on the same step and explain what to send next.
- Missing state data, stale callbacks, and wrong-flow actions return short alerts without changing state.
- MikroTik failures abort the active flow, explain that the router is unavailable, and offer returning to the main menu.

## Implementation Notes

- Keep the work focused in `src/tgbot_manage_addresslist/telegram_bot.py` unless a small helper improves clarity.
- Add compact keyboard builder helpers for the main menu, navigation buttons, and confirmation screens.
- Add a lightweight callback data format like `action:session:payload`.
- Add callback fallback handling so unknown or outdated callbacks do not silently fail.
- Update help text so users see the button-first model instead of the legacy command-only flow.
