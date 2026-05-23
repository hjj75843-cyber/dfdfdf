import asyncio
import csv
import hashlib
import html
import json
import logging
import os
import re
import shutil
import sqlite3
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import aiosqlite
from aiohttp import web
from aiogram import BaseMiddleware, Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, FSInputFile, InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, Message, ReplyKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

BOT_TOKEN = os.getenv("BOT_TOKEN", "8315257655:AAHvfV6QOtM9WZtF5hd0Ogt1vjmiEPxCW-k")
VERSION = "HYPER MEGA SUPER ULTRA GLOBAL PRO PLUS MAX PREMIUM ELITE SUPREME ULTIMATE DELUXE PLATINUM EDITION 2.0"
PROJECT_NAME = "CHIGURH GLOBAL"
MAIN_CHANNEL_ID = os.getenv("MAIN_CHANNEL_ID", "-1003952527688")
OWNER_IDS = [7834317269, 1769080824]
CREATORS = ["MRTOTEMCHIK", "KEMEL"]
WEB_HOST = os.getenv("WEB_HOST", "127.0.0.1")
WEB_PORT = int(os.getenv("WEB_PORT", "8088"))
WEB_APP_SECRET = os.getenv("WEB_APP_SECRET", "kemel")
DATABASE_PATH = Path(os.getenv("DATABASE_PATH", "hyper_global_2_0.db"))
STORAGE_DIR = Path(os.getenv("STORAGE_DIR", "hyper_global_storage"))
CODE_DIR = STORAGE_DIR / "codes"
BACKUP_DIR = STORAGE_DIR / "backups"
EXPORT_DIR = STORAGE_DIR / "exports"
TEMP_DIR = STORAGE_DIR / "temp"
MEDIA_DIR = STORAGE_DIR / "media"

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(name)s - %(message)s")
logger = logging.getLogger("hyper_global_2_0")

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()
router = Router()

user_buffers: dict[str, dict[str, Any]] = {}
rate_limits: dict[str, list[float]] = {}

SCRIPT_TYPES = [
    "Универсальный", "Хаб", "Auto Farm", "ESP", "Aimbot", "Teleport", "Dupe", "Keyless", "GUI", "Admin",
    "Farm", "OP", "Silent Aim", "Hitbox", "Speed", "Fly", "Noclip", "God Mode", "Anti AFK", "Server Hop",
    "Trade", "Pet", "Money", "Level", "Webhook", "Bypass", "Event", "Raid", "Quest", "Visual",
    "Utility", "Movement", "Combat", "Premium", "Free", "Mobile", "PC"
]
PLATFORMS = ["Mobile", "PC", "Mobile + PC", "Universal", "Unknown"]
SCRIPT_STATUSES = ["Работает", "Не проверен", "Обновлён", "Старый", "Сломан", "Риск", "Премиум", "Бесплатный"]
POST_STYLES = ["Глобалка", "Тёмный премиум", "Неон", "Чистый минимал", "Roblox Hub", "Большой релиз", "Короткий", "Технический", "Русский"]
MODULE_CATEGORIES = ["Публикации", "Канал", "Код", "Файлы", "Фото", "Черновики", "База", "Поиск", "Шаблоны", "Оформление", "Очередь", "Статистика", "Backup", "Безопасность", "Браузер", "Логи", "Глобалки", "Медиа", "Настройки", "Автоматизация"]
MODULE_ACTIONS = ["быстрый режим", "полный режим", "редактирование", "автосохранение", "проверка", "экспорт", "импорт", "пагинация", "поиск", "фильтр", "сортировка", "архив", "восстановление", "тест", "уведомление", "повтор", "очистка", "шаблон", "предпросмотр", "безопасная отправка"]


def ensure_dirs() -> None:
    for directory in [STORAGE_DIR, CODE_DIR, BACKUP_DIR, EXPORT_DIR, TEMP_DIR, MEDIA_DIR]:
        directory.mkdir(parents=True, exist_ok=True)


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def clean(value: Any) -> str:
    return str(value or "").strip()


def safe_html(value: Any) -> str:
    return html.escape("" if value is None else str(value), quote=False)


def normalize_code(code: str) -> str:
    lines = clean(code).replace("\r\n", "\n").replace("\r", "\n").split("\n")
    return "\n".join(line.rstrip() for line in lines if line.strip())


def code_hash(code: str) -> str:
    return hashlib.sha256(normalize_code(code).encode("utf-8", errors="ignore")).hexdigest()


def slugify(value: str, fallback: str = "script") -> str:
    raw = clean(value).lower()
    result = []
    for char in raw:
        if char.isalnum():
            result.append(char)
        elif char in {" ", "-", "_", "."}:
            result.append("_")
    slug = "".join(result).strip("_")
    while "__" in slug:
        slug = slug.replace("__", "_")
    return slug[:90] if slug else fallback


def chunk_text(text: str, limit: int = 3800) -> list[str]:
    text = clean(text)
    if len(text) <= limit:
        return [text]
    chunks = []
    current = []
    size = 0
    for line in text.splitlines():
        line_size = len(line) + 1
        if current and size + line_size > limit:
            chunks.append("\n".join(current))
            current = [line]
            size = line_size
        else:
            current.append(line)
            size += line_size
    if current:
        chunks.append("\n".join(current))
    return chunks


def parse_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value == 1
    return str(value).lower() in {"1", "true", "yes", "да", "on"}


def normalize_data(data: dict[str, Any] | None = None) -> dict[str, Any]:
    base = {
        "photo_id": "",
        "game_name": "",
        "script_name": "",
        "script_type": "Универсальный",
        "platform": "Mobile + PC",
        "key_required": False,
        "status": "Работает",
        "version": "1.0",
        "features": "",
        "tags": "",
        "description": "",
        "instruction": "",
        "lua_code": "",
        "note": "",
        "style": "Глобалка",
        "mode": "full",
    }
    if data:
        for key, value in data.items():
            if key in base:
                base[key] = value
    base["key_required"] = parse_bool(base.get("key_required"))
    base["lua_code"] = normalize_code(base.get("lua_code", ""))
    return base


def validate_post_data(data: dict[str, Any]) -> list[str]:
    issues = []
    if len(clean(data.get("game_name"))) < 2:
        issues.append("Название игры слишком короткое")
    if len(clean(data.get("script_name"))) < 2:
        issues.append("Название скрипта слишком короткое")
    if len(clean(data.get("features"))) < 3:
        issues.append("Функции не заполнены")
    if len(normalize_code(data.get("lua_code", ""))) < 10:
        issues.append("Lua-код слишком короткий или пустой")
    if not clean(data.get("script_type")):
        issues.append("Тип скрипта не выбран")
    if not clean(data.get("platform")):
        issues.append("Платформа не выбрана")
    return issues


def clean_design_text(text: str) -> str:
    raw_lines = clean(text).replace("\r\n", "\n").replace("\r", "\n").split("\n")
    blocked = [
        "подпиш", "subscribe", "join", "канал", "channel", "telegram", "реклама", "advert", "promo",
        "купить", "продажа", "донат", "discord", "youtube", "tiktok", "instagram"
    ]
    result = []
    for line in raw_lines:
        stripped = line.strip()
        low = stripped.lower()
        if not stripped:
            if result and result[-1] != "":
                result.append("")
            continue
        if re.search(r"https?://\S+", stripped):
            continue
        if re.search(r"(?:t\.me|telegram\.me|telegram\.dog)/\S+", low):
            continue
        if re.search(r"@[a-zA-Z0-9_]{4,}", stripped):
            continue
        if any(word in low for word in blocked):
            continue
        cleaned = re.sub(r"https?://\S+", "", stripped)
        cleaned = re.sub(r"(?:t\.me|telegram\.me|telegram\.dog)/\S+", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"@[a-zA-Z0-9_]{4,}", "", cleaned)
        cleaned = cleaned.strip()
        if cleaned:
            result.append(cleaned)
    while result and result[-1] == "":
        result.pop()
    return "\n".join(result).strip()


@asynccontextmanager
async def open_db():
    ensure_dirs()
    db = await aiosqlite.connect(DATABASE_PATH, timeout=30)
    db.row_factory = aiosqlite.Row
    try:
        await db.execute("PRAGMA journal_mode=WAL")
        await db.execute("PRAGMA busy_timeout=5000")
        await db.execute("PRAGMA foreign_keys=ON")
        yield db
    finally:
        await db.close()


async def db_run(query: str, params: tuple[Any, ...] = (), retries: int = 6) -> None:
    last_error = None
    for attempt in range(retries):
        try:
            async with open_db() as db:
                await db.execute(query, params)
                await db.commit()
            return
        except sqlite3.OperationalError as error:
            last_error = error
            if "locked" not in str(error).lower():
                raise
            await asyncio.sleep(0.12 * (attempt + 1))
    raise last_error


async def db_one(query: str, params: tuple[Any, ...] = ()) -> dict[str, Any] | None:
    async with open_db() as db:
        async with db.execute(query, params) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None


async def db_all(query: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    async with open_db() as db:
        async with db.execute(query, params) as cursor:
            return [dict(row) for row in await cursor.fetchall()]


async def init_db() -> None:
    ensure_dirs()
    async with open_db() as db:
        await db.execute("CREATE TABLE IF NOT EXISTS users (telegram_id TEXT PRIMARY KEY, role TEXT NOT NULL, username TEXT, name TEXT, is_active INTEGER DEFAULT 1, last_seen TEXT, created_at TEXT)")
        await db.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT, updated_at TEXT)")
        await db.execute("CREATE TABLE IF NOT EXISTS logs (id INTEGER PRIMARY KEY AUTOINCREMENT, action TEXT, actor_id TEXT, actor_name TEXT, details TEXT, created_at TEXT)")
        await db.execute("CREATE TABLE IF NOT EXISTS scripts (id INTEGER PRIMARY KEY AUTOINCREMENT, game_name TEXT, script_name TEXT, script_type TEXT, platform TEXT, key_required INTEGER DEFAULT 0, status TEXT, version TEXT, features TEXT, tags TEXT, description TEXT, instruction TEXT, lua_code TEXT, code_hash TEXT, photo_id TEXT, style TEXT, created_by TEXT, created_at TEXT, updated_at TEXT, use_count INTEGER DEFAULT 0, publish_count INTEGER DEFAULT 0, archived INTEGER DEFAULT 0)")
        await db.execute("CREATE TABLE IF NOT EXISTS posts (id INTEGER PRIMARY KEY AUTOINCREMENT, script_id INTEGER, creator_id TEXT, game_name TEXT, script_name TEXT, telegram_message_id TEXT, file_message_id TEXT, code_file_path TEXT, status TEXT, error TEXT, created_at TEXT)")
        await db.execute("CREATE TABLE IF NOT EXISTS drafts (id INTEGER PRIMARY KEY AUTOINCREMENT, creator_id TEXT, title TEXT, data_json TEXT, created_at TEXT, updated_at TEXT)")
        await db.execute("CREATE TABLE IF NOT EXISTS queue (id INTEGER PRIMARY KEY AUTOINCREMENT, creator_id TEXT, data_json TEXT, publish_at TEXT, status TEXT, error TEXT, created_at TEXT, updated_at TEXT)")
        await db.execute("CREATE TABLE IF NOT EXISTS templates (id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT, body TEXT, source TEXT, created_by TEXT, created_at TEXT)")
        await db.execute("CREATE TABLE IF NOT EXISTS favorites (user_id TEXT, script_id INTEGER, created_at TEXT, PRIMARY KEY(user_id, script_id))")
        await db.execute("CREATE TABLE IF NOT EXISTS media (id INTEGER PRIMARY KEY AUTOINCREMENT, file_id TEXT, title TEXT, created_by TEXT, created_at TEXT)")
        await db.execute("CREATE TABLE IF NOT EXISTS modules (id INTEGER PRIMARY KEY, category TEXT, title TEXT, enabled INTEGER DEFAULT 1, created_at TEXT)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_scripts_hash ON scripts(code_hash)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_scripts_search ON scripts(game_name, script_name, script_type, status, tags)")
        for owner_id in OWNER_IDS:
            await db.execute("INSERT OR IGNORE INTO users (telegram_id, role, username, name, is_active, last_seen, created_at) VALUES (?, 'owner', '', '', 1, ?, ?)", (str(owner_id), now_iso(), now_iso()))
            await db.execute("UPDATE users SET role = 'owner', is_active = 1 WHERE telegram_id = ?", (str(owner_id),))
        defaults = {
            "project_name": PROJECT_NAME,
            "main_channel_id": MAIN_CHANNEL_ID,
            "footer": "@ChigurhScripts",
            "menu_photo_id": "",
            "web_public_url": "",
            "web_app_secret": WEB_APP_SECRET,
            "default_style": "Глобалка",
            "antispam_enabled": "1",
            "auto_save_scripts": "1",
            "send_post_before_file": "1",
            "browser_app_enabled": "1",
        }
        for key, value in defaults.items():
            await db.execute("INSERT OR IGNORE INTO settings (key, value, updated_at) VALUES (?, ?, ?)", (key, value, now_iso()))
        count_row = await db.execute("SELECT COUNT(*) FROM modules")
        count = (await count_row.fetchone())[0]
        if count == 0:
            index = 1
            for category in MODULE_CATEGORIES:
                for action in MODULE_ACTIONS:
                    await db.execute("INSERT OR IGNORE INTO modules (id, category, title, enabled, created_at) VALUES (?, ?, ?, 1, ?)", (index, category, f"{category}: {action}", now_iso()))
                    index += 1
        await db.commit()


async def get_setting(key: str, default: str = "") -> str:
    row = await db_one("SELECT value FROM settings WHERE key = ?", (key,))
    return str(row["value"]) if row else default


