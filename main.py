import os
import random
import asyncio
from datetime import datetime
from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.enums import ParseMode

BOT_TOKEN = os.environ.get("DEMO_BOT_TOKEN", "ВСТАВЬ_ТОКЕН_ДЕМО_БОТА")
ADMIN_ID = int(os.environ.get("DEMO_ADMIN_ID", "0"))  # твой Telegram ID

# ============================================
# ДАННЫЕ (в памяти — для демо)
# ============================================
PRODUCTS = [
    {"id": "cake_red",   "name": "Красный бархат",  "price": 1500, "weight": "1.5 кг", "cat": "cakes",     "emoji": "🎂", "desc": "Нежный бисквит, крем-чиз, ягода"},
    {"id": "cake_choco", "name": "Шоколадный трюфель","price": 1700, "weight": "1.8 кг", "cat": "cakes",     "emoji": "🍫", "desc": "Тёмный шоколад, ганаш, хрустящий слой"},
    {"id": "cake_medovik","name": "Медовик",         "price": 1300, "weight": "1.2 кг", "cat": "cakes",     "emoji": "🍯", "desc": "Классика со сметанным кремом"},
    {"id": "cup_van",    "name": "Капкейк ванильный","price": 180,  "weight": "90 г",   "cat": "cupcakes",  "emoji": "🧁", "desc": "Ваниль + ягодный конфитюр"},
    {"id": "cup_choco",  "name": "Капкейк шоколадный","price": 180, "weight": "90 г",   "cat": "cupcakes",  "emoji": "🧁", "desc": "Шоколад + ганаш"},
    {"id": "mac_pack",   "name": "Макаруны (набор 6)","price": 750, "weight": "180 г",  "cat": "macarons",  "emoji": "🌈", "desc": "6 вкусов: фисташка, малина, манго..."},
    {"id": "des_panna",  "name": "Панна-котта",      "price": 320,  "weight": "120 г",  "cat": "desserts",  "emoji": "🍮", "desc": "Сливочная, с ягодным соусом"},
    {"id": "des_eclair", "name": "Эклер",            "price": 250,  "weight": "80 г",   "cat": "desserts",  "emoji": "🥐", "desc": "Заварной крем, шоколадная глазурь"},
]

CATEGORIES = {
    "cakes":    "🎂 Торты",
    "cupcakes": "🧁 Капкейки",
    "macarons": "🌈 Макаруны",
    "desserts": "🍮 Десерты",
}

DELIVERY_COST = 300
FREE_FROM = 3000

# Корзины и заказы в памяти
CARTS = {}    # {user_id: [{"id":..., "qty":...}]}
ORDERS = {}   # {number: {...}}

STATUS_FLOW = ["new", "cooking", "ready", "delivered"]
STATUS_LABEL = {
    "new":       "🟡 Принят",
    "cooking":   "👨‍🍳 Готовится",
    "ready":     "✅ Готов",
    "delivered": "🎉 Доставлен",
    "cancelled": "❌ Отменён",
}
STATUS_NOTIFY = {
    "cooking":   "👨‍ Ваш заказ #{num} начали готовить!",
    "ready":     "✅ Заказ #{num} готов! Курьер выехал 🚚",
    "delivered": "🎉 Заказ #{num} доставлен. Приятного аппетита! 🍰",
    "cancelled": "❌ Заказ #{num} отменён. Напиши в поддержку, если вопрос.",
}

router = Router()

def cart_of(user_id):
    return CARTS.setdefault(user_id, [])

def cart_total(user_id):
    total = 0
    for item in cart_of(user_id):
        p = next((x for x in PRODUCTS if x["id"] == item["id"]), None)
        if p:
            total += p["price"] * item["qty"]
    return total

def find_product(pid):
    return next((x for x in PRODUCTS if x["id"] == pid), None)

# ============================================
# КЛАВИАТУРЫ
# ============================================
def main_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🛒 Меню", callback_data="menu")],
        [InlineKeyboardButton(text="🧺 Корзина", callback_data="cart")],
        [InlineKeyboardButton(text="📦 Мои заказы", callback_data="my_orders")],
    ])

