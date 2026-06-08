import asyncio
import random
import json
import os
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor
from aiogram.contrib.fsm_storage.memory import MemoryStorage

# ---------- НАСТРОЙКИ ----------
TOKEN = "8350483157:AAGn8MgX8W5FJwZvB6ptvKSXrGVUarHXbZA"
PVE_INTERVAL = 3 * 3600  # 3 часа в секундах

bot = Bot(token=TOKEN)
dp = Dispatcher(bot, storage=MemoryStorage())

# ---------- ДАННЫЕ ----------
PLAYERS_FILE = "players.json"
MONSTERS_FILE = "monsters.json"

CLASSES = {
    "воин":  {"hp": 120, "attack": 15, "defense": 10, "emoji": "⚔️", "weapon": "ржавый меч", "armor": "кожаная броня"},
    "маг":   {"hp": 80,  "attack": 25, "defense": 4,  "emoji": "🔮", "weapon": "деревянный посох", "armor": "тканевая роба"},
    "лучник":{"hp": 90,  "attack": 18, "defense": 6,  "emoji": "🏹", "weapon": "короткий лук", "armor": "стеганый доспех"},
}

WEAPONS = {
    "ржавый меч":      {"attack": 0,  "price": 0,   "desc": "Стартовое оружие воина"},
    "деревянный посох": {"attack": 0,  "price": 0,   "desc": "Стартовое оружие мага"},
    "короткий лук":     {"attack": 0,  "price": 0,   "desc": "Стартовое оружие лучника"},
    "стальной меч":     {"attack": 8,  "price": 120, "desc": "+8 к атаке, только для воинов", "class": "воин"},
    "двуручный топор":  {"attack": 12, "price": 200, "desc": "+12 к атаке, -3 к защите, только для воинов", "class": "воин", "defense_penalty": 3},
    "магический жезл":  {"attack": 10, "price": 150, "desc": "+10 к атаке, только для магов", "class": "маг"},
    "посох стихий":     {"attack": 14, "price": 250, "desc": "+14 к атаке, только для магов", "class": "маг"},
    "длинный лук":      {"attack": 9,  "price": 130, "desc": "+9 к атаке, только для лучников", "class": "лучник"},
    "арбалет":          {"attack": 11, "price": 180, "desc": "+11 к атаке, только для лучников", "class": "лучник"},
}

