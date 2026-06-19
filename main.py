"""
Raja Rani Chor Sipahi - Telegram Bot
Owner  : @xdsonic
Channel: @nexushubxd
"""

import asyncio
import random
import sqlite3
import os
import logging
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, ContextTypes
)
from telegram.constants import ParseMode

logging.basicConfig(format="%(asctime)s | %(levelname)s | %(message)s", level=logging.INFO)
log = logging.getLogger(__name__)

load_dotenv()
BOT_TOKEN    = os.getenv("BOT_TOKEN", "")
WEBHOOK_URL  = os.getenv("WEBHOOK_URL", "")
PORT         = int(os.getenv("PORT", 8080))
OWNER        = "@xdsonic"
CHANNEL      = "@nexushubxd"
CHANNEL_LINK = "https://t.me/nexushubxd"

ROLES  = ["Raja", "Rani", "Chor", "Sipahi"]
EMOJI  = {"Raja": "👑", "Rani": "👸", "Chor": "🦹", "Sipahi": "👮"}
POINTS = {"Raja": 1000, "Rani": 500, "Sipahi": 300, "Chor": 0}

# Robot personalities
BOT_NAMES = ["Ali 🤖", "Sara 🤖", "Zain 🤖", "Hina 🤖", "Umar 🤖", "Nida 🤖"]

games: dict = {}

def fresh_game(mode="friends"):
    return {
        "phase":        "joining",
        "mode":         mode,   # friends | robot
        "players":      [],
        "roles":        {},
        "raja_id":      None,
        "sipahi_id":    None,
        "chor_id":      None,
        "join_msg_id":  None,
        "guess_msg_id": None,
    }

# --- SQLite ---
DB = "scores.db"

def db_init():
    con = sqlite3.connect(DB)
    con.execute("""
        CREATE TABLE IF NOT EXISTS scores (
            user_id INTEGER, chat_id INTEGER,
            name TEXT, username TEXT DEFAULT '',
            points INTEGER DEFAULT 0, games INTEGER DEFAULT 0, wins INTEGER DEFAULT 0,
            PRIMARY KEY(user_id, chat_id)
        )
    """)
    con.commit(); con.close()

def db_add(chat_id, user_id, name, username, pts, won=False):
    con = sqlite3.connect(DB)
    con.execute("""
        INSERT INTO scores(user_id,chat_id,name,username,points,games,wins)
        VALUES(?,?,?,?,?,1,?)
        ON CONFLICT(user_id,chat_id) DO UPDATE SET
        points=points+excluded.points, games=games+1,
        wins=wins+excluded.wins, name=excluded.name, username=excluded.username
    """, (user_id, chat_id, name, username, pts, 1 if won else 0))
    con.commit(); con.close()

def db_top(chat_id):
    con = sqlite3.connect(DB)
    rows = con.execute("""
        SELECT name,username,points,games,wins FROM scores
        WHERE chat_id=? ORDER BY points DESC LIMIT 10
    """, (chat_id,)).fetchall()
    con.close(); return rows

def db_me(chat_id, user_id):
    con = sqlite3.connect(DB)
    row = con.execute(
        "SELECT name,points,games,wins FROM scores WHERE chat_id=? AND user_id=?",
        (chat_id, user_id)
    ).fetchone()
    rank = con.execute("""
        SELECT COUNT(*)+1 FROM scores WHERE chat_id=? AND points>(
            SELECT COALESCE(points,0) FROM scores WHERE chat_id=? AND user_id=?)
    """, (chat_id, chat_id, user_id)).fetchone()[0]
    con.close(); return row, rank

# --- Channel Check ---
async def is_member(bot, user_id):
    try:
        m = await bot.get_chat_member(CHANNEL, user_id)
        return m.status.name not in ("LEFT","BANNED","RESTRICTED")
    except:
        return False

def channel_kb():
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("📢 Channel Join Karo", url=CHANNEL_LINK),
        InlineKeyboardButton("✅ Joined!", callback_data="check_join"),
    ]])

def mention(name, uid):
    # Safe mention using HTML
    return f'<a href="tg://user?id={uid}">{name}</a>'