async def set_setting(key: str, value: str) -> None:
    await db_run("INSERT OR REPLACE INTO settings (key, value, updated_at) VALUES (?, ?, ?)", (key, value, now_iso()))


async def log_action(action: str, actor: Any, details: str = "") -> None:
    actor_id = str(getattr(actor, "id", actor))
    actor_name = getattr(actor, "username", None) or getattr(actor, "first_name", None) or actor_id
    await db_run("INSERT INTO logs (action, actor_id, actor_name, details, created_at) VALUES (?, ?, ?, ?, ?)", (action, actor_id, actor_name, clean(details), now_iso()))


@dataclass
class Access:
    role: str
    allowed: bool


async def get_access(user: Any) -> Access:
    if not user:
        return Access("guest", False)
    user_id = str(user.id)
    if user.id in OWNER_IDS:
        await db_run("UPDATE users SET username = ?, name = ?, last_seen = ?, is_active = 1 WHERE telegram_id = ?", (user.username or "", user.first_name or "", now_iso(), user_id))
        return Access("owner", True)
    row = await db_one("SELECT role, is_active FROM users WHERE telegram_id = ?", (user_id,))
    if row and int(row["is_active"]) == 1:
        await db_run("UPDATE users SET username = ?, name = ?, last_seen = ? WHERE telegram_id = ?", (user.username or "", user.first_name or "", now_iso(), user_id))
        return Access(str(row["role"]), True)
    return Access("guest", False)


async def check_rate_limit(user_id: str) -> bool:
    if await get_setting("antispam_enabled", "1") != "1":
        return True
    now_ts = time.time()
    window = [ts for ts in rate_limits.get(user_id, []) if now_ts - ts < 2.0]
    window.append(now_ts)
    rate_limits[user_id] = window
    return len(window) <= 10


class AccessMiddleware(BaseMiddleware):
    async def __call__(self, handler, event, data):
        user = data.get("event_from_user")
        if isinstance(event, Message) and (event.text or "").startswith("/myid"):
            return await handler(event, data)
        access = await get_access(user)
        if access.allowed:
            if user and not await check_rate_limit(str(user.id)):
                if isinstance(event, CallbackQuery):
                    await event.answer("Слишком быстро. Подожди пару секунд.", show_alert=True)
                else:
                    await event.answer("Слишком быстро. Подожди пару секунд.")
                return None
            data["role"] = access.role
            return await handler(event, data)
        if isinstance(event, CallbackQuery):
            await event.answer("⛔ Нет доступа.", show_alert=True)
            return None
        await event.answer("⛔ Нет доступа. Отправь /myid владельцу.")
        return None


class PostStates(StatesGroup):
    photo_choice = State()
    photo = State()
    game_name = State()
    script_name = State()
    script_type = State()
    platform = State()
    key_required = State()
    status = State()
    version = State()
    features = State()
    tags = State()
    description = State()
    instruction = State()
    code = State()
    note = State()
    style = State()
    preview = State()
    edit_text = State()
    edit_code = State()
    edit_photo = State()


class SearchStates(StatesGroup):
    scripts = State()
    modules = State()


class DesignStates(StatesGroup):
    clean_title = State()
    clean_text = State()
    template_title = State()
    template_body = State()


class SettingsStates(StatesGroup):
    value = State()
    menu_photo = State()


class MediaStates(StatesGroup):
    photo = State()
    title = State()


def inline_rows(rows: list[list[tuple[str, str]]]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for row in rows:
        builder.row(*[InlineKeyboardButton(text=text, callback_data=data) for text, data in row])
    return builder.as_markup()


def button_grid(items: list[str], prefix: str, width: int = 3) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    row = []
    for item in items:
        row.append(InlineKeyboardButton(text=item, callback_data=f"{prefix}:{item}"))
        if len(row) == width:
            builder.row(*row)
            row = []
    if row:
        builder.row(*row)
    builder.row(InlineKeyboardButton(text="🛑 Отмена", callback_data="flow:cancel"))
    return builder.as_markup()


def main_reply_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🔥 Создать пост"), KeyboardButton(text="⚡ Быстрый пост")],
            [KeyboardButton(text="📚 База"), KeyboardButton(text="🌐 Глобалки")],
            [KeyboardButton(text="🧾 Черновики"), KeyboardButton(text="🗓 Очередь")],
            [KeyboardButton(text="🎨 Оформление"), KeyboardButton(text="🖼 Медиа")],
            [KeyboardButton(text="📊 Статистика"), KeyboardButton(text="⚙️ Настройки")],
            [KeyboardButton(text="🌍 Приложение"), KeyboardButton(text="❓ Помощь")],
        ],
        resize_keyboard=True,
        input_field_placeholder="GLOBAL 2.0",
    )


def main_inline_keyboard() -> InlineKeyboardMarkup:
    return inline_rows([
        [("🔥 Создать", "post:start:full"), ("⚡ Быстро", "post:start:quick")],
        [("📚 База", "db:menu"), ("🌐 Глобалки", "global:menu")],
        [("🧾 Черновики", "drafts:list:0"), ("🗓 Очередь", "queue:menu")],
        [("🎨 Оформление", "design:menu"), ("🌍 Приложение", "webapp:info")],
        [("📊 Статистика", "stats:show"), ("⚙️ Настройки", "settings:menu")],
    ])


def preview_keyboard() -> InlineKeyboardMarkup:
    return inline_rows([
        [("🚀 Опубликовать", "preview:publish"), ("🧾 Черновик", "preview:draft")],
        [("🗓 В очередь 10 мин", "preview:queue10"), ("⏰ В очередь 1 час", "preview:queue60")],
        [("✏️ Игра", "edit:game_name"), ("✏️ Название", "edit:script_name")],
        [("⚙️ Функции", "edit:features"), ("💻 Код", "edit:lua_code")],
        [("🎨 Стиль", "edit:style"), ("🖼 Фото", "edit:photo")],
        [("🛑 Отмена", "flow:cancel")],
    ])


def db_keyboard() -> InlineKeyboardMarkup:
    return inline_rows([
        [("🔍 Поиск", "db:search"), ("📋 Все", "db:list:0")],
        [("➕ Добавить", "post:start:full"), ("⭐ Избранное", "db:favorites:0")],
        [("🏆 Топ", "db:top:0"), ("🌐 Глобалки", "db:global:0")],
        [("📤 Export CSV", "export:scripts"), ("◀️ Меню", "menu:home")],
    ])


def settings_keyboard() -> InlineKeyboardMarkup:
    rows = [
        [("📣 Канал публикации", "settings:edit:main_channel_id")],
        [("🏷 Название проекта", "settings:edit:project_name"), ("🔗 Подвал", "settings:edit:footer")],
        [("🌍 URL приложения", "settings:edit:web_public_url"), ("🔐 Ключ сайта", "settings:edit:web_app_secret")],
        [("🖼 Фото меню", "settings:menu_photo"), ("🧪 Тест", "test:run")],
        [("💾 Backup", "backup:create"), ("📜 Логи", "logs:show")],
        [("◀️ Меню", "menu:home")],
    ]
    return inline_rows(rows)


def design_keyboard() -> InlineKeyboardMarkup:
    return inline_rows([
        [("🧼 Очистить оформление", "design:clean"), ("📋 Шаблоны", "design:templates:0")],
        [("➕ Создать шаблон", "design:new_template"), ("🎨 Стили", "design:styles")],
        [("🖼 Фото меню", "settings:menu_photo"), ("◀️ Меню", "menu:home")],
    ])


def queue_keyboard() -> InlineKeyboardMarkup:
    return inline_rows([
        [("📋 Список", "queue:list"), ("▶️ Опубликовать следующий", "queue:next")],
        [("🧹 Очистить ожидание", "queue:clear"), ("◀️ Меню", "menu:home")],
    ])