def cats_kb():
    rows = [[InlineKeyboardButton(text=label, callback_data=f"cat_{cid}")] for cid, label in CATEGORIES.items()]
    rows.append([InlineKeyboardButton(text="🔙 В меню", callback_data="back_home")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def products_kb(cat):
    rows = []
    for p in PRODUCTS:
        if p["cat"] == cat:
            rows.append([InlineKeyboardButton(
                text=f"{p['emoji']} {p['name']} — {p['price']}₽",
                callback_data=f"prod_{p['id']}"
            )])
    rows.append([InlineKeyboardButton(text="🔙 Категории", callback_data="menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def product_kb(pid):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ В корзину", callback_data=f"add_{pid}")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_cat_" + (find_product(pid) or {}).get("cat", "cakes"))],
    ])

def cart_kb(user_id):
    items = cart_of(user_id)
    rows = []
    for it in items:
        p = find_product(it["id"])
        if not p:
            continue
        rows.append([
            InlineKeyboardButton(text=f"➖", callback_data=f"dec_{p['id']}"),
            InlineKeyboardButton(text=f"{p['emoji']} {p['name']} ×{it['qty']}", callback_data="noop"),
            InlineKeyboardButton(text="➕", callback_data=f"inc_{p['id']}"),
        ])
    total = cart_total(user_id)
    delivery = 0 if total >= FREE_FROM or total == 0 else DELIVERY_COST
    rows.append([InlineKeyboardButton(text=f"💰 Итого: {total + delivery}₽", callback_data="noop")])
    if total > 0:
        rows.append([InlineKeyboardButton(text="✅ Оформить заказ", callback_data="checkout")])
    rows.append([InlineKeyboardButton(text="🔙 В меню", callback_data="back_home")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def checkout_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚚 Доставка (+300₽)", callback_data="dlv_delivery")],
        [InlineKeyboardButton(text="🏠 Самовывоз (0₽)", callback_data="dlv_pickup")],
        [InlineKeyboardButton(text="🔙 В корзину", callback_data="cart")],
    ])

def pay_kb(num):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 Оплатить (демо)", callback_data=f"pay_{num}")],
        [InlineKeyboardButton(text="❌ Отменить", callback_data=f"cancel_{num}")],
    ])

def track_kb(num):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📦 Обновить статус", callback_data=f"track_{num}")],
        [InlineKeyboardButton(text="🔙 В меню", callback_data="back_home")],
    ])

