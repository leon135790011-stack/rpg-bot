import random
import json
import os
from datetime import datetime
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# ---------- НАСТРОЙКИ ----------
TOKEN = "8952729637:AAH4_8HovY5axd2SM96QHwzbi6My5wup2WY"  # <-- ЗАМЕНИ НА СВОЙ ТОКЕН
PVE_INTERVAL = 3 * 3600

PLAYERS_FILE = "players.json"

CLASSES = {
    "воин":  {"hp": 120, "attack": 15, "defense": 10, "emoji": "⚔️", "weapon": "ржавый меч", "armor": "кожаная броня"},
    "маг":   {"hp": 80,  "attack": 25, "defense": 4,  "emoji": "🔮", "weapon": "деревянный посох", "armor": "тканевая роба"},
    "лучник":{"hp": 90,  "attack": 18, "defense": 6,  "emoji": "🏹", "weapon": "короткий лук", "armor": "стеганый доспех"},
}

WEAPONS = {
    "ржавый меч":      {"attack": 0,  "price": 0,   "desc": "Стартовое оружие воина"},
    "деревянный посох": {"attack": 0,  "price": 0,   "desc": "Стартовое оружие мага"},
    "короткий лук":     {"attack": 0,  "price": 0,   "desc": "Стартовое оружие лучника"},
    "стальной меч":     {"attack": 8,  "price": 120, "desc": "+8 к атаке (воин)", "class": "воин"},
    "двуручный топор":  {"attack": 12, "price": 200, "desc": "+12 атаки, -3 защиты (воин)", "class": "воин", "defense_penalty": 3},
    "магический жезл":  {"attack": 10, "price": 150, "desc": "+10 к атаке (маг)", "class": "маг"},
    "посох стихий":     {"attack": 14, "price": 250, "desc": "+14 к атаке (маг)", "class": "маг"},
    "длинный лук":      {"attack": 9,  "price": 130, "desc": "+9 к атаке (лучник)", "class": "лучник"},
    "арбалет":          {"attack": 11, "price": 180, "desc": "+11 к атаке (лучник)", "class": "лучник"},
}

ARMORS = {
    "кожаная броня":    {"defense": 0, "price": 0,   "desc": "Стартовая броня"},
    "тканевая роба":    {"defense": 0, "price": 0,   "desc": "Стартовая броня"},
    "стеганый доспех":  {"defense": 0, "price": 0,   "desc": "Стартовая броня"},
    "кольчуга":         {"defense": 6, "price": 100, "desc": "+6 к защите"},
    "латный доспех":    {"defense": 10,"price": 220, "desc": "+10 защиты, -2 атаки", "attack_penalty": 2},
    "магическая мантия":{"defense": 5, "price": 140, "desc": "+5 защиты, +3 атаки (маг)", "attack_bonus": 3, "class": "маг"},
    "эльфийский плащ":  {"defense": 7, "price": 160, "desc": "+7 защиты, +2 атаки (лучник)", "attack_bonus": 2, "class": "лучник"},
}

MONSTERS = [
    {"name": "Гоблин",       "hp": 40,  "attack": 8,  "defense": 2, "exp": 30,  "gold": 15, "emoji": "👺"},
    {"name": "Скелет",       "hp": 55,  "attack": 12, "defense": 4, "exp": 45,  "gold": 25, "emoji": "💀"},
    {"name": "Орк",          "hp": 80,  "attack": 15, "defense": 6, "exp": 60,  "gold": 40, "emoji": "👹"},
    {"name": "Тёмный маг",   "hp": 60,  "attack": 22, "defense": 3, "exp": 75,  "gold": 55, "emoji": "🧙‍♂️"},
    {"name": "Волк-оборотень","hp": 100,"attack": 18, "defense": 7, "exp": 90,  "gold": 70, "emoji": "🐺"},
    {"name": "Элементаль",   "hp": 120, "attack": 25, "defense": 10,"exp": 120, "gold": 100,"emoji": "🔥"},
    {"name": "Драконид",     "hp": 150, "attack": 30, "defense": 12,"exp": 160, "gold": 150,"emoji": "🐉"},
    {"name": "Демон",        "hp": 200, "attack": 35, "defense": 15,"exp": 220, "gold": 220,"emoji": "😈"},
]

def load_json(path):
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

players = load_json(PLAYERS_FILE)
pve_state = {}