def webapp_button(url: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🌍 Открыть приложение", url=url)]])


async def generate_post(data: dict[str, Any]) -> str:
    data = normalize_data(data)
    footer = await get_setting("footer", "@ChigurhScripts")
    style = data.get("style", "Глобалка")
    game = safe_html(data.get("game_name"))
    script = safe_html(data.get("script_name"))
    script_type = safe_html(data.get("script_type"))
    platform = safe_html(data.get("platform"))
    status = safe_html(data.get("status"))
    version = safe_html(data.get("version"))
    key_text = "Да" if data.get("key_required") else "Нет"
    features = format_features(data.get("features", ""), style)
    tags = build_hashtags(data)
    description = safe_html(data.get("description"))
    instruction = safe_html(data.get("instruction"))
    note = safe_html(data.get("note"))

    if style == "Тёмный премиум":
        text = f"🌑 <b>{script}</b>\n━━━━━━━━━━━━━━━━\n🎮 <b>Игра:</b> {game}\n🧩 <b>Тип:</b> {script_type}\n📱 <b>Платформа:</b> {platform}\n🔑 <b>Ключ:</b> {key_text}\n🟢 <b>Статус:</b> {status}\n🔖 <b>Версия:</b> {version}\n\n⚙️ <b>Функции:</b>\n{features}\n"
    elif style == "Неон":
        text = f"💠 <b>NEON RELEASE</b> 💠\n\n🎮 <b>{game}</b>\n📜 <b>{script}</b>\n\n⚡ <b>{script_type}</b> | {platform}\n🔑 Ключ: <b>{key_text}</b>\n🟢 {status} | v{version}\n\n{features}\n"
    elif style == "Чистый минимал":
        text = f"<b>{script}</b>\n\n🎮 Игра: {game}\n🧩 Тип: {script_type}\n📱 Платформа: {platform}\n🔑 Ключ: {key_text}\n🟢 Статус: {status}\n\n{features}\n"
    elif style == "Технический":
        text = f"<b>/* ДАННЫЕ СКРИПТА */</b>\nИгра: {game}\nНазвание: {script}\nТип: {script_type}\nПлатформа: {platform}\nКлюч: {key_text}\nСтатус: {status}\nВерсия: {version}\n\nФункции:\n{features}\n"
    elif style == "Короткий":
        text = f"🎮 <b>{game}</b>\n📜 <b>{script}</b>\n🧩 {script_type} | {platform}\n🔑 Ключ: {key_text}\n⚙️ {features}\n"
    elif style == "Большой релиз":
        text = f"🚀🔥 <b>БОЛЬШОЙ РЕЛИЗ СКРИПТА</b> 🔥🚀\n\n🎮 Игра: <b>{game}</b>\n📜 Скрипт: <b>{script}</b>\n🧩 Тип: <b>{script_type}</b>\n📱 Платформа: <b>{platform}</b>\n🔑 Ключ: <b>{key_text}</b>\n🟢 Статус: <b>{status}</b>\n🔖 Версия: <b>{version}</b>\n\n⚙️ <b>Функции:</b>\n{features}\n"
    else:
        text = f"🌐 <b>GLOBAL 2.0</b>\n━━━━━━━━━━━━━━━━\n🎮 <b>{game}</b>\n📜 <b>{script}</b>\n🧩 <b>{script_type}</b>\n📱 <b>{platform}</b>\n🔑 Ключ: <b>{key_text}</b>\n🟢 Статус: <b>{status}</b>\n🔖 Версия: <b>{version}</b>\n\n⚙️ <b>Функции:</b>\n{features}\n"

    if description:
        text += f"\n📝 <b>Описание:</b>\n{description}\n"
    if instruction:
        text += f"\n📌 <b>Инструкция:</b>\n{instruction}\n"
    if note:
        text += f"\n🧾 <b>Заметка:</b> {note}\n"
    text += "\n📁 Lua-код прикреплён отдельным .txt файлом.\n"
    if tags:
        text += f"\n{safe_html(tags)}\n"
    if footer:
        text += f"\n🔗 {safe_html(footer)}"
    return text.strip()


def format_features(features: str, style: str) -> str:
    items = [safe_html(item.strip()) for item in clean(features).split(",") if item.strip()]
    if not items:
        return "Не указано"
    if style in {"Глобалка", "Тёмный премиум", "Неон"}:
        return "\n".join(f"◆ {item}" for item in items)
    if style == "Технический":
        return "\n".join(f"{index}. {item}" for index, item in enumerate(items, 1))
    if style == "Короткий":
        return ", ".join(items)
    return "\n".join(f"• {item}" for item in items)


def build_hashtags(data: dict[str, Any]) -> str:
    values = [data.get("game_name", ""), data.get("script_type", ""), data.get("platform", "")]
    values += [item.strip() for item in clean(data.get("tags", "")).split(",") if item.strip()]
    tags = []
    for value in values:
        slug = slugify(str(value), "")
        if slug:
            tags.append("#" + slug.replace("_", ""))
    return " ".join(dict.fromkeys(tags[:10]))


def make_code_file(data: dict[str, Any]) -> Path:
    ensure_dirs()
    data = normalize_data(data)
    game = slugify(data.get("game_name", "game"), "game")
    script = slugify(data.get("script_name", "script"), "script")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = CODE_DIR / f"{game}_{script}_{timestamp}.txt"
    header = (
        f"{PROJECT_NAME}\n"
        f"Версия бота: {VERSION}\n"
        f"Игра: {data.get('game_name', '')}\n"
        f"Скрипт: {data.get('script_name', '')}\n"
        f"Тип: {data.get('script_type', '')}\n"
        f"Платформа: {data.get('platform', '')}\n"
        f"Дата: {now_iso()}\n\n"
    )
    path.write_text(header + normalize_code(data.get("lua_code", "")) + "\n", encoding="utf-8")
    return path


async def save_script(data: dict[str, Any], user_id: str) -> int:
    data = normalize_data(data)
    h = code_hash(data.get("lua_code", ""))
    existing = await db_one("SELECT id FROM scripts WHERE code_hash = ? AND archived = 0", (h,))
    if existing:
        await db_run("UPDATE scripts SET use_count = use_count + 1, updated_at = ? WHERE id = ?", (now_iso(), existing["id"]))
        return int(existing["id"])
    async with open_db() as db:
        cursor = await db.execute(
            "INSERT INTO scripts (game_name, script_name, script_type, platform, key_required, status, version, features, tags, description, instruction, lua_code, code_hash, photo_id, style, created_by, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (data["game_name"], data["script_name"], data["script_type"], data["platform"], 1 if data["key_required"] else 0, data["status"], data["version"], data["features"], data["tags"], data["description"], data["instruction"], data["lua_code"], h, data["photo_id"], data["style"], user_id, now_iso(), now_iso()),
        )
        await db.commit()
        return int(cursor.lastrowid)


async def send_html_message(chat_id: str | int, text: str, markup: InlineKeyboardMarkup | None = None) -> Message:
    chunks = chunk_text(text, 3800)
    sent = None
    for index, chunk in enumerate(chunks):
        try:
            sent = await bot.send_message(chat_id=chat_id, text=chunk, reply_markup=markup if index == len(chunks) - 1 else None, parse_mode=ParseMode.HTML)
        except Exception:
            sent = await bot.send_message(chat_id=chat_id, text=re.sub(r"<[^>]+>", "", chunk), reply_markup=markup if index == len(chunks) - 1 else None)
    return sent


async def send_post_to_channel(data: dict[str, Any], actor: Any) -> dict[str, Any]:
    data = normalize_data(data)
    issues = validate_post_data(data)
    if issues:
        raise ValueError("; ".join(issues))
    channel_id = await get_setting("main_channel_id", MAIN_CHANNEL_ID)
    script_id = await save_script(data, str(getattr(actor, "id", actor)))
    post_text = await generate_post(data)
    code_file = make_code_file(data)
    status = "published"
    error = ""
    message_id = ""
    file_message_id = ""
    try:
        if data.get("photo_id"):
            try:
                if len(post_text) <= 1000:
                    msg = await bot.send_photo(chat_id=channel_id, photo=data["photo_id"], caption=post_text, parse_mode=ParseMode.HTML)
                else:
                    await bot.send_photo(chat_id=channel_id, photo=data["photo_id"])
                    msg = await send_html_message(channel_id, post_text)
            except Exception:
                msg = await send_html_message(channel_id, post_text)
        else:
            msg = await send_html_message(channel_id, post_text)
        file_msg = await bot.send_document(chat_id=channel_id, document=FSInputFile(code_file), caption="📁 Lua-код скрипта")
        message_id = str(msg.message_id)
        file_message_id = str(file_msg.message_id)
    except Exception as exc:
        status = "error"
        error = str(exc)
        raise
    finally:
        await db_run("UPDATE scripts SET publish_count = publish_count + 1, updated_at = ? WHERE id = ?", (now_iso(), script_id))
        await db_run("INSERT INTO posts (script_id, creator_id, game_name, script_name, telegram_message_id, file_message_id, code_file_path, status, error, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (script_id, str(getattr(actor, "id", actor)), data["game_name"], data["script_name"], message_id, file_message_id, str(code_file), status, error, now_iso()))
        await log_action("publish", actor, f"script_id={script_id}; status={status}; error={error}")
    return {"script_id": script_id, "message_id": message_id, "file_message_id": file_message_id, "code_file": str(code_file), "status": status}


async def save_draft(data: dict[str, Any], user_id: str) -> int:
    data = normalize_data(data)
    title = f"{data.get('game_name') or 'Без игры'} | {data.get('script_name') or 'Без названия'}"
    async with open_db() as db:
        cursor = await db.execute("INSERT INTO drafts (creator_id, title, data_json, created_at, updated_at) VALUES (?, ?, ?, ?, ?)", (user_id, title, json.dumps(data, ensure_ascii=False), now_iso(), now_iso()))
        await db.commit()
        return int(cursor.lastrowid)


async def add_to_queue(data: dict[str, Any], user_id: str, publish_at: datetime) -> int:
    async with open_db() as db:
        cursor = await db.execute("INSERT INTO queue (creator_id, data_json, publish_at, status, error, created_at, updated_at) VALUES (?, ?, ?, 'waiting', '', ?, ?)", (user_id, json.dumps(normalize_data(data), ensure_ascii=False), publish_at.isoformat(timespec="seconds"), now_iso(), now_iso()))
        await db.commit()
        return int(cursor.lastrowid)


async def show_home(chat_id: int, user: Any) -> None:
    project = await get_setting("project_name", PROJECT_NAME)
    text = (
        f"🚀 <b>{safe_html(project)}</b>\n"
        f"<b>{safe_html(VERSION)}</b>\n\n"
        "Рабочая панель для публикации Roblox Lua-скриптов в один канал.\n\n"
        "Главное:\n"
        "• публикация только в основной канал;\n"
        "• Lua-код всегда отдельным .txt файлом;\n"
        "• управление из Telegram и браузера;\n"
        "• база, черновики, очередь, оформление, backup, статистика."
    )
    photo_id = await get_setting("menu_photo_id", "")
    if photo_id:
        try:
            await bot.send_photo(chat_id=chat_id, photo=photo_id, caption=text[:1000], reply_markup=main_inline_keyboard(), parse_mode=ParseMode.HTML)
            await bot.send_message(chat_id, "⌨️ Основное меню:", reply_markup=main_reply_keyboard())
            return
        except Exception as exc:
            logger.warning("menu photo failed: %s", exc)
    await bot.send_message(chat_id, text, reply_markup=main_inline_keyboard(), parse_mode=ParseMode.HTML)
    await bot.send_message(chat_id, "⌨️ Основное меню:", reply_markup=main_reply_keyboard())


async def show_preview(message: Message, user_id: str, state: FSMContext) -> None:
    data = normalize_data(user_buffers.get(user_id, {}))
    issues = validate_post_data(data)
    duplicates = []
    if data.get("lua_code"):
        duplicates = await db_all("SELECT id, game_name, script_name FROM scripts WHERE code_hash = ? AND archived = 0 LIMIT 5", (code_hash(data["lua_code"]),))
    post = await generate_post(data)
    header = "👀 <b>Предпросмотр</b>\n\n"
    if issues:
        header += "⚠️ <b>Нужно исправить:</b>\n" + "\n".join(f"• {safe_html(item)}" for item in issues) + "\n\n"
    if duplicates:
        header += "🧹 <b>Похожие записи в базе:</b>\n" + "\n".join(f"• #{item['id']} {safe_html(item['game_name'])} | {safe_html(item['script_name'])}" for item in duplicates) + "\n\n"
    await send_html_message(message.chat.id, header + "━━━━━━━━━━━━\n" + post, preview_keyboard())
    await state.set_state(PostStates.preview)


async def edit_or_answer(callback: CallbackQuery, text: str, markup: InlineKeyboardMarkup | None = None) -> None:
    try:
        await callback.message.edit_text(text, reply_markup=markup, parse_mode=ParseMode.HTML)
    except Exception:
        await callback.message.answer(text, reply_markup=markup, parse_mode=ParseMode.HTML)


@router.message(Command("myid"))
async def cmd_myid(message: Message) -> None:
    await message.answer(f"🆔 Ваш Telegram ID:\n<code>{message.from_user.id}</code>", parse_mode=ParseMode.HTML)


@router.message(CommandStart())
@router.message(Command("menu"))
async def cmd_start(message: Message) -> None:
    await show_home(message.chat.id, message.from_user)
    await log_action("start", message.from_user)


@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext) -> None:
    user_buffers.pop(str(message.from_user.id), None)
    await state.clear()
    await message.answer("🛑 Действие отменено.", reply_markup=main_reply_keyboard())


@router.message(Command("test"))
async def cmd_test(message: Message) -> None:
    await send_test_report(message.chat.id, message.from_user)


@router.message(Command("app"))
async def cmd_app(message: Message) -> None:
    await send_app_info(message.chat.id)


@router.message(Command("clean_design"))
async def cmd_clean_design(message: Message, state: FSMContext) -> None:
    await state.set_state(DesignStates.clean_title)
    await message.answer("🧼 Введи название чистого оформления:")


@router.callback_query(F.data == "menu:home")
async def cb_home(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.clear()
    await show_home(callback.message.chat.id, callback.from_user)


@router.message(F.text.in_({"🔥 Создать пост", "⚡ Быстрый пост"}))
async def post_message_start(message: Message, state: FSMContext) -> None:
    mode = "quick" if message.text == "⚡ Быстрый пост" else "full"
    await start_post_flow(message, state, mode)


@router.callback_query(F.data.startswith("post:start:"))
async def cb_post_start(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    mode = callback.data.split(":")[-1]
    user_buffers[str(callback.from_user.id)] = normalize_data({"mode": mode})
    await state.set_state(PostStates.photo_choice)
    await edit_or_answer(callback, "🖼 <b>Нужно фото для поста?</b>", inline_rows([[("✅ Да", "photo:yes"), ("❌ Нет", "photo:no")], [("🛑 Отмена", "flow:cancel")]]))


async def start_post_flow(message: Message, state: FSMContext, mode: str) -> None:
    user_buffers[str(message.from_user.id)] = normalize_data({"mode": mode})
    await state.set_state(PostStates.photo_choice)
    await message.answer("🖼 <b>Нужно фото для поста?</b>", reply_markup=inline_rows([[("✅ Да", "photo:yes"), ("❌ Нет", "photo:no")], [("🛑 Отмена", "flow:cancel")]]), parse_mode=ParseMode.HTML)


@router.callback_query(F.data == "flow:cancel")
async def flow_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    user_buffers.pop(str(callback.from_user.id), None)
    await state.clear()
    await callback.answer("Отменено")
    await edit_or_answer(callback, "🛑 Действие отменено.", main_inline_keyboard())


@router.callback_query(F.data.startswith("photo:"), PostStates.photo_choice)
async def post_photo_choice(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.data.endswith("yes"):
        await state.set_state(PostStates.photo)
        await edit_or_answer(callback, "🖼 Отправь фото для поста.", inline_rows([[("🛑 Отмена", "flow:cancel")]]))
    else:
        user_buffers[str(callback.from_user.id)]["photo_id"] = ""
        await state.set_state(PostStates.game_name)
        await edit_or_answer(callback, "🎮 <b>Название игры:</b>", inline_rows([[("🛑 Отмена", "flow:cancel")]]))


@router.message(PostStates.photo, F.photo)
async def post_photo(message: Message, state: FSMContext) -> None:
    user_buffers[str(message.from_user.id)]["photo_id"] = message.photo[-1].file_id
    await state.set_state(PostStates.game_name)
    await message.answer("✅ Фото сохранено.\n\n🎮 <b>Название игры:</b>", parse_mode=ParseMode.HTML)


@router.message(PostStates.photo)
async def post_photo_invalid(message: Message) -> None:
    await message.answer("Отправь именно фото.")


@router.message(PostStates.game_name)
async def post_game(message: Message, state: FSMContext) -> None:
    user_buffers[str(message.from_user.id)]["game_name"] = clean(message.text)
    await state.set_state(PostStates.script_name)
    await message.answer("📜 <b>Название скрипта:</b>", parse_mode=ParseMode.HTML)


@router.message(PostStates.script_name)
async def post_script(message: Message, state: FSMContext) -> None:
    user_id = str(message.from_user.id)
    user_buffers[user_id]["script_name"] = clean(message.text)
    if user_buffers[user_id].get("mode") == "quick":
        await state.set_state(PostStates.features)
        await message.answer("⚙️ <b>Функции через запятую:</b>", parse_mode=ParseMode.HTML)
    else:
        await state.set_state(PostStates.script_type)
        await message.answer("🧩 <b>Тип скрипта:</b>", reply_markup=button_grid(SCRIPT_TYPES, "type", 3), parse_mode=ParseMode.HTML)


@router.callback_query(F.data.startswith("type:"), PostStates.script_type)
async def post_type(callback: CallbackQuery, state: FSMContext) -> None:
    user_buffers[str(callback.from_user.id)]["script_type"] = callback.data.split(":", 1)[1]
    await callback.answer()
    await state.set_state(PostStates.platform)
    await callback.message.answer("📱 <b>Платформа:</b>", reply_markup=button_grid(PLATFORMS, "platform", 2), parse_mode=ParseMode.HTML)


@router.callback_query(F.data.startswith("platform:"), PostStates.platform)
async def post_platform(callback: CallbackQuery, state: FSMContext) -> None:
    user_buffers[str(callback.from_user.id)]["platform"] = callback.data.split(":", 1)[1]
    await callback.answer()
    await state.set_state(PostStates.key_required)
    await callback.message.answer("🔑 <b>Нужен ключ?</b>", reply_markup=inline_rows([[("✅ Да", "key:yes"), ("❌ Нет", "key:no")], [("🛑 Отмена", "flow:cancel")]]), parse_mode=ParseMode.HTML)


@router.callback_query(F.data.startswith("key:"), PostStates.key_required)
async def post_key(callback: CallbackQuery, state: FSMContext) -> None:
    user_buffers[str(callback.from_user.id)]["key_required"] = callback.data.endswith("yes")
    await callback.answer()
    await state.set_state(PostStates.status)
    await callback.message.answer("🟢 <b>Статус:</b>", reply_markup=button_grid(SCRIPT_STATUSES, "status", 3), parse_mode=ParseMode.HTML)


@router.callback_query(F.data.startswith("status:"), PostStates.status)
async def post_status(callback: CallbackQuery, state: FSMContext) -> None:
    user_buffers[str(callback.from_user.id)]["status"] = callback.data.split(":", 1)[1]
    await callback.answer()
    await state.set_state(PostStates.version)
    await callback.message.answer("🔖 <b>Версия:</b>\nМожно написать 1.0 или нажать пропуск.", reply_markup=inline_rows([[("⏭ 1.0", "skip:version")], [("🛑 Отмена", "flow:cancel")]]), parse_mode=ParseMode.HTML)


@router.callback_query(F.data == "skip:version", PostStates.version)
async def skip_version(callback: CallbackQuery, state: FSMContext) -> None:
    user_buffers[str(callback.from_user.id)]["version"] = "1.0"
    await callback.answer()
    await state.set_state(PostStates.features)
    await callback.message.answer("⚙️ <b>Функции через запятую:</b>", parse_mode=ParseMode.HTML)


@router.message(PostStates.version)
async def post_version(message: Message, state: FSMContext) -> None:
    user_buffers[str(message.from_user.id)]["version"] = clean(message.text)[:30] or "1.0"
    await state.set_state(PostStates.features)
    await message.answer("⚙️ <b>Функции через запятую:</b>", parse_mode=ParseMode.HTML)


@router.message(PostStates.features)
async def post_features(message: Message, state: FSMContext) -> None:
    user_id = str(message.from_user.id)
    user_buffers[user_id]["features"] = clean(message.text)
    if user_buffers[user_id].get("mode") == "quick":
        await state.set_state(PostStates.code)
        await message.answer("💻 <b>Lua-код:</b>\nМожно текстом или .txt файлом.", parse_mode=ParseMode.HTML)
    else:
        await state.set_state(PostStates.tags)
        await message.answer("🏷 <b>Теги через запятую:</b>", reply_markup=inline_rows([[("⏭ Пропустить", "skip:tags")], [("🛑 Отмена", "flow:cancel")]]), parse_mode=ParseMode.HTML)


@router.callback_query(F.data == "skip:tags", PostStates.tags)
async def skip_tags(callback: CallbackQuery, state: FSMContext) -> None:
    user_buffers[str(callback.from_user.id)]["tags"] = ""
    await callback.answer()
    await state.set_state(PostStates.description)
    await callback.message.answer("📝 <b>Описание:</b>", reply_markup=inline_rows([[("⏭ Пропустить", "skip:description")], [("🛑 Отмена", "flow:cancel")]]), parse_mode=ParseMode.HTML)


@router.message(PostStates.tags)
async def post_tags(message: Message, state: FSMContext) -> None:
    user_buffers[str(message.from_user.id)]["tags"] = clean(message.text)
    await state.set_state(PostStates.description)
    await message.answer("📝 <b>Описание:</b>", reply_markup=inline_rows([[("⏭ Пропустить", "skip:description")], [("🛑 Отмена", "flow:cancel")]]), parse_mode=ParseMode.HTML)


@router.callback_query(F.data == "skip:description", PostStates.description)
async def skip_description(callback: CallbackQuery, state: FSMContext) -> None:
    user_buffers[str(callback.from_user.id)]["description"] = ""
    await callback.answer()
    await state.set_state(PostStates.instruction)
    await callback.message.answer("📌 <b>Инструкция:</b>", reply_markup=inline_rows([[("⏭ Пропустить", "skip:instruction")], [("🛑 Отмена", "flow:cancel")]]), parse_mode=ParseMode.HTML)


@router.message(PostStates.description)
async def post_description(message: Message, state: FSMContext) -> None:
    user_buffers[str(message.from_user.id)]["description"] = clean(message.text)
    await state.set_state(PostStates.instruction)
    await message.answer("📌 <b>Инструкция:</b>", reply_markup=inline_rows([[("⏭ Пропустить", "skip:instruction")], [("🛑 Отмена", "flow:cancel")]]), parse_mode=ParseMode.HTML)


@router.callback_query(F.data == "skip:instruction", PostStates.instruction)
async def skip_instruction(callback: CallbackQuery, state: FSMContext) -> None:
    user_buffers[str(callback.from_user.id)]["instruction"] = ""
    await callback.answer()
    await state.set_state(PostStates.code)
    await callback.message.answer("💻 <b>Lua-код:</b>\nМожно текстом или .txt файлом.", parse_mode=ParseMode.HTML)


@router.message(PostStates.instruction)
async def post_instruction(message: Message, state: FSMContext) -> None:
    user_buffers[str(message.from_user.id)]["instruction"] = clean(message.text)
    await state.set_state(PostStates.code)
    await message.answer("💻 <b>Lua-код:</b>\nМожно текстом или .txt файлом.", parse_mode=ParseMode.HTML)


async def read_document_text(message: Message) -> str:
    document = message.document
    if not document:
        return ""
    file_info = await bot.get_file(document.file_id)
    downloaded = await bot.download_file(file_info.file_path)
    raw = downloaded.read()
    for encoding in ["utf-8", "cp1251", "latin-1"]:
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="ignore")


@router.message(PostStates.code, F.document)
async def post_code_doc(message: Message, state: FSMContext) -> None:
    text = await read_document_text(message)
    if len(clean(text)) < 10:
        await message.answer("Файл пустой или код слишком короткий.")
        return
    user_buffers[str(message.from_user.id)]["lua_code"] = normalize_code(text)
    await after_code(message, state)


@router.message(PostStates.code)
async def post_code_text(message: Message, state: FSMContext) -> None:
    text = clean(message.text)
    if len(text) < 10:
        await message.answer("Код слишком короткий.")
        return
    user_buffers[str(message.from_user.id)]["lua_code"] = normalize_code(text)
    await after_code(message, state)


async def after_code(message: Message, state: FSMContext) -> None:
    user_id = str(message.from_user.id)
    if user_buffers[user_id].get("mode") == "quick":
        await state.set_state(PostStates.style)
        await message.answer("🎨 <b>Стиль:</b>", reply_markup=button_grid(POST_STYLES, "style", 2), parse_mode=ParseMode.HTML)
    else:
        await state.set_state(PostStates.note)
        await message.answer("🧾 <b>Заметка:</b>", reply_markup=inline_rows([[("⏭ Пропустить", "skip:note")], [("🛑 Отмена", "flow:cancel")]]), parse_mode=ParseMode.HTML)


@router.callback_query(F.data == "skip:note", PostStates.note)
async def skip_note(callback: CallbackQuery, state: FSMContext) -> None:
    user_buffers[str(callback.from_user.id)]["note"] = ""
    await callback.answer()
    await state.set_state(PostStates.style)
    await callback.message.answer("🎨 <b>Стиль:</b>", reply_markup=button_grid(POST_STYLES, "style", 2), parse_mode=ParseMode.HTML)


@router.message(PostStates.note)
async def post_note(message: Message, state: FSMContext) -> None:
    user_buffers[str(message.from_user.id)]["note"] = clean(message.text)
    await state.set_state(PostStates.style)
    await message.answer("🎨 <b>Стиль:</b>", reply_markup=button_grid(POST_STYLES, "style", 2), parse_mode=ParseMode.HTML)


@router.callback_query(F.data.startswith("style:"), PostStates.style)
async def post_style(callback: CallbackQuery, state: FSMContext) -> None:
    user_buffers[str(callback.from_user.id)]["style"] = callback.data.split(":", 1)[1]
    await callback.answer()
    await show_preview(callback.message, str(callback.from_user.id), state)


@router.callback_query(F.data == "preview:publish", PostStates.preview)
async def preview_publish(callback: CallbackQuery, state: FSMContext) -> None:
    user_id = str(callback.from_user.id)
    data = user_buffers.get(user_id)
    if not data:
        await callback.answer("Данные потеряны", show_alert=True)
        await state.clear()
        return
    try:
        result = await send_post_to_channel(data, callback.from_user)
        await state.clear()
        user_buffers.pop(user_id, None)
        await edit_or_answer(callback, f"✅ <b>Опубликовано.</b>\n\n🆔 Скрипт: <code>{result['script_id']}</code>\n📁 Файл: <code>{safe_html(Path(result['code_file']).name)}</code>", main_inline_keyboard())
    except Exception as exc:
        logger.exception("publish failed")
        await callback.message.answer(f"❌ Ошибка публикации:\n<code>{safe_html(exc)}</code>", parse_mode=ParseMode.HTML)


@router.callback_query(F.data == "preview:draft", PostStates.preview)
async def preview_draft(callback: CallbackQuery, state: FSMContext) -> None:
    user_id = str(callback.from_user.id)
    draft_id = await save_draft(user_buffers[user_id], user_id)
    await state.clear()
    await callback.answer("Черновик сохранён", show_alert=True)
    await edit_or_answer(callback, f"🧾 Черновик сохранён. ID: <code>{draft_id}</code>", main_inline_keyboard())


@router.callback_query(F.data.in_({"preview:queue10", "preview:queue60"}), PostStates.preview)
async def preview_queue(callback: CallbackQuery) -> None:
    user_id = str(callback.from_user.id)
    data = user_buffers.get(user_id)
    if not data:
        await callback.answer("Нет данных", show_alert=True)
        return
    minutes = 10 if callback.data.endswith("queue10") else 60
    queue_id = await add_to_queue(data, user_id, datetime.now() + timedelta(minutes=minutes))
    await callback.answer("Добавлено в очередь", show_alert=True)
    await callback.message.answer(f"🗓 Пост добавлен в очередь. ID: <code>{queue_id}</code>", parse_mode=ParseMode.HTML)


@router.callback_query(F.data.startswith("edit:"), PostStates.preview)
async def preview_edit(callback: CallbackQuery, state: FSMContext) -> None:
    field = callback.data.split(":", 1)[1]
    if field == "style":
        await state.set_state(PostStates.style)
        await callback.message.answer("🎨 Выбери новый стиль:", reply_markup=button_grid(POST_STYLES, "style", 2))
    elif field == "photo":
        await state.set_state(PostStates.edit_photo)
        await callback.message.answer("🖼 Отправь новое фото:")
    elif field == "lua_code":
        await state.update_data(edit_field=field)
        await state.set_state(PostStates.edit_code)
        await callback.message.answer("💻 Отправь новый код текстом или .txt:")
    else:
        await state.update_data(edit_field=field)
        await state.set_state(PostStates.edit_text)
        await callback.message.answer(f"✏️ Введи новое значение: <b>{safe_html(field)}</b>", parse_mode=ParseMode.HTML)
    await callback.answer()


@router.message(PostStates.edit_text)
async def edit_text_value(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    field = data.get("edit_field")
    if field:
        user_buffers[str(message.from_user.id)][field] = clean(message.text)
    await show_preview(message, str(message.from_user.id), state)


@router.message(PostStates.edit_code, F.document)
async def edit_code_doc(message: Message, state: FSMContext) -> None:
    text = await read_document_text(message)
    user_buffers[str(message.from_user.id)]["lua_code"] = normalize_code(text)
    await show_preview(message, str(message.from_user.id), state)


@router.message(PostStates.edit_code)
async def edit_code_text(message: Message, state: FSMContext) -> None:
    user_buffers[str(message.from_user.id)]["lua_code"] = normalize_code(message.text or "")
    await show_preview(message, str(message.from_user.id), state)


@router.message(PostStates.edit_photo, F.photo)
async def edit_photo_value(message: Message, state: FSMContext) -> None:
    user_buffers[str(message.from_user.id)]["photo_id"] = message.photo[-1].file_id
    await show_preview(message, str(message.from_user.id), state)


@router.message(F.text == "📚 База")
async def msg_db(message: Message) -> None:
    await message.answer("📚 <b>База скриптов</b>", reply_markup=db_keyboard(), parse_mode=ParseMode.HTML)


@router.callback_query(F.data == "db:menu")
async def cb_db(callback: CallbackQuery) -> None:
    await edit_or_answer(callback, "📚 <b>База скриптов</b>", db_keyboard())


async def scripts_list_text(page: int, mode: str, user_id: str) -> tuple[str, InlineKeyboardMarkup]:
    limit = 8
    offset = max(0, page) * limit
    if mode == "top":
        rows = await db_all("SELECT * FROM scripts WHERE archived = 0 ORDER BY publish_count DESC, use_count DESC, id DESC LIMIT ? OFFSET ?", (limit, offset))
        title = "🏆 <b>Топ скриптов</b>"
    elif mode == "favorites":
        rows = await db_all("SELECT s.* FROM scripts s JOIN favorites f ON s.id = f.script_id WHERE f.user_id = ? AND s.archived = 0 ORDER BY f.created_at DESC LIMIT ? OFFSET ?", (user_id, limit, offset))
        title = "⭐ <b>Избранное</b>"
    elif mode == "global":
        rows = await db_all("SELECT * FROM scripts WHERE archived = 0 AND (script_type LIKE '%Глоб%' OR script_type LIKE '%Универс%' OR script_type LIKE '%Universal%') ORDER BY id DESC LIMIT ? OFFSET ?", (limit, offset))
        title = "🌐 <b>Глобалки</b>"
    else:
        rows = await db_all("SELECT * FROM scripts WHERE archived = 0 ORDER BY id DESC LIMIT ? OFFSET ?", (limit, offset))
        title = "📋 <b>Все скрипты</b>"
    text = title + "\n\n"
    builder = InlineKeyboardBuilder()
    if not rows:
        text += "Пусто."
    for item in rows:
        text += f"#{item['id']} | <b>{safe_html(item['game_name'])}</b> | {safe_html(item['script_name'])}\n🧩 {safe_html(item['script_type'])} | 🚀 {item['publish_count']} | 👁 {item['use_count']}\n\n"
        builder.row(InlineKeyboardButton(text=f"#{item['id']} {item['script_name']}"[:64], callback_data=f"script:view:{item['id']}"))
    builder.row(InlineKeyboardButton(text="⬅️", callback_data=f"db:{mode}:{max(0, page - 1)}"), InlineKeyboardButton(text="➡️", callback_data=f"db:{mode}:{page + 1}"))
    builder.row(InlineKeyboardButton(text="◀️ База", callback_data="db:menu"))
    return text, builder.as_markup()


@router.callback_query(F.data.startswith("db:list:"))
async def cb_db_list(callback: CallbackQuery) -> None:
    page = int(callback.data.split(":")[-1])
    text, markup = await scripts_list_text(page, "list", str(callback.from_user.id))
    await edit_or_answer(callback, text, markup)


@router.callback_query(F.data.startswith("db:top:"))
async def cb_db_top(callback: CallbackQuery) -> None:
    page = int(callback.data.split(":")[-1])
    text, markup = await scripts_list_text(page, "top", str(callback.from_user.id))
    await edit_or_answer(callback, text, markup)


@router.callback_query(F.data.startswith("db:favorites:"))
async def cb_db_favorites(callback: CallbackQuery) -> None:
    page = int(callback.data.split(":")[-1])
    text, markup = await scripts_list_text(page, "favorites", str(callback.from_user.id))
    await edit_or_answer(callback, text, markup)


@router.callback_query(F.data.startswith("db:global:"))
async def cb_db_global(callback: CallbackQuery) -> None:
    page = int(callback.data.split(":")[-1])
    text, markup = await scripts_list_text(page, "global", str(callback.from_user.id))
    await edit_or_answer(callback, text, markup)


@router.callback_query(F.data == "db:search")
async def cb_db_search(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(SearchStates.scripts)
    await edit_or_answer(callback, "🔍 Введи запрос по базе:", inline_rows([[("◀️ База", "db:menu")]]))


@router.message(SearchStates.scripts)
async def msg_db_search(message: Message, state: FSMContext) -> None:
    query = clean(message.text)
    pattern = f"%{query}%"
    rows = await db_all("SELECT * FROM scripts WHERE archived = 0 AND (game_name LIKE ? OR script_name LIKE ? OR script_type LIKE ? OR tags LIKE ? OR features LIKE ?) ORDER BY id DESC LIMIT 20", (pattern, pattern, pattern, pattern, pattern))
    text = f"🔍 <b>Поиск:</b> {safe_html(query)}\n\n"
    builder = InlineKeyboardBuilder()
    if not rows:
        text += "Ничего не найдено."
    for item in rows:
        text += f"#{item['id']} | <b>{safe_html(item['game_name'])}</b> | {safe_html(item['script_name'])}\n"
        builder.row(InlineKeyboardButton(text=f"#{item['id']} {item['script_name']}"[:64], callback_data=f"script:view:{item['id']}"))
    builder.row(InlineKeyboardButton(text="◀️ База", callback_data="db:menu"))
    await state.clear()
    await message.answer(text, reply_markup=builder.as_markup(), parse_mode=ParseMode.HTML)


@router.callback_query(F.data.startswith("script:view:"))
async def cb_script_view(callback: CallbackQuery) -> None:
    script_id = int(callback.data.split(":")[-1])
    item = await db_one("SELECT * FROM scripts WHERE id = ?", (script_id,))
    if not item:
        await callback.answer("Не найдено", show_alert=True)
        return
    await db_run("UPDATE scripts SET use_count = use_count + 1 WHERE id = ?", (script_id,))
    text = (
        f"📜 <b>Скрипт #{item['id']}</b>\n\n"
        f"🎮 Игра: <b>{safe_html(item['game_name'])}</b>\n"
        f"📜 Название: <b>{safe_html(item['script_name'])}</b>\n"
        f"🧩 Тип: {safe_html(item['script_type'])}\n"
        f"📱 Платформа: {safe_html(item['platform'])}\n"
        f"🔑 Ключ: {'Да' if item['key_required'] else 'Нет'}\n"
        f"🟢 Статус: {safe_html(item['status'])}\n"
        f"🔖 Версия: {safe_html(item['version'])}\n"
        f"🚀 Публикаций: {item['publish_count']}\n"
        f"👁 Использований: {item['use_count']}\n\n"
        f"⚙️ {safe_html(item['features'])}"
    )
    await edit_or_answer(callback, text, inline_rows([
        [("🚀 Опубликовать", f"script:publish:{script_id}"), ("⭐ В избранное", f"script:fav:{script_id}")],
        [("📁 Скачать код", f"script:file:{script_id}"), ("🗑 В архив", f"script:archive:{script_id}")],
        [("◀️ База", "db:menu")],
    ]))


@router.callback_query(F.data.startswith("script:fav:"))
async def cb_script_fav(callback: CallbackQuery) -> None:
    script_id = int(callback.data.split(":")[-1])
    await db_run("INSERT OR REPLACE INTO favorites (user_id, script_id, created_at) VALUES (?, ?, ?)", (str(callback.from_user.id), script_id, now_iso()))
    await callback.answer("Добавлено в избранное", show_alert=True)


@router.callback_query(F.data.startswith("script:file:"))
async def cb_script_file(callback: CallbackQuery) -> None:
    script_id = int(callback.data.split(":")[-1])
    item = await db_one("SELECT * FROM scripts WHERE id = ?", (script_id,))
    if not item:
        await callback.answer("Не найдено", show_alert=True)
        return
    path = make_code_file(dict(item))
    await callback.message.answer_document(document=FSInputFile(path), caption=f"📁 Код скрипта #{script_id}")
    await callback.answer()


@router.callback_query(F.data.startswith("script:publish:"))
async def cb_script_publish(callback: CallbackQuery) -> None:
    script_id = int(callback.data.split(":")[-1])
    item = await db_one("SELECT * FROM scripts WHERE id = ?", (script_id,))
    if not item:
        await callback.answer("Не найдено", show_alert=True)
        return
    try:
        result = await send_post_to_channel(dict(item), callback.from_user)
        await callback.answer("Опубликовано", show_alert=True)
        await callback.message.answer(f"✅ Опубликовано из базы. Script ID: <code>{result['script_id']}</code>", parse_mode=ParseMode.HTML)
    except Exception as exc:
        await callback.message.answer(f"❌ Ошибка публикации:\n<code>{safe_html(exc)}</code>", parse_mode=ParseMode.HTML)


@router.callback_query(F.data.startswith("script:archive:"))
async def cb_script_archive(callback: CallbackQuery) -> None:
    script_id = int(callback.data.split(":")[-1])
    await db_run("UPDATE scripts SET archived = 1, updated_at = ? WHERE id = ?", (now_iso(), script_id))
    await log_action("script_archive", callback.from_user, f"script_id={script_id}")
    await callback.answer("Убрано в архив", show_alert=True)
    await cb_db(callback)


@router.message(F.text == "🌐 Глобалки")
async def msg_global(message: Message) -> None:
    await message.answer("🌐 <b>Глобалки</b>\n\nГлобальные и универсальные скрипты из базы.", reply_markup=inline_rows([[("📋 Смотреть", "db:global:0"), ("➕ Создать", "post:start:full")], [("◀️ Меню", "menu:home")]]), parse_mode=ParseMode.HTML)


@router.callback_query(F.data == "global:menu")
async def cb_global(callback: CallbackQuery) -> None:
    await edit_or_answer(callback, "🌐 <b>Глобалки</b>\n\nГлобальные и универсальные скрипты из базы.", inline_rows([[("📋 Смотреть", "db:global:0"), ("➕ Создать", "post:start:full")], [("◀️ Меню", "menu:home")]]))


@router.message(F.text == "🧾 Черновики")
async def msg_drafts(message: Message) -> None:
    await show_drafts(message.chat.id, str(message.from_user.id), 0)


@router.callback_query(F.data.startswith("drafts:list:"))
async def cb_drafts(callback: CallbackQuery) -> None:
    page = int(callback.data.split(":")[-1])
    await show_drafts(callback.message.chat.id, str(callback.from_user.id), page)
    await callback.answer()


async def show_drafts(chat_id: int, user_id: str, page: int) -> None:
    rows = await db_all("SELECT * FROM drafts WHERE creator_id = ? ORDER BY updated_at DESC LIMIT 10 OFFSET ?", (user_id, page * 10))
    text = "🧾 <b>Черновики</b>\n\n"
    builder = InlineKeyboardBuilder()
    if not rows:
        text += "Пусто."
    for row in rows:
        text += f"#{row['id']} | {safe_html(row['title'])}\n{safe_html(row['updated_at'])}\n\n"
        builder.row(InlineKeyboardButton(text=f"Открыть #{row['id']}", callback_data=f"draft:open:{row['id']}"))
    builder.row(InlineKeyboardButton(text="◀️ Меню", callback_data="menu:home"))
    await bot.send_message(chat_id, text, reply_markup=builder.as_markup(), parse_mode=ParseMode.HTML)


@router.callback_query(F.data.startswith("draft:open:"))
async def cb_draft_open(callback: CallbackQuery, state: FSMContext) -> None:
    draft_id = int(callback.data.split(":")[-1])
    row = await db_one("SELECT * FROM drafts WHERE id = ? AND creator_id = ?", (draft_id, str(callback.from_user.id)))
    if not row:
        await callback.answer("Черновик не найден", show_alert=True)
        return
    user_buffers[str(callback.from_user.id)] = normalize_data(json.loads(row["data_json"]))
    await callback.answer("Черновик открыт")
    await show_preview(callback.message, str(callback.from_user.id), state)


@router.message(F.text == "🗓 Очередь")
async def msg_queue(message: Message) -> None:
    await message.answer("🗓 <b>Очередь публикаций</b>", reply_markup=queue_keyboard(), parse_mode=ParseMode.HTML)


@router.callback_query(F.data == "queue:menu")
async def cb_queue_menu(callback: CallbackQuery) -> None:
    await edit_or_answer(callback, "🗓 <b>Очередь публикаций</b>", queue_keyboard())


@router.callback_query(F.data == "queue:list")
async def cb_queue_list(callback: CallbackQuery) -> None:
    rows = await db_all("SELECT * FROM queue ORDER BY publish_at ASC LIMIT 30")
    text = "🗓 <b>Очередь</b>\n\n"
    if not rows:
        text += "Пусто."
    for row in rows:
        data = json.loads(row["data_json"])
        text += f"#{row['id']} | {safe_html(row['status'])} | {safe_html(row['publish_at'])}\n{safe_html(data.get('game_name'))} | {safe_html(data.get('script_name'))}\n"
        if row.get("error"):
            text += f"Ошибка: {safe_html(row['error'])}\n"
        text += "\n"
    await edit_or_answer(callback, text, queue_keyboard())


@router.callback_query(F.data == "queue:next")
async def cb_queue_next(callback: CallbackQuery) -> None:
    row = await db_one("SELECT * FROM queue WHERE status = 'waiting' ORDER BY publish_at ASC LIMIT 1")
    if not row:
        await callback.answer("Очередь пуста", show_alert=True)
        return
    fake_user = type("WebActor", (), {"id": int(row["creator_id"]) if str(row["creator_id"]).isdigit() else OWNER_IDS[0], "username": "queue", "first_name": "Queue"})()
    try:
        await send_post_to_channel(json.loads(row["data_json"]), fake_user)
        await db_run("UPDATE queue SET status = 'published', updated_at = ? WHERE id = ?", (now_iso(), row["id"]))
        await callback.answer("Следующий пост опубликован", show_alert=True)
    except Exception as exc:
        await db_run("UPDATE queue SET status = 'error', error = ?, updated_at = ? WHERE id = ?", (str(exc), now_iso(), row["id"]))
        await callback.answer("Ошибка публикации", show_alert=True)


@router.callback_query(F.data == "queue:clear")
async def cb_queue_clear(callback: CallbackQuery) -> None:
    await db_run("DELETE FROM queue WHERE status = 'waiting'")
    await callback.answer("Ожидающая очередь очищена", show_alert=True)
    await cb_queue_menu(callback)


@router.message(F.text == "🎨 Оформление")
async def msg_design(message: Message) -> None:
    await message.answer("🎨 <b>Оформление</b>", reply_markup=design_keyboard(), parse_mode=ParseMode.HTML)


@router.callback_query(F.data == "design:menu")
async def cb_design(callback: CallbackQuery) -> None:
    await edit_or_answer(callback, "🎨 <b>Оформление</b>", design_keyboard())


@router.callback_query(F.data == "design:clean")
async def cb_design_clean(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(DesignStates.clean_title)
    await edit_or_answer(callback, "🧼 Введи название чистого оформления:", design_keyboard())


@router.message(DesignStates.clean_title)
async def design_clean_title(message: Message, state: FSMContext) -> None:
    await state.update_data(clean_title=clean(message.text) or "Чистое оформление")
    await state.set_state(DesignStates.clean_text)
    await message.answer("Теперь отправь оформление целиком. Я уберу ссылки, каналы, рекламу и оставлю дизайн.")


@router.message(DesignStates.clean_text)
async def design_clean_text(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    title = data.get("clean_title", "Чистое оформление")
    cleaned = clean_design_text(message.text or "")
    if not cleaned:
        await message.answer("После очистки ничего не осталось. Отправь другое оформление.")
        return
    async with open_db() as db:
        cursor = await db.execute("INSERT INTO templates (title, body, source, created_by, created_at) VALUES (?, ?, 'clean_design', ?, ?)", (title, cleaned, str(message.from_user.id), now_iso()))
        await db.commit()
        template_id = int(cursor.lastrowid)
    await state.clear()
    await message.answer(f"✅ Оформление очищено и сохранено как шаблон #{template_id}.\n\n<pre>{safe_html(cleaned[:2500])}</pre>", reply_markup=design_keyboard(), parse_mode=ParseMode.HTML)


@router.callback_query(F.data.startswith("design:templates:"))
async def cb_templates(callback: CallbackQuery) -> None:
    page = int(callback.data.split(":")[-1])
    rows = await db_all("SELECT * FROM templates ORDER BY id DESC LIMIT 10 OFFSET ?", (page * 10,))
    text = "📋 <b>Шаблоны</b>\n\n"
    builder = InlineKeyboardBuilder()
    if not rows:
        text += "Пусто."
    for row in rows:
        text += f"#{row['id']} | {safe_html(row['title'])}\n"
        builder.row(InlineKeyboardButton(text=f"Открыть #{row['id']}", callback_data=f"template:view:{row['id']}"))
    builder.row(InlineKeyboardButton(text="◀️ Оформление", callback_data="design:menu"))
    await edit_or_answer(callback, text, builder.as_markup())


@router.callback_query(F.data.startswith("template:view:"))
async def cb_template_view(callback: CallbackQuery) -> None:
    template_id = int(callback.data.split(":")[-1])
    row = await db_one("SELECT * FROM templates WHERE id = ?", (template_id,))
    if not row:
        await callback.answer("Не найдено", show_alert=True)
        return
    await edit_or_answer(callback, f"📋 <b>{safe_html(row['title'])}</b>\n\n<pre>{safe_html(row['body'][:3000])}</pre>", design_keyboard())


@router.callback_query(F.data == "design:new_template")
async def cb_template_new(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(DesignStates.template_title)
    await edit_or_answer(callback, "➕ Название нового шаблона:", design_keyboard())


@router.message(DesignStates.template_title)
async def template_new_title(message: Message, state: FSMContext) -> None:
    await state.update_data(template_title=clean(message.text) or "Шаблон")
    await state.set_state(DesignStates.template_body)
    await message.answer("Текст шаблона:")


@router.message(DesignStates.template_body)
async def template_new_body(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    title = data.get("template_title", "Шаблон")
    body = clean(message.text)
    await db_run("INSERT INTO templates (title, body, source, created_by, created_at) VALUES (?, ?, 'manual', ?, ?)", (title, body, str(message.from_user.id), now_iso()))
    await state.clear()
    await message.answer("✅ Шаблон сохранён.", reply_markup=design_keyboard(), parse_mode=ParseMode.HTML)


@router.callback_query(F.data == "design:styles")
async def cb_design_styles(callback: CallbackQuery) -> None:
    await edit_or_answer(callback, "🎨 <b>Стили постов</b>\n\n" + "\n".join(f"• {safe_html(item)}" for item in POST_STYLES), design_keyboard())


@router.message(F.text == "🖼 Медиа")
async def msg_media(message: Message, state: FSMContext) -> None:
    await state.set_state(MediaStates.photo)
    await message.answer("🖼 Отправь фото для медиа-библиотеки или баннера меню.")


@router.message(MediaStates.photo, F.photo)
async def media_photo(message: Message, state: FSMContext) -> None:
    await state.update_data(media_photo_id=message.photo[-1].file_id)
    await state.set_state(MediaStates.title)
    await message.answer("Название фото:")


@router.message(MediaStates.title)
async def media_title(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    await db_run("INSERT INTO media (file_id, title, created_by, created_at) VALUES (?, ?, ?, ?)", (data["media_photo_id"], clean(message.text) or "Фото", str(message.from_user.id), now_iso()))
    await state.clear()
    await message.answer("✅ Фото сохранено.", reply_markup=main_reply_keyboard())


@router.message(F.text == "📊 Статистика")
@router.callback_query(F.data == "stats:show")
async def stats_any(event: Message | CallbackQuery) -> None:
    chat_id = event.chat.id if isinstance(event, Message) else event.message.chat.id
    await send_stats(chat_id)
    if isinstance(event, CallbackQuery):
        await event.answer()


async def send_stats(chat_id: int) -> None:
    keys = {
        "scripts": "SELECT COUNT(*) as c FROM scripts WHERE archived = 0",
        "posts": "SELECT COUNT(*) as c FROM posts",
        "drafts": "SELECT COUNT(*) as c FROM drafts",
        "queue": "SELECT COUNT(*) as c FROM queue WHERE status = 'waiting'",
        "templates": "SELECT COUNT(*) as c FROM templates",
        "media": "SELECT COUNT(*) as c FROM media",
    }
    values = {}
    for key, query in keys.items():
        row = await db_one(query)
        values[key] = row["c"] if row else 0
    text = (
        "📊 <b>Статистика</b>\n\n"
        f"📚 Скриптов: <b>{values['scripts']}</b>\n"
        f"🚀 Публикаций: <b>{values['posts']}</b>\n"
        f"🧾 Черновиков: <b>{values['drafts']}</b>\n"
        f"🗓 В очереди: <b>{values['queue']}</b>\n"
        f"📋 Шаблонов: <b>{values['templates']}</b>\n"
        f"🖼 Медиа: <b>{values['media']}</b>"
    )
    await bot.send_message(chat_id, text, reply_markup=main_inline_keyboard(), parse_mode=ParseMode.HTML)


@router.message(F.text == "⚙️ Настройки")
async def msg_settings(message: Message) -> None:
    await message.answer("⚙️ <b>Настройки</b>", reply_markup=settings_keyboard(), parse_mode=ParseMode.HTML)


@router.callback_query(F.data == "settings:menu")
async def cb_settings(callback: CallbackQuery) -> None:
    await edit_or_answer(callback, "⚙️ <b>Настройки</b>", settings_keyboard())


@router.callback_query(F.data.startswith("settings:edit:"))
async def cb_settings_edit(callback: CallbackQuery, state: FSMContext) -> None:
    key = callback.data.split(":", 2)[2]
    current = await get_setting(key, "")
    await state.update_data(setting_key=key)
    await state.set_state(SettingsStates.value)
    await edit_or_answer(callback, f"⚙️ <b>{safe_html(key)}</b>\nТекущее значение:\n<code>{safe_html(current)}</code>\n\nВведи новое значение:", settings_keyboard())


@router.message(SettingsStates.value)
async def settings_value(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    key = data.get("setting_key")
    value = clean(message.text)
    if key:
        await set_setting(key, value)
        await log_action("setting_update", message.from_user, f"{key}={value}")
    await state.clear()
    await message.answer("✅ Настройка сохранена.", reply_markup=main_reply_keyboard())


@router.callback_query(F.data == "settings:menu_photo")
async def cb_settings_menu_photo(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(SettingsStates.menu_photo)
    await edit_or_answer(callback, "🖼 Отправь новое фото главного меню:", settings_keyboard())


@router.message(SettingsStates.menu_photo, F.photo)
async def settings_menu_photo(message: Message, state: FSMContext) -> None:
    await set_setting("menu_photo_id", message.photo[-1].file_id)
    await state.clear()
    await message.answer("✅ Фото меню установлено.", reply_markup=main_reply_keyboard())


@router.callback_query(F.data == "backup:create")
async def cb_backup(callback: CallbackQuery) -> None:
    path = await create_backup()
    await callback.message.answer_document(document=FSInputFile(path), caption="💾 Backup базы")
    await callback.answer()


@router.callback_query(F.data == "export:scripts")
async def cb_export_scripts(callback: CallbackQuery) -> None:
    path = await export_scripts_csv()
    await callback.message.answer_document(document=FSInputFile(path), caption="📤 Export скриптов CSV")
    await callback.answer()


@router.callback_query(F.data == "logs:show")
async def cb_logs(callback: CallbackQuery) -> None:
    rows = await db_all("SELECT * FROM logs ORDER BY id DESC LIMIT 40")
    text = "📜 <b>Логи</b>\n\n"
    if not rows:
        text += "Пусто."
    for row in rows:
        text += f"[{safe_html(row['created_at'])}] {safe_html(row['action'])} | {safe_html(row['actor_name'])} | {safe_html(row.get('details') or '')}\n"
    await edit_or_answer(callback, text[:3900], settings_keyboard())


@router.callback_query(F.data == "test:run")
async def cb_test(callback: CallbackQuery) -> None:
    await send_test_report(callback.message.chat.id, callback.from_user)
    await callback.answer()


@router.message(F.text == "🌍 Приложение")
async def msg_webapp(message: Message) -> None:
    await send_app_info(message.chat.id)


@router.callback_query(F.data == "webapp:info")
async def cb_webapp(callback: CallbackQuery) -> None:
    await send_app_info(callback.message.chat.id)
    await callback.answer()


async def send_app_info(chat_id: int) -> None:
    public_url = await get_setting("web_public_url", "")
    local_url = f"http://{WEB_HOST}:{WEB_PORT}"
    url = public_url or local_url
    secret = await get_setting("web_app_secret", WEB_APP_SECRET)
    text = (
        "🌍 <b>Браузерное приложение</b>\n\n"
        f"Локальная ссылка: <code>{safe_html(local_url)}</code>\n"
        f"Ключ входа: <code>{safe_html(secret)}</code>\n\n"
        "В приложении можно создавать скрипты, публиковать их в канал, работать с базой, черновиками, очередью, оформлением, настройками и backup."
    )
    await bot.send_message(chat_id, text, reply_markup=webapp_button(url), parse_mode=ParseMode.HTML)


async def send_test_report(chat_id: int, user: Any) -> None:
    lines = [f"🧪 <b>Диагностика {safe_html(VERSION)}</b>", ""]
    try:
        me = await bot.get_me()
        lines.append(f"✅ Бот: @{safe_html(me.username)} | <code>{me.id}</code>")
    except Exception as exc:
        lines.append(f"❌ Бот: {safe_html(exc)}")
    try:
        row = await db_one("SELECT COUNT(*) as c FROM scripts")
        lines.append(f"✅ База: OK | Скриптов: {row['c'] if row else 0}")
    except Exception as exc:
        lines.append(f"❌ База: {safe_html(exc)}")
    try:
        channel_id = await get_setting("main_channel_id", MAIN_CHANNEL_ID)
        chat = await bot.get_chat(channel_id)
        lines.append(f"✅ Канал: {safe_html(channel_id)} | {safe_html(chat.title or chat.username or chat.id)}")
    except Exception as exc:
        lines.append(f"❌ Канал: {safe_html(exc)}")
    lines.append(f"✅ Папки: {STORAGE_DIR.exists()} | codes={CODE_DIR.exists()} | backups={BACKUP_DIR.exists()}")
    lines.append(f"✅ Приложение: http://{WEB_HOST}:{WEB_PORT}")
    await bot.send_message(chat_id, "\n".join(lines), reply_markup=main_inline_keyboard(), parse_mode=ParseMode.HTML)


async def create_backup() -> Path:
    ensure_dirs()
    path = BACKUP_DIR / f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
    if DATABASE_PATH.exists():
        shutil.copy2(DATABASE_PATH, path)
    else:
        sqlite3.connect(path).close()
    return path


async def export_scripts_csv() -> Path:
    ensure_dirs()
    path = EXPORT_DIR / f"scripts_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    rows = await db_all("SELECT id, game_name, script_name, script_type, platform, key_required, status, version, features, tags, created_at, publish_count, use_count FROM scripts ORDER BY id DESC")
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=["id", "game_name", "script_name", "script_type", "platform", "key_required", "status", "version", "features", "tags", "created_at", "publish_count", "use_count"])
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    return path


async def scheduler_loop() -> None:
    while True:
        try:
            rows = await db_all("SELECT * FROM queue WHERE status = 'waiting' AND publish_at <= ? ORDER BY publish_at ASC LIMIT 3", (now_iso(),))
            for row in rows:
                actor = type("QueueActor", (), {"id": int(row["creator_id"]) if str(row["creator_id"]).isdigit() else OWNER_IDS[0], "username": "queue", "first_name": "Queue"})()
                try:
                    await db_run("UPDATE queue SET status = 'processing', updated_at = ? WHERE id = ?", (now_iso(), row["id"]))
                    await send_post_to_channel(json.loads(row["data_json"]), actor)
                    await db_run("UPDATE queue SET status = 'published', updated_at = ? WHERE id = ?", (now_iso(), row["id"]))
                except Exception as exc:
                    await db_run("UPDATE queue SET status = 'error', error = ?, updated_at = ? WHERE id = ?", (str(exc), now_iso(), row["id"]))
            await asyncio.sleep(20)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.exception("scheduler failed: %s", exc)
            await asyncio.sleep(30)


async def api_auth(request: web.Request) -> bool:
    expected = await get_setting("web_app_secret", WEB_APP_SECRET)
    provided = request.headers.get("X-App-Key") or request.query.get("key") or ""
    return bool(expected) and provided == expected


def json_response(data: Any, status: int = 200) -> web.Response:
    return web.json_response(data, status=status, dumps=lambda value: json.dumps(value, ensure_ascii=False))


async def require_api(request: web.Request) -> web.Response | None:
    if await api_auth(request):
        return None
    return json_response({"ok": False, "error": "Неверный ключ приложения"}, 401)


APP_HTML = r'''<!doctype html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>GLOBAL 2.0</title>
<style>
:root{--bg:#0b0f1a;--card:#121a2a;--card2:#172238;--line:#263553;--text:#e8eefc;--muted:#95a3bd;--accent:#8b5cf6;--accent2:#06b6d4;--bad:#ef4444;--good:#22c55e;--warn:#f59e0b}*{box-sizing:border-box}body{margin:0;font-family:Inter,Arial,sans-serif;background:linear-gradient(135deg,#090d16,#111827 45%,#0f172a);color:var(--text)}header{position:sticky;top:0;z-index:2;background:rgba(11,15,26,.92);backdrop-filter:blur(12px);border-bottom:1px solid var(--line);padding:14px 18px}.brand{display:flex;gap:12px;align-items:center;justify-content:space-between;flex-wrap:wrap}.brand h1{font-size:18px;margin:0}.brand p{margin:4px 0 0;color:var(--muted);font-size:13px}.wrap{max-width:1220px;margin:0 auto;padding:18px}.tabs{display:flex;gap:8px;flex-wrap:wrap;margin:14px 0}.tab{border:1px solid var(--line);background:var(--card);color:var(--text);border-radius:12px;padding:10px 12px;cursor:pointer}.tab.active{background:linear-gradient(135deg,var(--accent),var(--accent2));border-color:transparent}.grid{display:grid;grid-template-columns:repeat(12,1fr);gap:14px}.card{grid-column:span 12;background:rgba(18,26,42,.92);border:1px solid var(--line);border-radius:18px;padding:16px;box-shadow:0 18px 50px rgba(0,0,0,.22)}@media(min-width:900px){.half{grid-column:span 6}.third{grid-column:span 4}.wide{grid-column:span 8}}h2,h3{margin:0 0 12px}.muted{color:var(--muted)}input,textarea,select{width:100%;background:#0d1422;border:1px solid var(--line);border-radius:12px;color:var(--text);padding:11px;margin:6px 0 10px;outline:none}textarea{min-height:120px;resize:vertical}.btn{border:0;border-radius:12px;background:linear-gradient(135deg,var(--accent),var(--accent2));color:white;padding:11px 14px;cursor:pointer;font-weight:700;margin:4px}.btn.secondary{background:#1f2937}.btn.bad{background:var(--bad)}.btn.good{background:var(--good)}.btn.warn{background:var(--warn)}.list{display:grid;gap:10px}.item{background:#0d1422;border:1px solid var(--line);border-radius:14px;padding:12px}.item b{color:white}.pill{display:inline-block;padding:4px 8px;border-radius:999px;background:#1e293b;color:#cbd5e1;font-size:12px;margin:2px}.hidden{display:none}.status{white-space:pre-wrap;background:#08101f;border:1px solid var(--line);border-radius:12px;padding:12px;color:#dbeafe;max-height:360px;overflow:auto}.topline{display:flex;gap:8px;align-items:center;flex-wrap:wrap}.grow{flex:1}.danger{color:#fecaca}.ok{color:#bbf7d0}.small{font-size:12px}.footer{margin:30px 0;color:var(--muted);text-align:center}
</style>
</head>
<body>
<header><div class="brand"><div><h1>🚀 GLOBAL 2.0 Browser App</h1><p>Создатели: MRTOTEMCHIK и KEMEL. Telegram + браузерная публикация в один канал.</p></div><div class="topline"><input id="appKey" style="width:220px" placeholder="Ключ приложения"><button class="btn secondary" onclick="saveKey()">Сохранить ключ</button></div></div></header>
<div class="wrap">
<div class="tabs" id="tabs"></div>
<div id="view"></div>
<div class="footer">Hyper Mega Super Ultra Global Pro Plus Max Premium Elite Supreme Ultimate Deluxe Platinum Edition 2.0</div>
</div>
<script>
const tabs=[['dash','🏠 Главная'],['create','🔥 Создать'],['base','📚 База'],['drafts','🧾 Черновики'],['queue','🗓 Очередь'],['design','🎨 Оформление'],['settings','⚙️ Настройки'],['logs','📜 Логи'],['backup','💾 Backup']];
let current='dash';
const $=id=>document.getElementById(id);
function key(){return localStorage.getItem('appKey')||$('appKey').value||''}
function saveKey(){localStorage.setItem('appKey',$('appKey').value);notice('Ключ сохранён')}
function notice(t){const old=$('notice');if(old)old.remove();const d=document.createElement('div');d.id='notice';d.className='card';d.innerHTML='<b>'+escapeHtml(t)+'</b>';document.querySelector('.wrap').prepend(d);setTimeout(()=>d.remove(),2500)}
function escapeHtml(s){return String(s??'').replace(/[&<>"]/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[m]))}
async function api(path,opts={}){opts.headers=Object.assign({'X-App-Key':key()},opts.headers||{});if(opts.body&&!(opts.body instanceof FormData)){opts.headers['Content-Type']='application/json';opts.body=JSON.stringify(opts.body)}const r=await fetch(path,opts);const data=await r.json().catch(()=>({ok:false,error:'Ошибка ответа'}));if(!r.ok||data.ok===false)throw new Error(data.error||'Ошибка API');return data}
function renderTabs(){ $('appKey').value=localStorage.getItem('appKey')||''; $('tabs').innerHTML=tabs.map(t=>`<button class="tab ${t[0]===current?'active':''}" onclick="openTab('${t[0]}')">${t[1]}</button>`).join('')}
async function openTab(name){current=name;renderTabs();try{if(name==='dash')await dash();if(name==='create')create();if(name==='base')await base();if(name==='drafts')await drafts();if(name==='queue')await queue();if(name==='design')design();if(name==='settings')await settings();if(name==='logs')await logs();if(name==='backup')await backup()}catch(e){$('view').innerHTML=`<div class="card"><h2 class="danger">Ошибка</h2><pre class="status">${escapeHtml(e.message)}</pre></div>`}}
async function dash(){const s=await api('/api/stats');$('view').innerHTML=`<div class="grid"><div class="card wide"><h2>🏠 Главная панель</h2><p class="muted">Полное управление ботом из браузера.</p><div class="grid"><div class="card third"><h3>📚 Скрипты</h3><b>${s.data.scripts}</b></div><div class="card third"><h3>🚀 Публикации</h3><b>${s.data.posts}</b></div><div class="card third"><h3>🗓 Очередь</h3><b>${s.data.queue}</b></div></div></div><div class="card third"><h2>⚡ Быстро</h2><button class="btn" onclick="openTab('create')">Создать пост</button><button class="btn secondary" onclick="openTab('base')">Открыть базу</button><button class="btn secondary" onclick="runTest()">Тест</button></div><div class="card"><h2>🧪 Диагностика</h2><pre id="testBox" class="status">Нажми “Тест”.</pre></div></div>`}
async function runTest(){const r=await api('/api/test');$('testBox').textContent=r.lines.join('\n')}
function create(){ $('view').innerHTML=`<div class="grid"><div class="card wide"><h2>🔥 Создать и опубликовать</h2><div class="grid"><div class="card half"><label>Игра</label><input id="game_name"><label>Название скрипта</label><input id="script_name"><label>Тип</label><input id="script_type" value="Универсальный"><label>Платформа</label><select id="platform"><option>Mobile + PC</option><option>Mobile</option><option>PC</option><option>Universal</option></select><label>Статус</label><input id="status" value="Работает"><label>Версия</label><input id="version" value="1.0"><label><input id="key_required" type="checkbox" style="width:auto"> Нужен ключ</label></div><div class="card half"><label>Функции через запятую</label><textarea id="features"></textarea><label>Теги</label><input id="tags"><label>Описание</label><textarea id="description"></textarea><label>Инструкция</label><textarea id="instruction"></textarea><label>Стиль</label><select id="style"><option>Глобалка</option><option>Тёмный премиум</option><option>Неон</option><option>Чистый минимал</option><option>Большой релиз</option><option>Короткий</option><option>Технический</option></select></div></div><label>Lua-код</label><textarea id="lua_code" style="min-height:220px"></textarea><button class="btn good" onclick="publishFromForm()">🚀 Опубликовать в канал</button><button class="btn secondary" onclick="saveScriptFromForm()">💾 Сохранить в базу</button><button class="btn warn" onclick="saveDraftFromForm()">🧾 В черновик</button><pre id="createOut" class="status"></pre></div><div class="card third"><h2>Подсказка</h2><p class="muted">В канал отправится пост и отдельный .txt файл с Lua-кодом.</p></div></div>`}
function formData(){return{game_name:$('game_name').value,script_name:$('script_name').value,script_type:$('script_type').value,platform:$('platform').value,key_required:$('key_required').checked,status:$('status').value,version:$('version').value,features:$('features').value,tags:$('tags').value,description:$('description').value,instruction:$('instruction').value,lua_code:$('lua_code').value,style:$('style').value}}
async function publishFromForm(){try{const r=await api('/api/publish',{method:'POST',body:formData()});$('createOut').textContent='Опубликовано: '+JSON.stringify(r.result,null,2)}catch(e){$('createOut').textContent=e.message}}
async function saveScriptFromForm(){try{const r=await api('/api/scripts',{method:'POST',body:formData()});$('createOut').textContent='Сохранено. ID: '+r.id}catch(e){$('createOut').textContent=e.message}}
async function saveDraftFromForm(){try{const r=await api('/api/drafts',{method:'POST',body:formData()});$('createOut').textContent='Черновик сохранён. ID: '+r.id}catch(e){$('createOut').textContent=e.message}}
async function base(q=''){const r=await api('/api/scripts?search='+encodeURIComponent(q));$('view').innerHTML=`<div class="card"><h2>📚 База</h2><div class="topline"><input class="grow" id="search" placeholder="Поиск" value="${escapeHtml(q)}"><button class="btn" onclick="base($('search').value)">Найти</button><button class="btn secondary" onclick="openTab('create')">Добавить</button></div><div class="list">${r.items.map(s=>`<div class="item"><b>#${s.id} ${escapeHtml(s.game_name)} | ${escapeHtml(s.script_name)}</b><br><span class="pill">${escapeHtml(s.script_type)}</span><span class="pill">${escapeHtml(s.platform)}</span><span class="pill">🚀 ${s.publish_count}</span><p>${escapeHtml(s.features||'')}</p><button class="btn good" onclick="publishScript(${s.id})">Опубликовать</button><button class="btn secondary" onclick="downloadCode(${s.id})">Код</button><button class="btn bad" onclick="archiveScript(${s.id})">Архив</button></div>`).join('')||'<p>Пусто.</p>'}</div></div>`}
async function publishScript(id){try{await api('/api/scripts/'+id+'/publish',{method:'POST'});notice('Опубликовано')}catch(e){notice(e.message)}}
function downloadCode(id){window.open('/api/scripts/'+id+'/code?key='+encodeURIComponent(key()),'_blank')}
async function archiveScript(id){if(!confirm('Убрать в архив?'))return;await api('/api/scripts/'+id,{method:'DELETE'});await base()}
async function drafts(){const r=await api('/api/drafts');$('view').innerHTML=`<div class="card"><h2>🧾 Черновики</h2><div class="list">${r.items.map(d=>`<div class="item"><b>#${d.id} ${escapeHtml(d.title)}</b><br><span class="muted">${escapeHtml(d.updated_at)}</span><br><button class="btn good" onclick="publishDraft(${d.id})">Опубликовать</button><button class="btn bad" onclick="deleteDraft(${d.id})">Удалить</button></div>`).join('')||'<p>Пусто.</p>'}</div></div>`}
async function publishDraft(id){await api('/api/drafts/'+id+'/publish',{method:'POST'});notice('Опубликовано из черновика')}
async function deleteDraft(id){await api('/api/drafts/'+id,{method:'DELETE'});await drafts()}
async function queue(){const r=await api('/api/queue');$('view').innerHTML=`<div class="card"><h2>🗓 Очередь</h2><button class="btn" onclick="publishNext()">Опубликовать следующий</button><div class="list">${r.items.map(q=>`<div class="item"><b>#${q.id} ${escapeHtml(q.status)}</b><br>${escapeHtml(q.publish_at)}<br>${escapeHtml(q.title)}<br>${q.error?'<span class="danger">'+escapeHtml(q.error)+'</span>':''}</div>`).join('')||'<p>Пусто.</p>'}</div></div>`}
async function publishNext(){await api('/api/queue/next',{method:'POST'});await queue()}
function design(){ $('view').innerHTML=`<div class="grid"><div class="card half"><h2>🧼 Очистить оформление</h2><label>Название шаблона</label><input id="cleanTitle" value="Чистое оформление"><label>Чужое оформление</label><textarea id="dirtyDesign" style="min-height:260px"></textarea><button class="btn" onclick="cleanDesign()">Очистить и сохранить</button><pre id="cleanOut" class="status"></pre></div><div class="card half"><h2>🎨 Оформление</h2><p class="muted">Очистка убирает ссылки, @каналы, рекламу и мусорные строки, оставляя структуру дизайна.</p><button class="btn secondary" onclick="loadTemplates()">Показать шаблоны</button><div id="templates" class="list"></div></div></div>`}
async function cleanDesign(){try{const r=await api('/api/design/clean',{method:'POST',body:{title:$('cleanTitle').value,text:$('dirtyDesign').value}});$('cleanOut').textContent=r.cleaned}catch(e){$('cleanOut').textContent=e.message}}
async function loadTemplates(){const r=await api('/api/templates');$('templates').innerHTML=r.items.map(t=>`<div class="item"><b>#${t.id} ${escapeHtml(t.title)}</b><pre class="status">${escapeHtml(t.body.slice(0,900))}</pre></div>`).join('')||'Пусто'}
async function settings(){const r=await api('/api/settings');$('view').innerHTML=`<div class="card"><h2>⚙️ Настройки</h2>${Object.entries(r.settings).map(([k,v])=>`<label>${escapeHtml(k)}</label><input id="set_${k}" value="${escapeHtml(v)}">`).join('')}<button class="btn" onclick="saveSettings()">Сохранить</button><pre id="settingsOut" class="status"></pre></div>`}
async function saveSettings(){const inputs=[...document.querySelectorAll('[id^=set_]')];const data={};inputs.forEach(i=>data[i.id.slice(4)]=i.value);try{await api('/api/settings',{method:'POST',body:data});$('settingsOut').textContent='Сохранено'}catch(e){$('settingsOut').textContent=e.message}}
async function logs(){const r=await api('/api/logs');$('view').innerHTML=`<div class="card"><h2>📜 Логи</h2><pre class="status">${escapeHtml(r.items.map(l=>`[${l.created_at}] ${l.action} | ${l.actor_name} | ${l.details||''}`).join('\n'))}</pre></div>`}
async function backup(){const r=await api('/api/backups');$('view').innerHTML=`<div class="card"><h2>💾 Backup</h2><button class="btn" onclick="createBackup()">Создать backup</button><div class="list">${r.items.map(b=>`<div class="item"><b>${escapeHtml(b.name)}</b><br>${b.size} байт<br><a class="btn secondary" href="/api/backups/${encodeURIComponent(b.name)}?key=${encodeURIComponent(key())}" target="_blank">Скачать</a></div>`).join('')||'<p>Пусто.</p>'}</div></div>`}
async function createBackup(){await api('/api/backup',{method:'POST'});await backup()}
renderTabs();openTab('dash');
</script>
</body>
</html>'''


async def web_index(request: web.Request) -> web.Response:
    return web.Response(text=APP_HTML, content_type="text/html")


async def api_stats(request: web.Request) -> web.Response:
    auth = await require_api(request)
    if auth:
        return auth
    counts = {}
    queries = {
        "scripts": "SELECT COUNT(*) as c FROM scripts WHERE archived = 0",
        "posts": "SELECT COUNT(*) as c FROM posts",
        "drafts": "SELECT COUNT(*) as c FROM drafts",
        "queue": "SELECT COUNT(*) as c FROM queue WHERE status = 'waiting'",
        "templates": "SELECT COUNT(*) as c FROM templates",
        "media": "SELECT COUNT(*) as c FROM media",
    }
    for key, query in queries.items():
        row = await db_one(query)
        counts[key] = row["c"] if row else 0
    return json_response({"ok": True, "data": counts})


async def api_test(request: web.Request) -> web.Response:
    auth = await require_api(request)
    if auth:
        return auth
    lines = []
    try:
        me = await bot.get_me()
        lines.append(f"Бот: @{me.username} | {me.id}")
    except Exception as exc:
        lines.append(f"Бот: ошибка {exc}")
    try:
        row = await db_one("SELECT COUNT(*) as c FROM scripts")
        lines.append(f"База: OK | скриптов {row['c'] if row else 0}")
    except Exception as exc:
        lines.append(f"База: ошибка {exc}")
    try:
        chat = await bot.get_chat(await get_setting("main_channel_id", MAIN_CHANNEL_ID))
        lines.append(f"Канал: OK | {chat.title or chat.username or chat.id}")
    except Exception as exc:
        lines.append(f"Канал: ошибка {exc}")
    lines.append(f"Папки: {STORAGE_DIR.exists()}")
    return json_response({"ok": True, "lines": lines})


async def api_scripts(request: web.Request) -> web.Response:
    auth = await require_api(request)
    if auth:
        return auth
    search = clean(request.query.get("search", ""))
    if search:
        pattern = f"%{search}%"
        rows = await db_all("SELECT id, game_name, script_name, script_type, platform, status, features, publish_count, use_count FROM scripts WHERE archived = 0 AND (game_name LIKE ? OR script_name LIKE ? OR script_type LIKE ? OR tags LIKE ? OR features LIKE ?) ORDER BY id DESC LIMIT 80", (pattern, pattern, pattern, pattern, pattern))
    else:
        rows = await db_all("SELECT id, game_name, script_name, script_type, platform, status, features, publish_count, use_count FROM scripts WHERE archived = 0 ORDER BY id DESC LIMIT 80")
    return json_response({"ok": True, "items": rows})


async def api_create_script(request: web.Request) -> web.Response:
    auth = await require_api(request)
    if auth:
        return auth
    data = normalize_data(await request.json())
    issues = validate_post_data(data)
    if issues:
        return json_response({"ok": False, "error": "; ".join(issues)}, 400)
    script_id = await save_script(data, "web")
    await log_action("web_script_create", "web", f"script_id={script_id}")
    return json_response({"ok": True, "id": script_id})


async def api_publish(request: web.Request) -> web.Response:
    auth = await require_api(request)
    if auth:
        return auth
    data = normalize_data(await request.json())
    actor = type("WebActor", (), {"id": OWNER_IDS[0], "username": "web", "first_name": "Web"})()
    try:
        result = await send_post_to_channel(data, actor)
        return json_response({"ok": True, "result": result})
    except Exception as exc:
        return json_response({"ok": False, "error": str(exc)}, 400)


async def api_script_publish(request: web.Request) -> web.Response:
    auth = await require_api(request)
    if auth:
        return auth
    script_id = int(request.match_info["script_id"])
    item = await db_one("SELECT * FROM scripts WHERE id = ?", (script_id,))
    if not item:
        return json_response({"ok": False, "error": "Скрипт не найден"}, 404)
    actor = type("WebActor", (), {"id": OWNER_IDS[0], "username": "web", "first_name": "Web"})()
    try:
        result = await send_post_to_channel(dict(item), actor)
        return json_response({"ok": True, "result": result})
    except Exception as exc:
        return json_response({"ok": False, "error": str(exc)}, 400)


async def api_script_delete(request: web.Request) -> web.Response:
    auth = await require_api(request)
    if auth:
        return auth
    script_id = int(request.match_info["script_id"])
    await db_run("UPDATE scripts SET archived = 1, updated_at = ? WHERE id = ?", (now_iso(), script_id))
    return json_response({"ok": True})


async def api_script_code(request: web.Request) -> web.StreamResponse:
    auth = await require_api(request)
    if auth:
        return auth
    script_id = int(request.match_info["script_id"])
    item = await db_one("SELECT * FROM scripts WHERE id = ?", (script_id,))
    if not item:
        return json_response({"ok": False, "error": "Скрипт не найден"}, 404)
    path = make_code_file(dict(item))
    return web.FileResponse(path, headers={"Content-Disposition": f"attachment; filename={path.name}"})


async def api_drafts(request: web.Request) -> web.Response:
    auth = await require_api(request)
    if auth:
        return auth
    rows = await db_all("SELECT id, title, updated_at FROM drafts ORDER BY updated_at DESC LIMIT 100")
    return json_response({"ok": True, "items": rows})


async def api_create_draft(request: web.Request) -> web.Response:
    auth = await require_api(request)
    if auth:
        return auth
    data = normalize_data(await request.json())
    draft_id = await save_draft(data, "web")
    return json_response({"ok": True, "id": draft_id})


async def api_draft_publish(request: web.Request) -> web.Response:
    auth = await require_api(request)
    if auth:
        return auth
    draft_id = int(request.match_info["draft_id"])
    row = await db_one("SELECT * FROM drafts WHERE id = ?", (draft_id,))
    if not row:
        return json_response({"ok": False, "error": "Черновик не найден"}, 404)
    actor = type("WebActor", (), {"id": OWNER_IDS[0], "username": "web", "first_name": "Web"})()
    try:
        result = await send_post_to_channel(json.loads(row["data_json"]), actor)
        return json_response({"ok": True, "result": result})
    except Exception as exc:
        return json_response({"ok": False, "error": str(exc)}, 400)


async def api_draft_delete(request: web.Request) -> web.Response:
    auth = await require_api(request)
    if auth:
        return auth
    await db_run("DELETE FROM drafts WHERE id = ?", (int(request.match_info["draft_id"]),))
    return json_response({"ok": True})


async def api_queue(request: web.Request) -> web.Response:
    auth = await require_api(request)
    if auth:
        return auth
    rows = await db_all("SELECT * FROM queue ORDER BY publish_at ASC LIMIT 100")
    items = []
    for row in rows:
        data = json.loads(row["data_json"])
        items.append({"id": row["id"], "status": row["status"], "publish_at": row["publish_at"], "title": f"{data.get('game_name','')} | {data.get('script_name','')}", "error": row.get("error") or ""})
    return json_response({"ok": True, "items": items})


async def api_queue_next(request: web.Request) -> web.Response:
    auth = await require_api(request)
    if auth:
        return auth
    row = await db_one("SELECT * FROM queue WHERE status = 'waiting' ORDER BY publish_at ASC LIMIT 1")
    if not row:
        return json_response({"ok": False, "error": "Очередь пуста"}, 404)
    actor = type("WebActor", (), {"id": OWNER_IDS[0], "username": "web", "first_name": "Web"})()
    try:
        result = await send_post_to_channel(json.loads(row["data_json"]), actor)
        await db_run("UPDATE queue SET status = 'published', updated_at = ? WHERE id = ?", (now_iso(), row["id"]))
        return json_response({"ok": True, "result": result})
    except Exception as exc:
        await db_run("UPDATE queue SET status = 'error', error = ?, updated_at = ? WHERE id = ?", (str(exc), now_iso(), row["id"]))
        return json_response({"ok": False, "error": str(exc)}, 400)


async def api_design_clean(request: web.Request) -> web.Response:
    auth = await require_api(request)
    if auth:
        return auth
    data = await request.json()
    title = clean(data.get("title")) or "Чистое оформление"
    cleaned = clean_design_text(data.get("text", ""))
    if not cleaned:
        return json_response({"ok": False, "error": "После очистки ничего не осталось"}, 400)
    async with open_db() as db:
        cursor = await db.execute("INSERT INTO templates (title, body, source, created_by, created_at) VALUES (?, ?, 'web_clean_design', 'web', ?)", (title, cleaned, now_iso()))
        await db.commit()
        template_id = int(cursor.lastrowid)
    return json_response({"ok": True, "id": template_id, "cleaned": cleaned})


async def api_templates(request: web.Request) -> web.Response:
    auth = await require_api(request)
    if auth:
        return auth
    rows = await db_all("SELECT id, title, body, source, created_at FROM templates ORDER BY id DESC LIMIT 80")
    return json_response({"ok": True, "items": rows})


async def api_settings(request: web.Request) -> web.Response:
    auth = await require_api(request)
    if auth:
        return auth
    rows = await db_all("SELECT key, value FROM settings ORDER BY key")
    return json_response({"ok": True, "settings": {row["key"]: row["value"] for row in rows}})


async def api_update_settings(request: web.Request) -> web.Response:
    auth = await require_api(request)
    if auth:
        return auth
    data = await request.json()
    allowed = {"project_name", "main_channel_id", "footer", "web_public_url", "web_app_secret", "default_style", "antispam_enabled", "browser_app_enabled"}
    for key, value in data.items():
        if key in allowed:
            await set_setting(key, clean(value))
    return json_response({"ok": True})


async def api_logs(request: web.Request) -> web.Response:
    auth = await require_api(request)
    if auth:
        return auth
    rows = await db_all("SELECT * FROM logs ORDER BY id DESC LIMIT 120")
    return json_response({"ok": True, "items": rows})


async def api_backup(request: web.Request) -> web.Response:
    auth = await require_api(request)
    if auth:
        return auth
    path = await create_backup()
    return json_response({"ok": True, "name": path.name, "size": path.stat().st_size})


async def api_backups(request: web.Request) -> web.Response:
    auth = await require_api(request)
    if auth:
        return auth
    ensure_dirs()
    items = []
    for path in sorted(BACKUP_DIR.glob("*.db"), reverse=True):
        items.append({"name": path.name, "size": path.stat().st_size})
    return json_response({"ok": True, "items": items})


async def api_backup_file(request: web.Request) -> web.StreamResponse:
    auth = await require_api(request)
    if auth:
        return auth
    name = Path(request.match_info["name"]).name
    path = BACKUP_DIR / name
    if not path.exists():
        return json_response({"ok": False, "error": "Backup не найден"}, 404)
    return web.FileResponse(path, headers={"Content-Disposition": f"attachment; filename={path.name}"})


def create_web_app() -> web.Application:
    app = web.Application(client_max_size=20 * 1024 * 1024)
    app.router.add_get("/", web_index)
    app.router.add_get("/api/stats", api_stats)
    app.router.add_get("/api/test", api_test)
    app.router.add_get("/api/scripts", api_scripts)
    app.router.add_post("/api/scripts", api_create_script)
    app.router.add_post("/api/publish", api_publish)
    app.router.add_post("/api/scripts/{script_id}/publish", api_script_publish)
    app.router.add_delete("/api/scripts/{script_id}", api_script_delete)
    app.router.add_get("/api/scripts/{script_id}/code", api_script_code)
    app.router.add_get("/api/drafts", api_drafts)
    app.router.add_post("/api/drafts", api_create_draft)
    app.router.add_post("/api/drafts/{draft_id}/publish", api_draft_publish)
    app.router.add_delete("/api/drafts/{draft_id}", api_draft_delete)
    app.router.add_get("/api/queue", api_queue)
    app.router.add_post("/api/queue/next", api_queue_next)
    app.router.add_post("/api/design/clean", api_design_clean)
    app.router.add_get("/api/templates", api_templates)
    app.router.add_get("/api/settings", api_settings)
    app.router.add_post("/api/settings", api_update_settings)
    app.router.add_get("/api/logs", api_logs)
    app.router.add_post("/api/backup", api_backup)
    app.router.add_get("/api/backups", api_backups)
    app.router.add_get("/api/backups/{name}", api_backup_file)
    return app


async def start_web_server() -> web.AppRunner:
    app = create_web_app()
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, WEB_HOST, WEB_PORT)
    await site.start()
    logger.info("Web app started at http://%s:%s", WEB_HOST, WEB_PORT)
    return runner


async def main() -> None:
    await init_db()
    router.message.middleware(AccessMiddleware())
    router.callback_query.middleware(AccessMiddleware())
    dp.include_router(router)
    web_runner = await start_web_server()
    scheduler_task = asyncio.create_task(scheduler_loop())
    logger.info("%s started", VERSION)
    try:
        await dp.start_polling(bot)
    finally:
        scheduler_task.cancel()
        await web_runner.cleanup()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
