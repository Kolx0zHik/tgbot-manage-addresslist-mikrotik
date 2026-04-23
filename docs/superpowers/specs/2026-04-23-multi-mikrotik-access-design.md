# Multi-MikroTik Access Design

## Goal

Add support for multiple MikroTik routers configured only through environment variables.
Bot admins must be able to see and manage every configured MikroTik.
Regular users must be able to see and manage only the MikroTik routers explicitly assigned to them.

## Scope

This design covers:
- environment-driven configuration for multiple MikroTik routers
- role and access resolution for admins and regular users
- Telegram bot UX changes to select a MikroTik first and then work inside that router context
- updates to add and delete flows so they execute against the selected MikroTik
- tests, docs, and startup verification adjustments

This design does not introduce:
- a database
- local config files
- dynamic admin management inside Telegram
- changes to the existing address-list validation rules beyond preserving current behavior

## Requirements

### Functional

- The bot must support more than one MikroTik router at the same time.
- All runtime configuration must come from environment variables.
- The bot must keep a global Telegram allowlist gate.
- The bot must support a separate admin list.
- Admins must see all configured MikroTik routers.
- Regular users must see only the MikroTik routers explicitly assigned to them.
- The main menu must show accessible MikroTik routers first.
- After a user chooses a MikroTik router, the bot must show actions for that router.
- Add and delete flows must run only against the selected MikroTik router.
- `/start` must still reset any active flow and return to the main menu.
- Full address-list deletion must still require explicit confirmation.
- Old inline keyboards must still be treated as stale and rejected safely.

### Non-Functional

- Secrets must remain outside git.
- The design should keep modules small and focused.
- Existing button-first UX should remain intact.
- User-facing texts should stay short and explicit.
- Private-repo Docker and GHCR compatibility must be preserved.

## Configuration Design

### Environment Variables

The single-router variables `MIKROTIK_HOST`, `MIKROTIK_PORT`, `MIKROTIK_USERNAME`, and `MIKROTIK_PASSWORD` are replaced by a multi-router scheme.

Required variables:
- `TG_BOT_TOKEN`
- `ALLOWED_TELEGRAM_USER_IDS`
- `ADMIN_TELEGRAM_USER_IDS`
- `MIKROTIK_IDS`

Per-router required variables for each id from `MIKROTIK_IDS`:
- `MIKROTIK_<ID>_NAME`
- `MIKROTIK_<ID>_HOST`
- `MIKROTIK_<ID>_PORT`
- `MIKROTIK_<ID>_USERNAME`
- `MIKROTIK_<ID>_PASSWORD`

Optional variables:
- `LOG_LEVEL`
- `USER_MIKROTIK_ACCESS_<telegram_user_id>` for every regular user who should access one or more routers

Example:

```env
TG_BOT_TOKEN=replace_me
ALLOWED_TELEGRAM_USER_IDS=111111111,222222222,333333333
ADMIN_TELEGRAM_USER_IDS=111111111
MIKROTIK_IDS=mt1,mt2

MIKROTIK_MT1_NAME=Office
MIKROTIK_MT1_HOST=192.0.2.1
MIKROTIK_MT1_PORT=22
MIKROTIK_MT1_USERNAME=bot-office
MIKROTIK_MT1_PASSWORD=replace_me

MIKROTIK_MT2_NAME=Warehouse
MIKROTIK_MT2_HOST=192.0.2.2
MIKROTIK_MT2_PORT=22
MIKROTIK_MT2_USERNAME=bot-warehouse
MIKROTIK_MT2_PASSWORD=replace_me

USER_MIKROTIK_ACCESS_222222222=mt1
USER_MIKROTIK_ACCESS_333333333=mt2
```

### Validation Rules

- `ALLOWED_TELEGRAM_USER_IDS` must contain at least one user.
- `ADMIN_TELEGRAM_USER_IDS` must be a subset of `ALLOWED_TELEGRAM_USER_IDS`.
- `MIKROTIK_IDS` must contain at least one MikroTik id.
- MikroTik ids are case-insensitive in env input but normalized to uppercase variable suffix lookup and preserved as internal lowercase ids.
- Each MikroTik id must have all required `MIKROTIK_<ID>_*` variables.
- Router names shown in Telegram must not be empty.
- Every `USER_MIKROTIK_ACCESS_<telegram_user_id>` entry must reference only ids declared in `MIKROTIK_IDS`.
- Every non-admin allowed user must have at least one assigned MikroTik router.
- Admin users do not need `USER_MIKROTIK_ACCESS_<telegram_user_id>`.

## Data Model Design

### Settings Layer

Add a focused router configuration model:

```python
@dataclass(frozen=True, slots=True)
class MikroTikSettings:
    id: str
    name: str
    host: str
    port: int
    username: str
    password: str
```

Extend `Settings` with:
- `admin_telegram_user_ids: tuple[int, ...]`
- `mikrotiks: tuple[MikroTikSettings, ...]`
- `mikrotiks_by_id: dict[str, MikroTikSettings]`
- `user_mikrotik_access: dict[int, tuple[str, ...]]`

The settings layer remains the single source of truth for access control and connection data.

### Runtime Access Resolution

Add a small access helper that answers:
- whether a user is authorized for the bot
- whether a user is an admin
- which MikroTik routers are visible to a user
- whether a user may operate on a selected `mikrotik_id`

This keeps Telegram handlers from duplicating permission rules.

## Application Architecture

### SSH Client Construction