def get_effective_stats(player):
    weapon = WEAPONS.get(player.get("weapon", ""), {})
    armor = ARMORS.get(player.get("armor", ""), {})
    return {
        "attack": player["attack"] + weapon.get("attack", 0) + armor.get("attack_bonus", 0) - armor.get("attack_penalty", 0),
        "defense": player["defense"] + armor.get("defense", 0) - weapon.get("defense_penalty", 0)
    }

def get_player(group_id, user_id):
    return players.get(str(group_id), {}).get(str(user_id))

def set_player(group_id, user_id, data):
    gid = str(group_id)
    uid = str(user_id)
    if gid not in players:
        players[gid] = {}
    players[gid][uid] = data
    save_json(PLAYERS_FILE, players)

def exp_to_level(level):
    return 50 + level * 30

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎲 *РПГ-бот v2.0*\n\n"
        "`/create Имя класс` — создать персонажа\n"
        "`/stats` — характеристики\n"
        "`/attack` (ответом) — PvP\n"
        "`/hit` — атаковать монстра\n"
        "`/monster` — статус монстра\n"
        "`/inv` — инвентарь\n"
        "`/shop` — купить снаряжение\n"
        "`/buy N` — купить предмет\n"
        "`/equip N` — надеть предмет\n"
        "`/heal` — восстановить HP\n"
        "`/top` — рейтинг\n"
        "`/reset` — удалить персонажа",
        parse_mode="Markdown"
    )