ARMORS = {
    "кожаная броня":    {"defense": 0, "price": 0,   "desc": "Стартовая броня"},
    "тканевая роба":    {"defense": 0, "price": 0,   "desc": "Стартовая броня"},
    "стеганый доспех":  {"defense": 0, "price": 0,   "desc": "Стартовая броня"},
    "кольчуга":         {"defense": 6, "price": 100, "desc": "+6 к защите"},
    "латный доспех":    {"defense": 10,"price": 220, "desc": "+10 к защите, -2 к атаке", "attack_penalty": 2},
    "магическая мантия":{"defense": 5, "price": 140, "desc": "+5 к защите, +3 к атаке для магов", "attack_bonus": 3, "class": "маг"},
    "эльфийский плащ":  {"defense": 7, "price": 160, "desc": "+7 к защите, +2 к атаке для лучников", "attack_bonus": 2, "class": "лучник"},
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

# Загрузка/сохранение
def load_json(path):
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

players = load_json(PLAYERS_FILE)  # {group_id: {user_id: {данные}}}

# Состояние PvE для каждой группы
pve_state = {}  # {group_id: {"monster": {...}, "active": bool, "last_pve": datetime}}

# ---------- ИНВЕНТАРЬ И СТАТЫ ----------

def get_effective_stats(player):
    """Считает статы с учётом экипировки"""
    weapon = WEAPONS.get(player.get("weapon", ""), {"attack": 0, "defense_penalty": 0})
    armor = ARMORS.get(player.get("armor", ""), {"defense": 0, "attack_penalty": 0, "attack_bonus": 0})

    base_attack = player["attack"]
    base_defense = player["defense"]

    # Оружие
    bonus_attack = weapon.get("attack", 0)
    defense_from_weapon = weapon.get("defense_penalty", 0)

    # Броня
    bonus_defense = armor.get("defense", 0)
    attack_penalty = armor.get("attack_penalty", 0)
    attack_bonus = armor.get("attack_bonus", 0)

    return {
        "attack": base_attack + bonus_attack + attack_bonus - attack_penalty,
        "defense": base_defense + bonus_defense - defense_from_weapon
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

# ---------- КОМАНДЫ СОЗДАНИЯ И ИНФО ----------

@dp.message_handler(commands=['start'], chat_type=[types.ChatType.GROUP, types.ChatType.SUPERGROUP])
async def cmd_start(message: types.Message):
    await message.reply(
        "🎲 *РПГ-бот v2.0*\n\n"
        "*Персонаж:*\n"
        "`!создать [имя] [класс]` — создать персонажа\n"
        "`!перс` — посмотреть персонажа\n"
        "`!сброс` — удалить персонажа\n\n"
        "*Бой:*\n"
        "`!attack` (ответом) — PvP против игрока\n"
        "`!удар` — атаковать PvE-монстра\n\n"
        "*Инвентарь:*\n"
        "`!инв` — инвентарь и золото\n"
        "`!магазин` — купить снаряжение\n"
        "`!купить [номер]` — купить предмет из магазина\n"
        "`!экип [номер]` — надеть предмет\n\n"
        "*Рейтинг:*\n"
        "`!топ` — топ игроков\n"
        "`!лечить` — восстановить HP",
        parse_mode="Markdown"
    )

@dp.message_handler(commands=['создать'], chat_type=[types.ChatType.GROUP, types.ChatType.SUPERGROUP])
async def cmd_create(message: types.Message):
    args = message.get_args().split()
    if len(args) < 2:
        await message.reply("❌ `!создать Имя класс`\nКлассы: воин, маг, лучник", parse_mode="Markdown")
        return

    name = args[0]
    cls = args[1].lower()
    if cls not in CLASSES:
        await message.reply("❌ Неизвестный класс. Доступны: воин, маг, лучник")
        return

    if get_player(message.chat.id, message.from_user.id):
        await message.reply("❌ Уже есть персонаж. `!сброс` для удаления.", parse_mode="Markdown")
        return

    base = CLASSES[cls]
    player_data = {
        "name": name,
        "class": cls,
        "hp": base["hp"],
        "max_hp": base["hp"],
        "attack": base["attack"],
        "defense": base["defense"],
        "level": 1,
        "exp": 0,
        "gold": 0,
        "weapon": base["weapon"],
        "armor": base["armor"],
        "inventory": [],
        "pve_attacks": 0,
    }
    set_player(message.chat.id, message.from_user.id, player_data)
    eff = get_effective_stats(player_data)

    await message.reply(
        f"{base['emoji']} *{name}* — {cls.capitalize()}!\n"
        f"❤️ HP: {base['hp']}/{base['hp']}\n"
        f"⚔️ Атака: {eff['attack']} | 🛡️ Защита: {eff['defense']}\n"
        f"🗡️ Оружие: {base['weapon']}\n"
        f"🛡️ Броня: {base['armor']}\n"
        f"⭐ Уровень: 1 | 💰 0 золота",
        parse_mode="Markdown"
    )

@dp.message_handler(commands=['перс'], chat_type=[types.ChatType.GROUP, types.ChatType.SUPERGROUP])
async def cmd_stats(message: types.Message):
    p = get_player(message.chat.id, message.from_user.id)
    if not p:
        await message.reply("❌ Создайте персонажа: `!создать Имя класс`", parse_mode="Markdown")
        return

    eff = get_effective_stats(p)
    emoji = CLASSES[p["class"]]["emoji"]
    to_next = exp_to_level(p["level"]) - p["exp"]

    weapon_bonus = WEAPONS.get(p["weapon"], {}).get("attack", 0)
    armor_bonus = ARMORS.get(p["armor"], {}).get("defense", 0)

    await message.reply(
        f"{emoji} *{p['name']}* — {p['class'].capitalize()} | Ур. {p['level']}\n"
        f"❤️ HP: {p['hp']}/{p['max_hp']}\n"
        f"⚔️ Атака: {eff['attack']} (база {p['attack']} +{weapon_bonus} оружие)\n"
        f"🛡️ Защита: {eff['defense']} (база {p['defense']} +{armor_bonus} броня)\n"
        f"🗡️ Оружие: {p['weapon']}\n"
        f"🛡️ Броня: {p['armor']}\n"
        f"✨ Опыт: {p['exp']}/{exp_to_level(p['level'])} | 💰 Золото: {p['gold']}\n"
        f"🎒 Предметов: {len(p['inventory'])}",
        parse_mode="Markdown"
    )

# ---------- ИНВЕНТАРЬ И МАГАЗИН ----------

@dp.message_handler(commands=['инв'], chat_type=[types.ChatType.GROUP, types.ChatType.SUPERGROUP])
async def cmd_inventory(message: types.Message):
    p = get_player(message.chat.id, message.from_user.id)
    if not p:
        await message.reply("❌ Создайте персонажа: `!создать Имя класс`", parse_mode="Markdown")
        return

    text = f"🎒 *Инвентарь {p['name']}* | 💰 {p['gold']} золота\n\n"
    text += f"🗡️ Оружие: *{p['weapon']}*\n"
    text += f"🛡️ Броня: *{p['armor']}*\n\n"

    if not p["inventory"]:
        text += "Инвентарь пуст."
    else:
        text += "*Предметы в сумке:*\n"
        for i, item in enumerate(p["inventory"], 1):
            text += f"{i}. {item['name']} ({item['type']}) — `!экип {i}`\n"

    await message.reply(text, parse_mode="Markdown")

@dp.message_handler(commands=['магазин'], chat_type=[types.ChatType.GROUP, types.ChatType.SUPERGROUP])
async def cmd_shop(message: types.Message):
    p = get_player(message.chat.id, message.from_user.id)
    if not p:
        await message.reply("❌ Создайте персонажа: `!создать Имя класс`", parse_mode="Markdown")
        return

    player_class = p["class"]
    text = "🏪 *Магазин снаряжения* | `!купить номер`\n\n"
    text += f"💰 Ваше золото: *{p['gold']}*\n\n"

    # Показываем оружие для класса игрока
    text += "*Оружие:*\n"
    shop_items = []
    for name, data in WEAPONS.items():
        if data["price"] == 0:
            continue  # Пропускаем стартовые
        if "class" in data and data["class"] != player_class:
            continue  # Только для нужного класса
        shop_items.append({"name": name, "type": "оружие", "data": data, "price": data["price"], "desc": data["desc"]})
        i = len(shop_items)
        text += f"{i}. {name} — {data['price']}💰 | {data['desc']}\n"

    # Броня (без классовых ограничений, кроме специальных)
    text += "\n*Броня:*\n"
    for name, data in ARMORS.items():
        if data["price"] == 0:
            continue
        if "class" in data and data["class"] != player_class:
            continue
        shop_items.append({"name": name, "type": "броня", "data": data, "price": data["price"], "desc": data["desc"]})
        i = len(shop_items)
        text += f"{i}. {name} — {data['price']}💰 | {data['desc']}\n"

    # Сохраняем магазин для игрока
    p["_shop"] = shop_items
    set_player(message.chat.id, message.from_user.id, p)

    text += "\n`!купить 3` — купить третий предмет"
    await message.reply(text, parse_mode="Markdown")

@dp.message_handler(commands=['купить'], chat_type=[types.ChatType.GROUP, types.ChatType.SUPERGROUP])
async def cmd_buy(message: types.Message):
    p = get_player(message.chat.id, message.from_user.id)
    if not p:
        await message.reply("❌ Создайте персонажа: `!создать Имя класс`", parse_mode="Markdown")
        return

    if "_shop" not in p:
        await message.reply("❌ Сначала откройте магазин: `!магазин`", parse_mode="Markdown")
        return

    try:
        index = int(message.get_args().strip()) - 1
    except:
        await message.reply("❌ `!купить номер` — например `!купить 1`", parse_mode="Markdown")
        return

    if index < 0 or index >= len(p["_shop"]):
        await message.reply("❌ Неверный номер предмета.")
        return

    item = p["_shop"][index]
    if p["gold"] < item["price"]:
        await message.reply(f"❌ Не хватает золота! Нужно {item['price']}, у вас {p['gold']}.")
        return

    p["gold"] -= item["price"]
    p["inventory"].append({"name": item["name"], "type": item["type"]})
    set_player(message.chat.id, message.from_user.id, p)

    await message.reply(f"✅ Куплено: *{item['name']}* за {item['price']}💰\nНадеть: `!экип {len(p['inventory'])}`", parse_mode="Markdown")

@dp.message_handler(commands=['экип'], chat_type=[types.ChatType.GROUP, types.ChatType.SUPERGROUP])
async def cmd_equip(message: types.Message):
    p = get_player(message.chat.id, message.from_user.id)
    if not p:
        await message.reply("❌ Создайте персонажа: `!создать Имя класс`", parse_mode="Markdown")
        return

    try:
        index = int(message.get_args().strip()) - 1
    except:
        await message.reply("❌ `!экип номер` — например `!экип 1`", parse_mode="Markdown")
        return

    if index < 0 or index >= len(p["inventory"]):
        await message.reply("❌ Неверный номер предмета.")
        return

    item = p["inventory"].pop(index)
    item_type = item["type"]
    old_item = None

    # Снимаем старый предмет и кладём в инвентарь
    if item_type == "оружие":
        old_item = {"name": p["weapon"], "type": "оружие"}
        p["weapon"] = item["name"]
    else:
        old_item = {"name": p["armor"], "type": "броня"}
        p["armor"] = item["name"]

    # Стартовые предметы не кладём в инвентарь
    if WEAPONS.get(old_item["name"], {}).get("price", 0) > 0 or ARMORS.get(old_item["name"], {}).get("price", 0) > 0:
        p["inventory"].append(old_item)

    set_player(message.chat.id, message.from_user.id, p)
    eff = get_effective_stats(p)

    await message.reply(
        f"✅ Надето: *{item['name']}*\n"
        f"⚔️ Атака: {eff['attack']} | 🛡️ Защита: {eff['defense']}",
        parse_mode="Markdown"
    )

# ---------- PVP ----------

@dp.message_handler(commands=['attack'], chat_type=[types.ChatType.GROUP, types.ChatType.SUPERGROUP])
async def cmd_attack(message: types.Message):
    attacker = get_player(message.chat.id, message.from_user.id)
    if not attacker:
        await message.reply("❌ Создайте персонажа: `!создать Имя класс`", parse_mode="Markdown")
        return

    if not message.reply_to_message:
        await message.reply("❌ Ответьте на сообщение игрока, которого хотите атаковать!")
        return

    target_user = message.reply_to_message.from_user
    if target_user.id == message.from_user.id:
        await message.reply("🤕 Нельзя атаковать самого себя!")
        return

    defender = get_player(message.chat.id, target_user.id)
    if not defender:
        await message.reply(f"❌ У {target_user.first_name} нет персонажа!")
        return

    a_eff = get_effective_stats(attacker)
    d_eff = get_effective_stats(defender)

    base_dmg = random.randint(a_eff["attack"] - 3, a_eff["attack"] + 5)
    dmg_reduction = random.randint(0, d_eff["defense"] // 2)
    dmg = max(1, base_dmg - dmg_reduction)

    defender["hp"] -= dmg
    if defender["hp"] < 0:
        defender["hp"] = 0

    exp_gain = random.randint(10, 25)
    attacker["exp"] += exp_gain
    gold_gain = random.randint(5, 15)
    attacker["gold"] += gold_gain

    leveled_up = False
    while attacker["exp"] >= exp_to_level(attacker["level"]):
        attacker["exp"] -= exp_to_level(attacker["level"])
        attacker["level"] += 1
        attacker["max_hp"] += 15
        attacker["hp"] = attacker["max_hp"]
        attacker["attack"] += random.randint(2, 5)
        attacker["defense"] += random.randint(1, 3)
        leveled_up = True

    set_player(message.chat.id, target_user.id, defender)
    set_player(message.chat.id, message.from_user.id, attacker)

    a_emoji = CLASSES[attacker["class"]]["emoji"]
    d_emoji = CLASSES[defender["class"]]["emoji"]
    result = (
        f"{a_emoji} *{attacker['name']}* ⚔️ {d_emoji} *{defender['name']}*\n"
        f"💥 Урон: {dmg}\n"
        f"❤️ HP {defender['name']}: {defender['hp']}/{defender['max_hp']}\n"
        f"✨ +{exp_gain} опыта | 💰 +{gold_gain} золота"
    )

    if defender["hp"] == 0:
        result += f"\n\n💀 *{defender['name']}* повержен!"
        bonus = random.randint(20, 40)
        attacker["gold"] += bonus
        set_player(message.chat.id, message.from_user.id, attacker)
        result += f" (+{bonus}💰)"

    if leveled_up:
        result += f"\n\n🎉 *УРОВЕНЬ {attacker['level']}!*"

    await message.reply(result, parse_mode="Markdown")

# ---------- PVE ----------

def spawn_pve_event(group_id):
    """Создаёт случайного монстра для группы"""
    monster = random.choice(MONSTERS).copy()
    # Масштабируем под средний уровень группы
    group_players = players.get(str(group_id), {})
    if group_players:
        avg_level = sum(p["level"] for p in group_players.values()) / len(group_players)
        scale = 1 + (avg_level - 1) * 0.3
        monster["hp"] = int(monster["hp"] * scale)
        monster["attack"] = int(monster["attack"] * scale)
        monster["exp"] = int(monster["exp"] * scale)
        monster["gold"] = int(monster["gold"] * scale)

    pve_state[str(group_id)] = {
        "monster": monster,
        "active": True,
        "last_pve": datetime.now(),
        "attackers": [],  # кто уже атаковал
    }
    return monster

@dp.message_handler(commands=['удар'], chat_type=[types.ChatType.GROUP, types.ChatType.SUPERGROUP])
async def cmd_pve_attack(message: types.Message):
    gid = str(message.chat.id)
    uid = str(message.from_user.id)

    p = get_player(message.chat.id, message.from_user.id)
    if not p:
        await message.reply("❌ Создайте персонажа: `!создать Имя класс`", parse_mode="Markdown")
        return

    if gid not in pve_state or not pve_state[gid]["active"]:
        await message.reply("❌ Сейчас нет активных монстров! Ждите следующего вторжения.")
        return

    if uid in pve_state[gid]["attackers"]:
        await message.reply("⏳ Вы уже атаковали этого монстра! Ждите следующего хода.")
        return

    monster = pve_state[gid]["monster"]
    eff = get_effective_stats(p)

    # Удар игрока по монстру
    dmg = random.randint(eff["attack"] - 3, eff["attack"] + 5)
    monster["hp"] -= dmg
    pve_state[gid]["attackers"].append(uid)
    p["pve_attacks"] += 1

    result = f"{CLASSES[p['class']]['emoji']} *{p['name']}* атакует {monster['emoji']} *{monster['name']}*\n💥 -{dmg} HP | ❤️ Монстр: {max(0, monster['hp'])}/{monster.get('max_hp', monster['hp'] + dmg)}"

    # Монстр контратакует
    m_dmg = random.randint(monster["attack"] - 4, monster["attack"] + 2)
    m_reduction = random.randint(0, eff["defense"] // 3)
    m_dmg = max(1, m_dmg - m_reduction)
    p["hp"] -= m_dmg
    result += f"\n💢 *{monster['name']}* бьёт в ответ! -{m_dmg} HP"

    if p["hp"] <= 0:
        p["hp"] = 1
        result += "\n😵 Вы на грани смерти!"

    # Проверка, убит ли монстр
    if monster["hp"] <= 0:
        monster["hp"] = 0
        killer_exp = monster["exp"]
        killer_gold = monster["gold"]

        p["exp"] += killer_exp
        p["gold"] += killer_gold

        # Шанс на дроп предмета
        drop_text = ""
        if random.random() < 0.3:
            drop_item = random.choice([
                {"name": "зелье лечения", "type": "зелье"},
                {"name": "свиток усиления", "type": "свиток"},
            ])
            p["inventory"].append(drop_item)
            drop_text = f"\n🎁 Дроп: *{drop_item['name']}*!"

        pve_state[gid]["active"] = False

        leveled_up = False
        while p["exp"] >= exp_to_level(p["level"]):
            p["exp"] -= exp_to_level(p["level"])
            p["level"] += 1
            p["max_hp"] += 15
            p["hp"] = p["max_hp"]
            p["attack"] += random.randint(2, 5)
            p["defense"] += random.randint(1, 3)
            leveled_up = True

        result += (
            f"\n\n🎉 *МОНСТР ПОВЕРЖЕН!*\n"
            f"🏆 +{killer_exp} опыта | 💰 +{killer_gold} золота"
            f"{drop_text}"
        )
        if leveled_up:
            result += f"\n🎉 *УРОВЕНЬ {p['level']}!*"

    set_player(message.chat.id, message.from_user.id, p)

    # Обновляем pve_state только если монстр ещё жив
    if monster["hp"] > 0:
        pve_state[gid]["monster"] = monster

    await message.reply(result, parse_mode="Markdown")

@dp.message_handler(commands=['монстр'], chat_type=[types.ChatType.GROUP, types.ChatType.SUPERGROUP])
async def cmd_monster_info(message: types.Message):
    gid = str(message.chat.id)
    if gid in pve_state and pve_state[gid]["active"]:
        m = pve_state[gid]["monster"]
        attackers_count = len(pve_state[gid]["attackers"])
        await message.reply(
            f"{m['emoji']} *{m['name']}* угрожает группе!\n"
            f"❤️ HP: {m['hp']}\n"
            f"⚔️ Атака: {m['attack']} | 🛡️ Защита: {m['defense']}\n"
            f"👥 Атаковало игроков: {attackers_count}\n\n"
            f"`!удар` — атаковать монстра!",
            parse_mode="Markdown"
        )
    else:
        await message.reply("🎋 В округе тихо. Монстров нет.")

# ---------- ПРОЧИЕ КОМАНДЫ ----------

@dp.message_handler(commands=['лечить'], chat_type=[types.ChatType.GROUP, types.ChatType.SUPERGROUP])
async def cmd_heal(message: types.Message):
    p = get_player(message.chat.id, message.from_user.id)
    if not p:
        await message.reply("❌ Создайте персонажа: `!создать Имя класс`", parse_mode="Markdown")
        return

    # Ищем зелья в инвентаре
    potion_index = None
    for i, item in enumerate(p["inventory"]):
        if "зелье" in item["name"].lower():
            potion_index = i
            break

    if potion_index is not None:
        p["inventory"].pop(potion_index)
        heal = random.randint(25, 45)
        p["hp"] = min(p["max_hp"], p["hp"] + heal)
        set_player(message.chat.id, message.from_user.id, p)
        await message.reply(f"🧪 Использовано зелье! +{heal} HP\n❤️ HP: {p['hp']}/{p['max_hp']}")
    else:
        heal = random.randint(10, 20)
        p["hp"] = min(p["max_hp"], p["hp"] + heal)
        set_player(message.chat.id, message.from_user.id, p)
        await message.reply(f"💚 *{p['name']}* отдыхает у костра. +{heal} HP\n❤️ HP: {p['hp']}/{p['max_hp']}", parse_mode="Markdown")

@dp.message_handler(commands=['топ'], chat_type=[types.ChatType.GROUP, types.ChatType.SUPERGROUP])
async def cmd_top(message: types.Message):
    group_players = players.get(str(message.chat.id), {})
    if not group_players:
        await message.reply("В этой группе ещё нет персонажей!")
        return

    sorted_players = sorted(
        group_players.items(),
        key=lambda x: (x[1]["level"], x[1]["exp"]),
        reverse=True
    )[:10]

    text = "🏆 *Рейтинг игроков:*\n\n"
    medals = ["🥇", "🥈", "🥉"] + ["  "] * 7
    for i, (uid, p) in enumerate(sorted_players):
        try:
            member = await bot.get_chat_member(message.chat.id, int(uid))
            name = member.user.first_name
        except:
            name = p["name"]
        emoji = CLASSES[p["class"]]["emoji"]
        text += f"{medals[i]}{emoji} *{name}* — Ур.{p['level']} | ❤️{p['hp']}/{p['max_hp']} | 💰{p['gold']}\n"

    await message.reply(text, parse_mode="Markdown")

@dp.message_handler(commands=['сброс'], chat_type=[types.ChatType.GROUP, types.ChatType.SUPERGROUP])
async def cmd_reset(message: types.Message):
    gid = str(message.chat.id)
    uid = str(message.from_user.id)
    if gid in players and uid in players[gid]:
        del players[gid][uid]
        save_json(PLAYERS_FILE, players)
        await message.reply("🗑️ Персонаж удалён.")
    else:
        await message.reply("У вас нет персонажа.")

# ---------- PVE ТАЙМЕР ----------

async def pve_scheduler():
    """Фоновый цикл: каждые 3 часа спавнит монстра во всех группах"""
    await bot.send_message
    while True:
        await asyncio.sleep(60)  # Проверяем каждую минуту
        now = datetime.now()
        for gid_str in list(players.keys()):
            try:
                gid = int(gid_str)
            except:
                continue

            # Если нет активного PvE и прошло 3 часа с последнего
            if gid_str not in pve_state or not pve_state[gid_str]["active"]:
                last = pve_state.get(gid_str, {}).get("last_pve", datetime.min)
                if (now - last).total_seconds() >= PVE_INTERVAL:
                    monster = spawn_pve_event(gid)
                    try:
                        await bot.send_message(
                            gid,
                            f"⚠️ *Вторжение!* {monster['emoji']} *{monster['name']}* приближается!\n"
                            f"❤️ HP: {monster['hp']} | ⚔️ Атака: {monster['attack']} | 🛡️ Защита: {monster['defense']}\n"
                            f"💥 `!удар` — атаковать!\n`!монстр` — проверить статус",
                            parse_mode="Markdown"
                        )
                    except Exception as e:
                        print(f"Не удалось отправить PvE в группу {gid}: {e}")
                        # Бот мог быть удалён из группы
                        pass

# ---------- ЗАПУСК ----------
if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.create_task(pve_scheduler())
    print("🔥 РПГ-бот v2.0 запущен!")
    executor.start_polling(dp, skip_updates=True)