def join_text(game):
    count = len(game["players"])
    bar   = "🟩" * count + "⬜" * (4 - count)
    plist = "\n".join(f"  • {p['name']}" for p in game["players"])
    need  = f"{4-count} aur chahiye!" if count < 4 else "Sab aa gaye! Starting..."
    mode_badge = "👥 Friends Mode" if game["mode"] == "friends" else "🤖 Robot Mode"
    return (
        f"🎮 <b>Raja Rani Chor Sipahi</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"{mode_badge}\n"
        f"Players: {bar} <b>{count}/4</b>\n\n"
        f"{plist or '<i>Abhi koi nahi...</i>'}\n\n"
        f"⏳ {need}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📢 {CHANNEL_LINK} | 👤 {OWNER}"
    )

def join_kb():
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("✋ Join Game", callback_data="join_game")
    ]])

def mode_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("👥 Play with Friends", callback_data="mode_friends")],
        [InlineKeyboardButton("🤖 Play with Robots",  callback_data="mode_robot")],
    ])

# ═══════════════════════════════════════
#  /start
# ═══════════════════════════════════════
async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    text = (
        f"👋 <b>Assalam o Alaikum, {user.first_name}!</b>\n\n"
        f"🎮 Main hoon <b>Raja Rani Chor Sipahi Bot!</b>\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"<b>Kaise khelen?</b>\n"
        f"1️⃣ Apne group mein /startgame likho\n"
        f"2️⃣ Mode chunao — Friends ya Robot\n"
        f"3️⃣ Players join karen\n"
        f"4️⃣ Khel shuru!\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"<b>Roles:</b>\n"
        f"👑 Raja = 1000 pts\n"
        f"👸 Rani = 500 pts\n"
        f"👮 Sipahi = 300 pts\n"
        f"🦹 Chor = 0 pts\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📢 {CHANNEL_LINK}\n"
        f"👤 Owner: {OWNER}"
    )
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Group mein Add Karo", url="https://t.me/Sonicdmbot?startgroup=true")],
        [InlineKeyboardButton("📢 Channel Join Karo", url=CHANNEL_LINK)],
        [InlineKeyboardButton("❓ Help", callback_data="show_help")],
    ])
    await update.message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=kb, disable_web_page_preview=True)