The application no longer creates one global `MikroTikSSHClient`.
Instead, startup creates one client per configured MikroTik router and stores them in a registry keyed by `mikrotik_id`.

### Address List Manager Routing

Current business logic assumes a single manager backed by one client.
The new design introduces a small router-aware service layer:
- keep the current `AddressListManager` focused on one client
- add a registry or facade that resolves the correct manager by `mikrotik_id`

This preserves the existing tested add and delete logic while introducing per-router selection at the boundary.

Recommended shape:

```python
class AddressListService:
    def __init__(self, managers_by_id: dict[str, AddressListManager]) -> None:
        ...

    async def fetch_address_lists(self, mikrotik_id: str) -> list[str]:
        ...

    async def add_ips(self, mikrotik_id: str, ...) -> AddOperationResult:
        ...

    async def delete_list(self, mikrotik_id: str, list_name: str) -> DeleteOperationResult:
        ...
```

This keeps single-router logic isolated and minimizes changes in the lower-level MikroTik parsing code.

## Telegram UX Design

### Main Navigation

The top-level bot experience changes from action-first to router-first:

1. User sends `/start`.
2. Bot resets state and shows accessible MikroTik routers.
3. User picks one router.
4. Bot shows a router action menu for that router:
   - `Добавить IP`
   - `Удалить address-list`
   - `Назад`
   - `Помощь`

### Why Router-First

This matches the mental model of the new feature.
Users choose where they want to work before choosing what they want to do.
It also avoids ambiguity in confirmation messages and stale callbacks because every flow is clearly tied to one router.

### Router Labels

Buttons should use `MIKROTIK_<ID>_NAME`.
User-facing texts should mention the chosen router name in prompts and results where it improves clarity.

Examples:
- `MikroTik: Office`
- `Выбран MikroTik: Office`
- `Address-list vpn-office удален на MikroTik Office.`

### Empty Access Case

If an allowed non-admin user has no accessible routers because of a configuration problem, the bot should deny normal use with a short message:

`Для вашего пользователя не назначен ни один MikroTik.`

This should also be logged as a configuration issue.

## FSM Design

The FSM must retain the selected router context across add and delete flows.

New state data:
- `selected_mikrotik_id`
- `selected_mikrotik_name`

New or updated states:
- router selection state in the main menu flow
- router action menu state after a router is selected
- existing add and delete states continue, but now depend on selected router context

Callback session protection remains in place and must apply to router selection and router action buttons too.

## Flow Details

### Router Selection Flow

- `/start` shows available MikroTik routers.
- Selecting a router stores `selected_mikrotik_id` and `selected_mikrotik_name`.
- The next screen shows router-specific actions.
- `Назад` from the router action screen returns to the router selection screen.

### Add Flow

- User enters add flow from the selected router action screen.
- Address-lists are loaded only from the selected router.
- Existing `address-list` selection, new list creation, IP parsing, and confirmation remain unchanged in behavior.
- Confirmation text should include the selected router name.
- Final result text should include the selected router name.

### Delete Flow

- User enters delete flow from the selected router action screen.
- Address-lists are loaded only from the selected router.
- If there are no lists on that router, the bot returns to the router action menu with a short notice.
- Confirmation text should include both list name and router name.
- Final result text should include the selected router name.

## Error Handling

- Connection or SSH failures must mention that the operation failed for the selected MikroTik router.
- If fetching router-specific address-lists fails, the bot should return to the router action menu when possible instead of dropping the entire session.
- If the selected router becomes unauthorized because of stale state or stale callback data, the bot should force the user back to the router selection menu.
- Invalid router ids in callback payloads must be rejected with the same stale-menu safety approach used elsewhere.

## Logging

Logs should include the `mikrotik_id` or router name for:
- startup health checks
- address-list fetches
- add operations
- delete operations
- access-denied cases caused by configuration

This keeps multi-router support operable without exposing secrets.

## Startup Verification

Application startup should perform an initial SSH check for every configured router and log each result separately.
Startup should not abort if one router is unavailable, because the bot may still be usable for other routers.

## Testing Design

### Settings Tests

Add coverage for:
- parsing multiple MikroTik routers from env
- parsing admin ids
- parsing user router access entries
- rejecting unknown router ids in user access
- rejecting missing per-router env values
- rejecting allowed regular users without assigned routers

### Telegram Bot Tests

Add coverage for:
- admins seeing all routers
- regular users seeing only assigned routers
- router selection leading to router action menu
- add flow using only the selected router
- delete flow using only the selected router
- `/start` resetting router context correctly
- stale router-selection callbacks being rejected

### Application Wiring Tests

Add coverage for:
- startup building manager registry for all routers
- startup logging per-router health checks without failing the entire bot when one router is unavailable

## Documentation Updates

Update:
- `.env.example` with multi-router examples
- `README.md` configuration section
- `README.md` bot flow description to explain router-first navigation
- `README.md` manual verification checklist for admin and regular user visibility rules

## Manual Verification Plan

Before completion, manually verify with a real bot run:
- admin account sees all MikroTik routers in the first menu
- regular user sees only assigned MikroTik routers
- selecting a router opens router-specific actions
- add flow works against the selected router
- delete flow works against the selected router and still requires explicit confirmation
- `/start` resets from any step back to router selection
- stale buttons from old router and action menus are rejected safely

## Open Decisions Resolved

- Configuration stays entirely in environment variables.
- No JSON-based env values are introduced.
- Navigation is router-first, then action selection within the chosen router.