async def cmd_create(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if len(args) < 2:
        await update.message.reply_text("❌ `/create Имя класс`\nКлассы: воин, маг, лучник", parse_mode="Markdown")
        return
    name = args[0]
    cls = args[1].lower()
    if cls not in CLASSES:
        await update.message.reply_text("❌ Классы: воин, маг, лучник")
        return
    if get_player(update.effective_chat.id, update.effective_user.id):
        await update.message.reply_text("❌ Уже есть персонаж. `/reset` для удаления.", parse_mode="Markdown")
        return
    base = CLASSES[cls]
    p = {
        "name": name, "class": cls, "hp": base["hp"], "max_hp": base["hp"],
        "attack": base["attack"], "defense": base["defense"], "level": 1, "exp": 0,
        "gold": 0, "weapon": base["weapon"], "armor": base["armor"], "inventory": [], "pve_attacks": 0
    }
    set_player(update.effective_chat.id, update.effective_user.id, p)
    eff = get_effective_stats(p)
    await update.message.reply_text(
        f"{base['emoji']} *{name}* — {cls.capitalize()}!\n"
        f"❤️ HP: {base['hp']}/{base['hp']}\n"
        f"⚔️ Атака: {eff['attack']} | 🛡️ Защита: {eff['defense']}\n"
        f"🗡️ {base['weapon']} | 🛡️ {base['armor']}\n"
        f"⭐ Уровень: 1 | 💰 0 золота",
        parse_mode="Markdown"
    )

async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    p = get_player(update.effective_chat.id, update.effective_user.id)
    if not p:
        await update.message.reply_text("❌ Создайте персонажа: `/create Имя класс`", parse_mode="Markdown")
        return
    eff = get_effective_stats(p)
    emoji = CLASSES[p["class"]]["emoji"]
    to_next = exp_to_level(p["level"]) - p["exp"]
    await update.message.reply_text(
        f"{emoji} *{p['name']}* — {p['class'].capitalize()} | Ур. {p['level']}\n"
        f"❤️ HP: {p['hp']}/{p['max_hp']}\n"
        f"⚔️ Атака: {eff['attack']} | 🛡️ Защита: {eff['defense']}\n"
        f"🗡️ {p['weapon']} | 🛡️ {p['armor']}\n"
        f"✨ Опыт: {p['exp']}/{exp_to_level(p['level'])} | 💰 {p['gold']}",
        parse_mode="Markdown"
    )

async def cmd_inv(update: Update, context: ContextTypes.DEFAULT_TYPE):
    p = get_player(update.effective_chat.id, update.effective_user.id)
    if not p:
        await update.message.reply_text("❌ Создайте персонажа: `/create Имя класс`", parse_mode="Markdown")
        return
    text = f"🎒 *Инвентарь {p['name']}* | 💰 {p['gold']} золота\n\n"
    text += f"🗡️ Оружие: *{p['weapon']}*\n🛡️ Броня: *{p['armor']}*\n\n"
    if not p["inventory"]:
        text += "Инвентарь пуст."
    else:
        text += "*Предметы:*\n"
        for i, item in enumerate(p["inventory"], 1):
            text += f"{i}. {item['name']} ({item['type']}) — `/equip {i}`\n"
    await update.message.reply_text(text, parse_mode="Markdown")

async def cmd_shop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    p = get_player(update.effective_chat.id, update.effective_user.id)
    if not p:
        await update.message.reply_text("❌ Создайте персонажа", parse_mode="Markdown")
        return
    pc = p["class"]
    text = f"🏪 *Магазин* | 💰 Ваше золото: {p['gold']}\n\n*Оружие:*\n"
    shop = []
    for name, data in WEAPONS.items():
        if data["price"] == 0: continue
        if "class" in data and data["class"] != pc: continue
        shop.append({"name": name, "type": "оружие", "price": data["price"]})
        text += f"{len(shop)}. {name} — {data['price']}💰 | {data['desc']}\n"
    text += "\n*Броня:*\n"
    for name, data in ARMORS.items():
        if data["price"] == 0: continue
        if "class" in data and data["class"] != pc: continue
        shop.append({"name": name, "type": "броня", "price": data["price"]})
        text += f"{len(shop)}. {name} — {data['price']}💰 | {data['desc']}\n"
    p["_shop"] = shop
    set_player(update.effective_chat.id, update.effective_user.id, p)
    text += "\n`/buy N` — купить предмет"
    await update.message.reply_text(text, parse_mode="Markdown")

async def cmd_buy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    p = get_player(update.effective_chat.id, update.effective_user.id)
    if not p or "_shop" not in p:
        await update.message.reply_text("❌ Сначала `/shop`", parse_mode="Markdown")
        return
    try:
        idx = int(context.args[0]) - 1
    except:
        await update.message.reply_text("❌ `/buy N`", parse_mode="Markdown")
        return
    if idx < 0 or idx >= len(p["_shop"]):
        await update.message.reply_text("❌ Неверный номер")
        return
    item = p["_shop"][idx]
    if p["gold"] < item["price"]:
        await update.message.reply_text(f"❌ Не хватает золота! Нужно {item['price']}, у вас {p['gold']}")
        return
    p["gold"] -= item["price"]
    p["inventory"].append({"name": item["name"], "type": item["type"]})
    set_player(update.effective_chat.id, update.effective_user.id, p)
    await update.message.reply_text(f"✅ Куплено: *{item['name']}*\nНадеть: `/equip {len(p['inventory'])}`", parse_mode="Markdown")

async def cmd_equip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    p = get_player(update.effective_chat.id, update.effective_user.id)
    if not p:
        await update.message.reply_text("❌ Создайте персонажа", parse_mode="Markdown")
        return
    try:
        idx = int(context.args[0]) - 1
    except:
        await update.message.reply_text("❌ `/equip N`", parse_mode="Markdown")
        return
    if idx < 0 or idx >= len(p["inventory"]):
        await update.message.reply_text("❌ Неверный номер")
        return
    item = p["inventory"].pop(idx)
    if item["type"] == "оружие":
        old = {"name": p["weapon"], "type": "оружие"}
        p["weapon"] = item["name"]
    else:
        old = {"name": p["armor"], "type": "броня"}
        p["armor"] = item["name"]
    if WEAPONS.get(old["name"], {}).get("price", 0) > 0 or ARMORS.get(old["name"], {}).get("price", 0) > 0:
        p["inventory"].append(old)
    set_player(update.effective_chat.id, update.effective_user.id, p)
    eff = get_effective_stats(p)
    await update.message.reply_text(f"✅ Надето: *{item['name']}*\n⚔️ Атака: {eff['attack']} | 🛡️ Защита: {eff['defense']}", parse_mode="Markdown")

async def cmd_attack(update: Update, context: ContextTypes.DEFAULT_TYPE):
    attacker = get_player(update.effective_chat.id, update.effective_user.id)
    if not attacker:
        await update.message.reply_text("❌ Создайте персонажа", parse_mode="Markdown")
        return
    if not update.message.reply_to_message:
        await update.message.reply_text("❌ Ответьте на сообщение противника!")
        return
    target_user = update.message.reply_to_message.from_user
    if target_user.id == update.effective_user.id:
        await update.message.reply_text("🤕 Нельзя атаковать себя!")
        return
    defender = get_player(update.effective_chat.id, target_user.id)
    if not defender:
        await update.message.reply_text(f"❌ У {target_user.first_name} нет персонажа!")
        return
    a_eff = get_effective_stats(attacker)
    d_eff = get_effective_stats(defender)
    dmg = max(1, random.randint(a_eff["attack"] - 3, a_eff["attack"] + 5) - random.randint(0, d_eff["defense"] // 2))
    defender["hp"] = max(0, defender["hp"] - dmg)
    exp_gain = random.randint(10, 25)
    gold_gain = random.randint(5, 15)
    attacker["exp"] += exp_gain
    attacker["gold"] += gold_gain
    leveled = False
    while attacker["exp"] >= exp_to_level(attacker["level"]):
        attacker["exp"] -= exp_to_level(attacker["level"])
        attacker["level"] += 1
        attacker["max_hp"] += 15
        attacker["hp"] = attacker["max_hp"]
        attacker["attack"] += random.randint(2, 5)
        attacker["defense"] += random.randint(1, 3)
        leveled = True
    set_player(update.effective_chat.id, target_user.id, defender)
    set_player(update.effective_chat.id, update.effective_user.id, attacker)
    a_emoji = CLASSES[attacker["class"]]["emoji"]
    d_emoji = CLASSES[defender["class"]]["emoji"]
    result = f"{a_emoji} *{attacker['name']}* ⚔️ {d_emoji} *{defender['name']}*\n💥 Урон: {dmg}\n❤️ HP {defender['name']}: {defender['hp']}/{defender['max_hp']}\n✨ +{exp_gain} опыта | 💰 +{gold_gain} золота"
    if defender["hp"] == 0:
        bonus = random.randint(20, 40)
        attacker["gold"] += bonus
        set_player(update.effective_chat.id, update.effective_user.id, attacker)
        result += f"\n\n💀 *{defender['name']}* повержен! (+{bonus}💰)"
    if leveled:
        result += f"\n\n🎉 *УРОВЕНЬ {attacker['level']}!*"
    await update.message.reply_text(result, parse_mode="Markdown")

async def cmd_hit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    gid = str(update.effective_chat.id)
    uid = str(update.effective_user.id)
    p = get_player(update.effective_chat.id, update.effective_user.id)
    if not p:
        await update.message.reply_text("❌ Создайте персонажа", parse_mode="Markdown")
        return
    if gid not in pve_state or not pve_state[gid]["active"]:
        await update.message.reply_text("❌ Нет активных монстров!")
        return
    if uid in pve_state[gid]["attackers"]:
        await update.message.reply_text("⏳ Вы уже атаковали этого монстра!")
        return
    monster = pve_state[gid]["monster"]
    eff = get_effective_stats(p)
    dmg = random.randint(eff["attack"] - 3, eff["attack"] + 5)
    monster["hp"] -= dmg
    pve_state[gid]["attackers"].append(uid)
    m_dmg = max(1, random.randint(monster["attack"] - 4, monster["attack"] + 2) - random.randint(0, eff["defense"] // 3))
    p["hp"] = max(1, p["hp"] - m_dmg)
    result = f"{CLASSES[p['class']]['emoji']} *{p['name']}* атакует {monster['emoji']} *{monster['name']}*\n💥 -{dmg} HP | ❤️ Монстр: {max(0, monster['hp'])}\n💢 *{monster['name']}* бьёт в ответ! -{m_dmg} HP"
    if monster["hp"] <= 0:
        monster["hp"] = 0
        p["exp"] += monster["exp"]
        p["gold"] += monster["gold"]
        pve_state[gid]["active"] = False
        drop_text = ""
        if random.random() < 0.3:
            drop = random.choice([{"name": "зелье лечения", "type": "зелье"}, {"name": "свиток усиления", "type": "свиток"}])
            p["inventory"].append(drop)
            drop_text = f"\n🎁 Дроп: *{drop['name']}*!"
        result += f"\n\n🎉 *МОНСТР ПОВЕРЖЕН!*\n🏆 +{monster['exp']} опыта | 💰 +{monster['gold']} золота{drop_text}"
    set_player(update.effective_chat.id, update.effective_user.id, p)
    if monster["hp"] > 0:
        pve_state[gid]["monster"] = monster
    await update.message.reply_text(result, parse_mode="Markdown")

async def cmd_monster(update: Update, context: ContextTypes.DEFAULT_TYPE):
    gid = str(update.effective_chat.id)
    if gid in pve_state and pve_state[gid]["active"]:
        m = pve_state[gid]["monster"]
        await update.message.reply_text(
            f"{m['emoji']} *{m['name']}*\n❤️ HP: {m['hp']}\n⚔️ Атака: {m['attack']} | 🛡️ Защита: {m['defense']}\n👥 Атаковало: {len(pve_state[gid]['attackers'])}\n\n`/hit` — атаковать!",
            parse_mode="Markdown"
        )
    else:
        await update.message.reply_text("🎋 Монстров нет.")

async def cmd_heal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    p = get_player(update.effective_chat.id, update.effective_user.id)
    if not p:
        await update.message.reply_text("❌ Создайте персонажа", parse_mode="Markdown")
        return
    for i, item in enumerate(p["inventory"]):
        if "зелье" in item["name"].lower():
            p["inventory"].pop(i)
            heal = random.randint(25, 45)
            p["hp"] = min(p["max_hp"], p["hp"] + heal)
            set_player(update.effective_chat.id, update.effective_user.id, p)
            await update.message.reply_text(f"🧪 Использовано зелье! +{heal} HP\n❤️ HP: {p['hp']}/{p['max_hp']}")
            return
    heal = random.randint(10, 20)
    p["hp"] = min(p["max_hp"], p["hp"] + heal)
    set_player(update.effective_chat.id, update.effective_user.id, p)
    await update.message.reply_text(f"💚 *{p['name']}* отдыхает. +{heal} HP\n❤️ HP: {p['hp']}/{p['max_hp']}", parse_mode="Markdown")

async def cmd_top(update: Update, context: ContextTypes.DEFAULT_TYPE):
    gp = players.get(str(update.effective_chat.id), {})
    if not gp:
        await update.message.reply_text("Нет персонажей!")
        return
    sp = sorted(gp.items(), key=lambda x: (x[1]["level"], x[1]["exp"]), reverse=True)[:10]
    text = "🏆 *Рейтинг:*\n\n"
    medals = ["🥇", "🥈", "🥉"] + ["  "] * 7
    for i, (uid, p) in enumerate(sp):
        text += f"{medals[i]}{CLASSES[p['class']]['emoji']} *{p['name']}* — Ур.{p['level']} | ❤️{p['hp']}/{p['max_hp']} | 💰{p['gold']}\n"
    await update.message.reply_text(text, parse_mode="Markdown")

async def cmd_reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    gid = str(update.effective_chat.id)
    uid = str(update.effective_user.id)
    if gid in players and uid in players[gid]:
        del players[gid][uid]
        save_json(PLAYERS_FILE, players)
        await update.message.reply_text("🗑️ Персонаж удалён.")
    else:
        await update.message.reply_text("У вас нет персонажа.")

async def pve_callback(context: ContextTypes.DEFAULT_TYPE):
    for gid_str in list(players.keys()):
        if gid_str not in pve_state or not pve_state[gid_str]["active"]:
            m = random.choice(MONSTERS).copy()
            gp = players.get(gid_str, {})
            if gp:
                avg = sum(p["level"] for p in gp.values()) / len(gp)
                scale = 1 + (avg - 1) * 0.3
                m["hp"] = int(m["hp"] * scale)
                m["attack"] = int(m["attack"] * scale)
                m["exp"] = int(m["exp"] * scale)
                m["gold"] = int(m["gold"] * scale)
            pve_state[gid_str] = {"monster": m, "active": True, "attackers": [], "last_pve": datetime.now()}
            try:
                await context.bot.send_message(
                    int(gid_str),
                    f"⚠️ *Вторжение!* {m['emoji']} *{m['name']}*!\n❤️ HP: {m['hp']} | ⚔️ Атака: {m['attack']}\n💥 `/hit` — атаковать!",
                    parse_mode="Markdown"
                )
            except:
                pass

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print(f"Ошибка: {context.error}")

def main():
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("create", cmd_create))
    app.add_handler(CommandHandler("stats", cmd_stats))
    app.add_handler(CommandHandler("inv", cmd_inv))
    app.add_handler(CommandHandler("shop", cmd_shop))
    app.add_handler(CommandHandler("buy", cmd_buy))
    app.add_handler(CommandHandler("equip", cmd_equip))
    app.add_handler(CommandHandler("attack", cmd_attack))
    app.add_handler(CommandHandler("hit", cmd_hit))
    app.add_handler(CommandHandler("monster", cmd_monster))
    app.add_handler(CommandHandler("heal", cmd_heal))
    app.add_handler(CommandHandler("top", cmd_top))
    app.add_handler(CommandHandler("reset", cmd_reset))

    app.job_queue.run_repeating(pve_callback, interval=PVE_INTERVAL, first=10)
    app.add_error_handler(error_handler)

    print("РПГ-бот v2.0 запущен!")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