def admin_orders_kb():
    rows = []
    for num, o in sorted(ORDERS.items(), key=lambda x: x[1]["created"], reverse=True)[:10]:
        rows.append([InlineKeyboardButton(
            text=f"#{num} · {o['client']} · {o['total']}₽ · {STATUS_LABEL[o['status']]}",
            callback_data=f"adm_open_{num}"
        )])
    if not rows:
        rows = [[InlineKeyboardButton(text="📭 Заказов нет", callback_data="noop")]]
    rows.append([InlineKeyboardButton(text="🔙 В меню", callback_data="back_home")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def admin_status_kb(num):
    rows = []
    for st in STATUS_FLOW + ["cancelled"]:
        rows.append([InlineKeyboardButton(text=f"→ {STATUS_LABEL[st]}", callback_data=f"adm_set_{num}_{st}")])
    rows.append([InlineKeyboardButton(text="🔙 К списку", callback_data="admin")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

# ============================================
# ХЕНДЛЕРЫ — КЛИЕНТ
# ============================================
@router.message(Command("start"))
async def cmd_start(m: Message):
    await m.answer(
        "🍰 <b>Sweet Nil — демо кондитерской</b>\n\n"
        "Торты, капкейки, макаруны и десерты с доставкой.\n"
        "⚠️ Это демо-проект: оплата и статусы имитируются.",
        reply_markup=main_kb(), parse_mode=ParseMode.HTML
    )

@router.callback_query(F.data == "back_home")
async def back_home(c: CallbackQuery):
    await c.answer()
    await c.message.edit_text("🍰 <b>Sweet Nil</b>\nВыбери действие:", reply_markup=main_kb(), parse_mode=ParseMode.HTML)

@router.callback_query(F.data == "menu")
async def show_menu(c: CallbackQuery):
    await c.answer()
    await c.message.edit_text("🛒 <b>Категории:</b>", reply_markup=cats_kb(), parse_mode=ParseMode.HTML)

@router.callback_query(F.data.startswith("cat_"))
async def show_cat(c: CallbackQuery):
    cat = c.data.replace("cat_", "")
    await c.answer()
    await c.message.edit_text(f"🛒 <b>{CATEGORIES.get(cat, cat)}:</b>", reply_markup=products_kb(cat), parse_mode=ParseMode.HTML)

@router.callback_query(F.data.startswith("back_cat_"))
async def back_cat(c: CallbackQuery):
    cat = c.data.replace("back_cat_", "")
    await c.answer()
    await c.message.edit_text(f"🛒 <b>{CATEGORIES.get(cat, cat)}:</b>", reply_markup=products_kb(cat), parse_mode=ParseMode.HTML)

@router.callback_query(F.data.startswith("prod_"))
async def show_prod(c: CallbackQuery):
    pid = c.data.replace("prod_", "")
    p = find_product(pid)
    if not p:
        await c.answer("Товар не найден"); return
    await c.answer()
    await c.message.edit_text(
        f"{p['emoji']} <b>{p['name']}</b>\n"
        f"📝 {p['desc']}\n"
        f"⚖️ {p['weight']}\n"
        f"💰 <b>{p['price']}₽</b>",
        reply_markup=product_kb(pid), parse_mode=ParseMode.HTML
    )

@router.callback_query(F.data.startswith("add_"))
async def add_to_cart(c: CallbackQuery):
    pid = c.data.replace("add_", "")
    p = find_product(pid)
    if not p:
        await c.answer("Товар не найден"); return
    cart = cart_of(c.from_user.id)
    ex = next((i for i in cart if i["id"] == pid), None)
    if ex: ex["qty"] += 1
    else: cart.append({"id": pid, "qty": 1})
    await c.answer(f"➕ {p['name']} в корзине")

@router.callback_query(F.data.startswith("inc_"))
async def inc(c: CallbackQuery):
    pid = c.data.replace("inc_", "")
    for i in cart_of(c.from_user.id):
        if i["id"] == pid: i["qty"] += 1
    await c.answer()
    await show_cart(c)

@router.callback_query(F.data.startswith("dec_"))
async def dec(c: CallbackQuery):
    pid = c.data.replace("dec_", "")
    cart = cart_of(c.from_user.id)
    for i in cart:
        if i["id"] == pid:
            i["qty"] -= 1
            if i["qty"] <= 0:
                cart.remove(i)
            break
    await c.answer()
    await show_cart(c)

@router.callback_query(F.data == "cart")
async def show_cart(c: CallbackQuery):
    await c.answer()
    items = cart_of(c.from_user.id)
    if not items:
        await c.message.edit_text("🧺 Корзина пуста.\nДобавь что-нибудь из меню!", reply_markup=main_kb())
        return
    lines = []
    for it in items:
        p = find_product(it["id"])
        if p: lines.append(f"{p['emoji']} {p['name']} ×{it['qty']} = {p['price']*it['qty']}₽")
    total = cart_total(c.from_user.id)
    delivery = 0 if total >= FREE_FROM else DELIVERY_COST
    txt = "🧺 <b>Корзина:</b>\n\n" + "\n".join(lines)
    txt += f"\n\n🚚 Доставка: {delivery}₽" + (" (бесплатно от 3000₽)" if delivery == 0 else "")
    txt += f"\n💰 <b>Итого: {total + delivery}₽</b>"
    await c.message.edit_text(txt, reply_markup=cart_kb(c.from_user.id), parse_mode=ParseMode.HTML)

@router.callback_query(F.data == "checkout")
async def checkout(c: CallbackQuery):
    await c.answer()
    await c.message.edit_text("📦 <b>Способ получения:</b>", reply_markup=checkout_kb(), parse_mode=ParseMode.HTML)

@router.callback_query(F.data.startswith("dlv_"))
async def choose_delivery(c: CallbackQuery):
    kind = c.data.replace("dlv_", "")
    user_id = c.from_user.id
    cart = cart_of(user_id)
    if not cart:
        await c.answer("Корзина пуста"); return
    total = cart_total(user_id)
    delivery = 0 if kind == "pickup" or total >= FREE_FROM else DELIVERY_COST
    num = f"SW-{random.randint(1000,9999)}"
    ORDERS[num] = {
        "number": num,
        "client": c.from_user.full_name,
        "tg_id": user_id,
        "items": [dict(find_product(i["id"]), qty=i["qty"]) for i in cart],
        "subtotal": total,
        "delivery": delivery,
        "delivery_type": kind,
        "total": total + delivery,
        "status": "new",
        "payment": "waiting",
        "created": datetime.now().isoformat(),
    }
    CARTS[user_id] = []
    await c.answer()
    await c.message.edit_text(
        f"📋 <b>Заказ #{num}</b>\n\n"
        f"🚚 {kind.upper()}\n"
        f"💰 Сумма: <b>{ORDERS[num]['total']}₽</b>\n\n"
        f"Нажми «Оплатить», чтобы подтвердить (демо).",
        reply_markup=pay_kb(num), parse_mode=ParseMode.HTML
    )
    # уведомляем админа
    try:
        await c.bot.send_message(ADMIN_ID,
            f"🆕 <b>НОВЫЙ ЗАКАЗ #{num}</b>\n👤 {ORDERS[num]['client']}\n💰 {ORDERS[num]['total']}₽\n⏳ Ожидает оплаты",
            parse_mode=ParseMode.HTML)
    except Exception:
        pass

@router.callback_query(F.data.startswith("pay_"))
async def pay(c: CallbackQuery):
    num = c.data.replace("pay_", "")
    o = ORDERS.get(num)
    if not o:
        await c.answer("Заказ не найден"); return
    o["payment"] = "paid"
    await c.answer("💳 Оплата прошла (демо)")
    await c.message.edit_text(
        f"✅ <b>Заказ #{num} оплачен!</b>\n\n"
        f"🟡 Статус: Принят\n"
        f"🔔 Будем уведомлять о каждом этапе.\n\n"
        f"📦 Отследить:",
        reply_markup=track_kb(num), parse_mode=ParseMode.HTML
    )
    try:
        await c.bot.send_message(ADMIN_ID,
            f"💰 <b>Заказ #{num} ОПЛАЧЕН</b>\n👤 {o['client']}\n💰 {o['total']}₽\n✅ Можно готовить!",
            parse_mode=ParseMode.HTML)
    except Exception:
        pass

@router.callback_query(F.data.startswith("cancel_"))
async def cancel_order(c: CallbackQuery):
    num = c.data.replace("cancel_", "")
    o = ORDERS.get(num)
    if not o:
        await c.answer("Заказ не найден"); return
    o["status"] = "cancelled"
    await c.answer("❌ Заказ отменён")
    await c.message.edit_text(f"❌ Заказ #{num} отменён.", reply_markup=main_kb())

@router.callback_query(F.data.startswith("track_"))
async def track(c: CallbackQuery):
    num = c.data.replace("track_", "")
    o = ORDERS.get(num)
    if not o:
        await c.answer("Не найден"); return
    await c.answer()
    await c.message.edit_text(
        f"📦 <b>Заказ #{num}</b>\n"
        f"Статус: {STATUS_LABEL[o['status']]}\n"
        f"💰 {o['total']}₽",
        reply_markup=track_kb(num), parse_mode=ParseMode.HTML
    )

@router.callback_query(F.data == "my_orders")
async def my_orders(c: CallbackQuery):
    await c.answer()
    mine = [o for o in ORDERS.values() if o["tg_id"] == c.from_user.id]
    if not mine:
        await c.message.edit_text("📭 У тебя пока нет заказов.", reply_markup=main_kb())
        return
    txt = "📦 <b>Мои заказы:</b>\n\n"
    for o in sorted(mine, key=lambda x: x["created"], reverse=True):
        txt += f"#{o['number']} · {o['total']}₽ · {STATUS_LABEL[o['status']]}\n"
    await c.message.edit_text(txt, reply_markup=main_kb(), parse_mode=ParseMode.HTML)

@router.callback_query(F.data == "noop")
async def noop(c: CallbackQuery):
    await c.answer()

# ============================================
# ХЕНДЛЕРЫ — АДМИН
# ============================================
@router.callback_query(F.data == "admin")
async def admin_panel(c: CallbackQuery):
    if c.from_user.id != ADMIN_ID:
        await c.answer("⛔ Нет доступа"); return
    await c.answer()
    await c.message.edit_text("👑 <b>Заказы (демо):</b>", reply_markup=admin_orders_kb(), parse_mode=ParseMode.HTML)

@router.callback_query(F.data.startswith("adm_open_"))
async def adm_open(c: CallbackQuery):
    if c.from_user.id != ADMIN_ID:
        await c.answer("⛔ Нет доступа"); return
    num = c.data.replace("adm_open_", "")
    o = ORDERS.get(num)
    if not o:
        await c.answer("Не найден"); return
    await c.answer()
    items_txt = "\n".join(f"{i['emoji']} {i['name']} ×{i['qty']}" for i in o["items"])
    await c.message.edit_text(
        f"📋 <b>Заказ #{num}</b>\n"
        f"👤 {o['client']}\n"
        f"🚚 {o['delivery_type']}\n"
        f"🧺 {items_txt}\n"
        f"💰 {o['total']}₽\n"
        f"📊 Статус: {STATUS_LABEL[o['status']]}\n\n"
        f"Смени статус:",
        reply_markup=admin_status_kb(num), parse_mode=ParseMode.HTML
    )

@router.callback_query(F.data.startswith("adm_set_"))
async def adm_set(c: CallbackQuery):
    if c.from_user.id != ADMIN_ID:
        await c.answer("⛔ Нет доступа"); return
    _, _, num, st = c.data.split("_", 3)
    o = ORDERS.get(num)
    if not o:
        await c.answer("Не найден"); return
    o["status"] = st
    await c.answer(f"✅ Статус: {STATUS_LABEL[st]}")
    # уведомляем клиента
    msg = STATUS_NOTIFY.get(st, f"📦 Заказ #{num}: {STATUS_LABEL[st]}").format(num=num)
    try:
        await c.bot.send_message(o["tg_id"],
            f"🔔 <b>Обновление по заказу #{num}</b>\n\n{msg}",
            parse_mode=ParseMode.HTML, reply_markup=track_kb(num))
    except Exception:
        pass
    await adm_open(c)

# ============================================
# ЗАПУСК
# ============================================
async def main():
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher()
    dp.include_router(router)
    print("🍰 Sweet Nil DEMO запущен!")
    print(f"👑 Admin ID: {ADMIN_ID}")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