# ═══════════════════════════════════════
#  /help
# ═══════════════════════════════════════
async def cmd_help(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text = (
        "🎮 <b>Raja Rani Chor Sipahi — Help</b>\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "<b>Commands:</b>\n"
        "🟢 /startgame — Naya game shuru karo\n"
        "✋ /join — Game mein shamil ho\n"
        "🏆 /leaderboard — Top 10 scores\n"
        "📊 /myscore — Apna score dekho\n"
        "❓ /help — Ye message\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "<b>2 Modes hain:</b>\n\n"
        "👥 <b>Play with Friends</b>\n"
        "   4 real players join karte hain\n\n"
        "🤖 <b>Play with Robots</b>\n"
        "   Akele khelo! 3 AI robots saath honge\n"
        "   Robots khud apni chaalein chalenge!\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "<b>Points:</b>\n"
        "👑 Raja = 1000 | 👸 Rani = 500\n"
        "👮 Sipahi = 300 | 🦹 Chor = 0\n\n"
        "<b>Twist:</b> Sipahi galat pakde toh\n"
        "Chor +300, Sipahi = 0!\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"📢 {CHANNEL_LINK} | 👤 {OWNER}"
    )
    await update.message.reply_text(text, parse_mode=ParseMode.HTML, disable_web_page_preview=True)

async def cb_show_help(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    cb = update.callback_query
    await cb.answer()
    text = (
        "🎮 <b>Raja Rani Chor Sipahi — Help</b>\n\n"
        "👥 <b>Friends Mode:</b> 4 real players\n"
        "🤖 <b>Robot Mode:</b> Akele + 3 AI robots\n\n"
        "<b>Commands:</b>\n"
        "/startgame /join /leaderboard /myscore\n\n"
        "<b>Points:</b>\n"
        "👑 Raja=1000 | 👸 Rani=500\n"
        "👮 Sipahi=300 | 🦹 Chor=0\n\n"
        f"📢 {CHANNEL_LINK} | 👤 {OWNER}"
    )
    await cb.edit_message_text(text, parse_mode=ParseMode.HTML, disable_web_page_preview=True)

async def cb_check_join(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    cb = update.callback_query
    if await is_member(ctx.bot, cb.from_user.id):
        await cb.answer("✅ Shukriya! Ab game khelo.", show_alert=True)
        await cb.message.delete()
    else:
        await cb.answer("❌ Abhi tak join nahi kiya!", show_alert=True)

# ═══════════════════════════════════════
#  /startgame
# ═══════════════════════════════════════
async def cmd_startgame(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user

    if chat.type == "private":
        await update.message.reply_text("⚠️ Ye command sirf groups mein kaam karti hai!")
        return

    if not await is_member(ctx.bot, user.id):
        await update.message.reply_text(
            f"⚠️ <b>Pehle hamara channel join karo!</b>\n{CHANNEL_LINK}",
            parse_mode=ParseMode.HTML, reply_markup=channel_kb(), disable_web_page_preview=True)
        return

    cid = chat.id
    if cid in games and games[cid]["phase"] != "done":
        await update.message.reply_text("⚠️ Ek game pehle se chal rahi hai! /join karo.")
        return

    await update.message.reply_text(
        "🎮 <b>Game Mode Chunao!</b>\n\n"
        "👥 <b>Play with Friends</b>\n"
        "   4 real players join karen\n\n"
        "🤖 <b>Play with Robots</b>\n"
        "   Akele khelo, 3 AI robots saath honge!\n"
        "   Bilkul real feel aayega! 😄",
        parse_mode=ParseMode.HTML,
        reply_markup=mode_kb()
    )

# ═══════════════════════════════════════
#  Mode selection callbacks
# ═══════════════════════════════════════
async def cb_mode(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    cb   = update.callback_query
    mode = "friends" if cb.data == "mode_friends" else "robot"
    cid  = cb.message.chat.id
    user = cb.from_user

    await cb.answer()

    if cid in games and games[cid]["phase"] != "done":
        await cb.answer("Game pehle se chal rahi hai!", show_alert=True)
        return

    games[cid] = fresh_game(mode)
    g = games[cid]
    g["players"].append({
        "id": user.id,
        "name": user.full_name,
        "username": user.username or "",
        "is_bot": False,
    })

    if mode == "robot":
        # Add 3 robot players
        bots = random.sample(BOT_NAMES, 3)
        for i, bname in enumerate(bots):
            g["players"].append({
                "id": -(i+1),   # negative IDs for bots
                "name": bname,
                "username": "",
                "is_bot": True,
            })
        await cb.edit_message_text(
            join_text(g), parse_mode=ParseMode.HTML, disable_web_page_preview=True
        )
        # Auto start immediately
        await _start_round(cid, ctx)
    else:
        sent = await cb.edit_message_text(
            join_text(g), parse_mode=ParseMode.HTML,
            reply_markup=join_kb(), disable_web_page_preview=True
        )
        g["join_msg_id"] = cb.message.message_id

# ═══════════════════════════════════════
#  /join
# ═══════════════════════════════════════
async def cmd_join(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await _do_join(update.effective_chat.id, update.effective_user, ctx, update)

async def cb_join(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    cb = update.callback_query
    await cb.answer()
    await _do_join(cb.message.chat.id, cb.from_user, ctx, update)

async def _do_join(cid, user, ctx, update):
    if not await is_member(ctx.bot, user.id):
        if update.message:
            await update.message.reply_text(
                f"⚠️ Pehle channel join karo!\n{CHANNEL_LINK}",
                reply_markup=channel_kb(), disable_web_page_preview=True)
        return

    if cid not in games or games[cid]["phase"] != "joining":
        if update.message:
            await update.message.reply_text("❌ Koi active game nahi! /startgame se shuru karo.")
        return

    g = games[cid]

    if g["mode"] == "robot":
        if update.message:
            await update.message.reply_text("🤖 Robot mode mein sirf ek player hota hai!")
        return

    ids = [p["id"] for p in g["players"]]
    if user.id in ids:
        if update.message:
            await update.message.reply_text("⚠️ Tum pehle se join kar chuke ho!")
        return

    g["players"].append({
        "id": user.id, "name": user.full_name,
        "username": user.username or "", "is_bot": False,
    })

    count = len(g["players"])
    try:
        await ctx.bot.edit_message_text(
            chat_id=cid, message_id=g["join_msg_id"],
            text=join_text(g), parse_mode=ParseMode.HTML,
            reply_markup=join_kb() if count < 4 else None,
            disable_web_page_preview=True,
        )
    except:
        pass

    if count >= 4:
        await _start_round(cid, ctx)

# ═══════════════════════════════════════
#  Game Round
# ═══════════════════════════════════════
async def _start_round(cid, ctx):
    g = games[cid]
    g["phase"] = "guessing"

    players  = g["players"][:4]
    shuffled = players[:]
    random.shuffle(shuffled)

    for p, role in zip(shuffled, ROLES):
        g["roles"][p["id"]] = role
        if role == "Raja":   g["raja_id"]   = p["id"]
        if role == "Sipahi": g["sipahi_id"] = p["id"]
        if role == "Chor":   g["chor_id"]   = p["id"]

    raja_p   = next(p for p in players if p["id"] == g["raja_id"])
    sipahi_p = next(p for p in players if p["id"] == g["sipahi_id"])
    unknown  = [p for p in players if p["id"] not in (g["raja_id"], g["sipahi_id"])]

    role_lines = []
    for p in players:
        role = g["roles"][p["id"]]
        if role == "Raja":
            role_lines.append(f"👑 <b>{p['name']}</b> — Raja (Revealed!)")
        else:
            role_lines.append(f"❓ <b>{p['name']}</b> — Role Hidden")

    await ctx.bot.send_message(
        cid,
        f"🎭 <b>Roles Assign Ho Gaye!</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        + "\n".join(role_lines) +
        f"\n\n━━━━━━━━━━━━━━━━━━━━\n"
        f"👑 <b>Raja:</b> {mention(raja_p['name'], raja_p['id'])}\n\n"
        f'👑 Raja kehte hain:\n<i>"Sipahi! Chor ko pakdo!"</i> 🔍\n\n'
        f"⏳ Sipahi ke paas <b>60 seconds</b> hain...",
        parse_mode=ParseMode.HTML,
        disable_web_page_preview=True,
    )

    # Robot mode — if Sipahi is a bot, auto guess after delay
    if sipahi_p.get("is_bot"):
        await _robot_guess(cid, ctx, sipahi_p, unknown)
        return

    buttons = [
        [InlineKeyboardButton(f"🔎 {p['name']}", callback_data=f"guess_{cid}_{p['id']}")]
        for p in unknown
    ]

    guess_sent = await ctx.bot.send_message(
        cid,
        f"👮 {mention(sipahi_p['name'], sipahi_p['id'])} — <b>Tum Sipahi ho!</b>\n\n"
        f"Inme se kaun <b>Chor</b> 🦹 hai?\n"
        f"Neeche button dabao — 60 seconds hain!",
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(buttons),
        disable_web_page_preview=True,
    )
    g["guess_msg_id"] = guess_sent.message_id

    async def _timeout():
        await asyncio.sleep(60)
        if cid in games and games[cid]["phase"] == "guessing":
            games[cid]["phase"] = "done"
            try:
                await ctx.bot.edit_message_reply_markup(cid, g["guess_msg_id"], reply_markup=None)
            except:
                pass
            await ctx.bot.send_message(
                cid,
                "⏰ <b>Time Out!</b>\nSipahi ne jawab nahi diya!\n"
                "Game khatam — /startgame se dobara khelo!\n\n"
                f"📢 {CHANNEL_LINK} | 👤 {OWNER}",
                parse_mode=ParseMode.HTML, disable_web_page_preview=True,
            )
            games.pop(cid, None)

    asyncio.create_task(_timeout())

# ═══════════════════════════════════════
#  Robot Sipahi auto-guess
# ═══════════════════════════════════════
async def _robot_guess(cid, ctx, sipahi_p, unknown):
    g = games[cid]

    # Robot "thinks" for 3-6 seconds — realistic feel
    think_time = random.randint(3, 6)
    await ctx.bot.send_message(
        cid,
        f"🤖 <b>{sipahi_p['name']}</b> soch raha hai...\n"
        f"<i>Clues dhundh raha hai...</i> 🔍",
        parse_mode=ParseMode.HTML,
    )
    await asyncio.sleep(think_time)

    # Robot randomly guesses (50/50 — fair game!)
    guessed = random.choice(unknown)

    robot_lines = [
        f"🤖 Maine analyze kiya aur mujhe lagta hai <b>{guessed['name']}</b> Chor hai!",
        f"🤖 Meri calculations ke mutabiq <b>{guessed['name']}</b> suspicious lag raha hai!",
        f"🤖 AI analysis complete! <b>{guessed['name']}</b> Chor hai — main sure hoon!",
        f"🤖 Pattern recognition se pata chala — <b>{guessed['name']}</b> Chor hai! 😤",
    ]

    await ctx.bot.send_message(
        cid,
        random.choice(robot_lines),
        parse_mode=ParseMode.HTML,
    )
    await asyncio.sleep(1)

    await _resolve_game(cid, ctx, guessed["id"], sipahi_p)

# ═══════════════════════════════════════
#  Sipahi Guess (human)
# ═══════════════════════════════════════
async def cb_guess(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    cb   = update.callback_query
    data = cb.data.split("_")
    cid         = int(data[1])
    guessed_uid = int(data[2])

    if cid not in games:
        await cb.answer("Game nahi mili!", show_alert=True); return

    g = games[cid]

    if cb.from_user.id != g["sipahi_id"]:
        await cb.answer("Sirf Sipahi choose kar sakta hai! 👮", show_alert=True); return

    if g["phase"] != "guessing":
        await cb.answer("Game active nahi hai!", show_alert=True); return

    await cb.answer("✅ Jawab darz ho gaya!")

    try:
        await ctx.bot.edit_message_reply_markup(cid, g["guess_msg_id"], reply_markup=None)
    except:
        pass

    sipahi_p = next(p for p in games[cid]["players"] if p["id"] == g["sipahi_id"])
    guessed_p = next(p for p in games[cid]["players"] if p["id"] == guessed_uid)
    await _resolve_game(cid, ctx, guessed_uid, sipahi_p)

# ═══════════════════════════════════════
#  Resolve Game (shared)
# ═══════════════════════════════════════
async def _resolve_game(cid, ctx, guessed_uid, sipahi_p):
    g = games[cid]
    g["phase"] = "done"

    players  = g["players"][:4]
    roles    = g["roles"]
    chor_id  = g["chor_id"]
    correct  = (guessed_uid == chor_id)

    awards = {}
    for p in players:
        role = roles[p["id"]]
        if correct:
            awards[p["id"]] = POINTS[role]
        else:
            if role == "Sipahi":   awards[p["id"]] = 0
            elif role == "Chor":   awards[p["id"]] = 300
            else:                  awards[p["id"]] = POINTS[role]

    result_lines = []
    for p in players:
        role = roles[p["id"]]
        pts  = awards[p["id"]]
        bot_tag = " 🤖" if p.get("is_bot") else ""
        result_lines.append(
            f"{EMOJI[role]} <b>{p['name']}{bot_tag}</b> — {role} → <b>+{pts} pts</b>"
        )

    chor_p    = next(p for p in players if p["id"] == chor_id)
    guessed_p = next(p for p in players if p["id"] == guessed_uid)

    if correct:
        verdict = (
            f"✅ <b>Sipahi ne sahi pakda!</b> 🎯\n"
            f"🦹 Chor tha: <b>{chor_p['name']}</b>\n"
        )
    else:
        verdict = (
            f"❌ <b>Sipahi ne galat pakda!</b> 😱\n"
            f"<b>{guessed_p['name']}</b> Chor nahi tha!\n"
            f"🦹 Asli Chor: <b>{chor_p['name']}</b> — +300 mil gaye! 😈\n"
        )

    mode_tag = "🤖 Robot Mode" if g["mode"] == "robot" else "👥 Friends Mode"

    await ctx.bot.send_message(
        cid,
        f"🏁 <b>Game Over!</b> [{mode_tag}]\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"{verdict}\n"
        f"<b>Final Scores:</b>\n"
        + "\n".join(result_lines) +
        f"\n\n━━━━━━━━━━━━━━━━━━━━\n"
        f"🔁 /startgame | 🏆 /leaderboard\n"
        f"📢 {CHANNEL_LINK} | 👤 {OWNER}",
        parse_mode=ParseMode.HTML,
        disable_web_page_preview=True,
    )

    # Save only real player scores
    for p in players:
        if not p.get("is_bot"):
            role = roles[p["id"]]
            won  = correct and role in ("Raja","Rani","Sipahi")
            db_add(cid, p["id"], p["name"], p.get("username",""), awards[p["id"]], won)

    games.pop(cid, None)

# ═══════════════════════════════════════
#  /leaderboard
# ═══════════════════════════════════════
async def cmd_leaderboard(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    rows = db_top(update.effective_chat.id)
    if not rows:
        await update.message.reply_text("📋 Koi scores nahi hain. Pehle khelo! 🎮"); return
    medals = ["🥇","🥈","🥉"] + ["🏅"]*7
    lines  = [f"🏆 <b>Leaderboard</b>\n━━━━━━━━━━━━━━━━━━━━"]
    for i,(name,uname,pts,gms,wins) in enumerate(rows):
        u = f"@{uname}" if uname else ""
        lines.append(f"{medals[i]} <b>{name}</b> {u}\n   💰 {pts} pts | 🎮 {gms} | 🏅 {wins} wins")
    lines.append(f"\n📢 {CHANNEL_LINK} | 👤 {OWNER}")
    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML, disable_web_page_preview=True)

# ═══════════════════════════════════════
#  /myscore
# ═══════════════════════════════════════
async def cmd_myscore(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    row, rank = db_me(update.effective_chat.id, update.effective_user.id)
    if not row:
        await update.message.reply_text("❌ Score nahi hai. Pehle game khelo! 🎮"); return
    name,pts,gms,wins = row
    await update.message.reply_text(
        f"📊 <b>Tumhara Score</b>\n━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 <b>{name}</b>\n💰 Points: <b>{pts}</b>\n"
        f"🎮 Games: <b>{gms}</b>\n🏅 Wins: <b>{wins}</b>\n🏆 Rank: <b>#{rank}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n📢 {CHANNEL_LINK} | 👤 {OWNER}",
        parse_mode=ParseMode.HTML,
    )

# ═══════════════════════════════════════
#  Main
# ═══════════════════════════════════════
def main():
    db_init()
    log.info("Bot start ho raha hai...")

    application = Application.builder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start",       cmd_start))
    application.add_handler(CommandHandler("help",        cmd_help))
    application.add_handler(CommandHandler("startgame",   cmd_startgame))
    application.add_handler(CommandHandler("join",        cmd_join))
    application.add_handler(CommandHandler("leaderboard", cmd_leaderboard))
    application.add_handler(CommandHandler("myscore",     cmd_myscore))

    application.add_handler(CallbackQueryHandler(cb_check_join, pattern="^check_join$"))
    application.add_handler(CallbackQueryHandler(cb_show_help,  pattern="^show_help$"))
    application.add_handler(CallbackQueryHandler(cb_mode,       pattern="^mode_(friends|robot)$"))
    application.add_handler(CallbackQueryHandler(cb_join,       pattern="^join_game$"))
    application.add_handler(CallbackQueryHandler(cb_guess,      pattern=r"^guess_-?\d+_-?\d+$"))

    webhook_url = WEBHOOK_URL.rstrip("/")
    log.info(f"Webhook: {webhook_url}/webhook")

    application.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        webhook_url=f"{webhook_url}/webhook",
        url_path="webhook",
    )

if __name__ == "__main__":
    main()
