"""
Raja Rani Chor Sipahi - Telegram Bot
Owner  : @xdsonic | Channel: @nexushubxd
"""

import asyncio
import random
import sqlite3
import os
import logging
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
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
TOTAL_ROUNDS = 20

ROLES  = ["Raja", "Rani", "Chor", "Sipahi"]
EMOJI  = {"Raja": "👑", "Rani": "👸", "Chor": "🦹", "Sipahi": "👮"}
POINTS = {"Raja": 1000, "Rani": 500, "Sipahi": 300, "Chor": 0}

BOT_NAMES = ["Ali", "Sara", "Zain", "Hina", "Umar", "Nida", "Bilal", "Sana"]

games: dict = {}

def fresh_game(mode="friends"):
    return {
        "phase":        "joining",
        "mode":         mode,
        "players":      [],
        "round":        0,
        "scores":       {},   # {user_id: total_points}
        "roles":        {},
        "raja_id":      None,
        "sipahi_id":    None,
        "chor_id":      None,
        "join_msg_id":  None,
        "guess_msg_id": None,
    }

# ─── SQLite ───────────────────────────────────
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

# ─── Helpers ──────────────────────────────────
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
    return f'<a href="tg://user?id={uid}">{name}</a>'

def mode_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("👥 Play with Friends", callback_data="mode_friends")],
        [InlineKeyboardButton("🤖 Play with Robots",  callback_data="mode_robot")],
    ])

def join_kb():
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("✋ Join Game", callback_data="join_game")
    ]])

def scoreboard_text(game):
    players = [p for p in game["players"] if not p.get("is_bot")]
    if not players:
        players = game["players"]
    lines = []
    sorted_p = sorted(players, key=lambda p: game["scores"].get(p["id"], 0), reverse=True)
    medals = ["🥇","🥈","🥉","4️⃣"]
    for i, p in enumerate(sorted_p):
        pts = game["scores"].get(p["id"], 0)
        bot_tag = " 🤖" if p.get("is_bot") else ""
        lines.append(f"{medals[i]} {p['name']}{bot_tag} — <b>{pts} pts</b>")
    return "\n".join(lines)

# ─── /start ───────────────────────────────────
async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await update.message.reply_text(
        f"👋 <b>Assalam o Alaikum, {user.first_name}!</b>\n\n"
        f"🎮 <b>Raja Rani Chor Sipahi Bot</b> mein khush aamdeed!\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"<b>Kaise khelen?</b>\n"
        f"1️⃣ Group mein /startgame likho\n"
        f"2️⃣ Mode chunao — Friends ya Robots\n"
        f"3️⃣ 20 rounds khelo\n"
        f"4️⃣ Highest score wala <b>Champion!</b> 🏆\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"<b>Roles:</b>\n"
        f"👑 Raja = 1000 | 👸 Rani = 500\n"
        f"👮 Sipahi = 300 | 🦹 Chor = 0\n\n"
        f"<b>Twist:</b> Sipahi galat pakde toh\n"
        f"Chor +300, Sipahi = 0!\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📢 {CHANNEL_LINK} | 👤 {OWNER}",
        parse_mode=ParseMode.HTML,
        disable_web_page_preview=True,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("➕ Group mein Add Karo", url="https://t.me/Sonicdmbot?startgroup=true")],
            [InlineKeyboardButton("📢 Channel", url=CHANNEL_LINK),
             InlineKeyboardButton("❓ Help", callback_data="show_help")],
        ])
    )

# ─── /help ────────────────────────────────────
async def cmd_help(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎮 <b>Raja Rani Chor Sipahi — Help</b>\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "<b>Commands:</b>\n"
        "/startgame — Naya game shuru karo\n"
        "/join — Game mein shamil ho\n"
        "/leaderboard — Top 10 scores\n"
        "/myscore — Apna score\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "<b>Game Modes:</b>\n\n"
        "👥 <b>Friends Mode</b>\n"
        "4 real players, 20 rounds\n"
        "Highest score = Champion!\n\n"
        "🤖 <b>Robot Mode</b>\n"
        "Akele khelo, 3 AI robots saath\n"
        "Robots realistic feel dete hain!\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "<b>Sipahi kaise khelega?</b>\n"
        "Sipahi ko group mein 2 buttons milenge\n"
        "Jis par click karo — woh Chor hai tumhare liye!\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 Owner: {OWNER}",
        parse_mode=ParseMode.HTML,
        disable_web_page_preview=True,
    )

async def cb_show_help(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    cb = update.callback_query
    await cb.answer()
    await cb.edit_message_text(
        "🎮 <b>Help</b>\n\n"
        "/startgame /join /leaderboard /myscore\n\n"
        "👥 Friends Mode: 4 real players, 20 rounds\n"
        "🤖 Robot Mode: Akele + 3 AI robots\n\n"
        "👑 Raja=1000 | 👸 Rani=500\n"
        "👮 Sipahi=300 | 🦹 Chor=0",
        parse_mode=ParseMode.HTML,
    )

async def cb_check_join(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    cb = update.callback_query
    if await is_member(ctx.bot, cb.from_user.id):
        await cb.answer("✅ Shukriya! Ab game khelo.", show_alert=True)
        await cb.message.delete()
    else:
        await cb.answer("❌ Abhi tak join nahi kiya!", show_alert=True)

# ─── /startgame ───────────────────────────────
async def cmd_startgame(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user

    if chat.type == "private":
        await update.message.reply_text("⚠️ Ye sirf groups mein kaam karta hai!")
        return

    if not await is_member(ctx.bot, user.id):
        await update.message.reply_text(
            f"⚠️ <b>Pehle channel join karo!</b>\n{CHANNEL_LINK}",
            parse_mode=ParseMode.HTML, reply_markup=channel_kb(), disable_web_page_preview=True)
        return

    cid = chat.id
    if cid in games and games[cid]["phase"] != "done":
        await update.message.reply_text("⚠️ Game pehle se chal rahi hai! /join karo.")
        return

    await update.message.reply_text(
        "🎮 <b>Game Mode Chunao!</b>\n\n"
        "👥 <b>Play with Friends</b>\n"
        "   4 real players, 20 rounds ka muqabla!\n\n"
        "🤖 <b>Play with Robots</b>\n"
        "   Akele khelo, 3 AI robots ke saath!\n"
        "   Bilkul real feel — robot sochte hain! 😄",
        parse_mode=ParseMode.HTML,
        reply_markup=mode_kb()
    )

# ─── Mode Selection ────────────────────────────
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
        "id": user.id, "name": user.full_name,
        "username": user.username or "", "is_bot": False,
    })
    g["scores"][user.id] = 0

    if mode == "robot":
        bots = random.sample(BOT_NAMES, 3)
        for i, bname in enumerate(bots):
            bid = -(i+1)
            g["players"].append({"id": bid, "name": bname, "username": "", "is_bot": True})
            g["scores"][bid] = 0

        await cb.edit_message_text(
            f"🤖 <b>Robot Mode!</b>\n\n"
            f"Tumhare saath khel rahe hain:\n"
            + "\n".join(f"🤖 {p['name']}" for p in g["players"] if p.get("is_bot")) +
            f"\n\n🎯 <b>{TOTAL_ROUNDS} rounds</b> honge!\n"
            f"Highest score = Champion 🏆",
            parse_mode=ParseMode.HTML,
        )
        await asyncio.sleep(2)
        await _start_round(cid, ctx)
    else:
        await cb.edit_message_text(
            f"👥 <b>Friends Mode!</b>\n\n"
            f"Players: 🟩⬜⬜⬜ <b>1/4</b>\n\n"
            f"• {user.full_name}\n\n"
            f"⏳ 3 aur chahiye!\n"
            f"🎯 <b>{TOTAL_ROUNDS} rounds</b> ka muqabla hoga!",
            parse_mode=ParseMode.HTML,
            reply_markup=join_kb(),
        )
        g["join_msg_id"] = cb.message.message_id

# ─── /join ────────────────────────────────────
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
            await update.message.reply_text("❌ Koi active game nahi! /startgame karo.")
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

    g["players"].append({"id": user.id, "name": user.full_name,
                          "username": user.username or "", "is_bot": False})
    g["scores"][user.id] = 0

    count = len(g["players"])
    bar   = "🟩" * count + "⬜" * (4 - count)
    plist = "\n".join(f"• {p['name']}" for p in g["players"])
    need  = f"{4-count} aur chahiye!" if count < 4 else "Sab aa gaye! Starting..."

    try:
        await ctx.bot.edit_message_text(
            chat_id=cid, message_id=g["join_msg_id"],
            text=(
                f"👥 <b>Friends Mode</b>\n\n"
                f"Players: {bar} <b>{count}/4</b>\n\n"
                f"{plist}\n\n"
                f"⏳ {need}\n"
                f"🎯 <b>{TOTAL_ROUNDS} rounds</b> ka muqabla!"
            ),
            parse_mode=ParseMode.HTML,
            reply_markup=join_kb() if count < 4 else None,
        )
    except:
        pass

    if count >= 4:
        await _start_round(cid, ctx)

# ─── Game Round ───────────────────────────────
async def _start_round(cid, ctx):
    g = games[cid]
    g["phase"]  = "guessing"
    g["round"] += 1
    g["roles"]  = {}

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
        tag  = " 🤖" if p.get("is_bot") else ""
        if role == "Raja":
            role_lines.append(f"👑 <b>{p['name']}{tag}</b> — Raja")
        else:
            role_lines.append(f"❓ <b>{p['name']}{tag}</b> — ???")

    await ctx.bot.send_message(
        cid,
        f"🃏 <b>Round {g['round']}/{TOTAL_ROUNDS}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        + "\n".join(role_lines) +
        f"\n\n👑 <b>Raja:</b> {raja_p['name']}"
        + (" 🤖" if raja_p.get("is_bot") else "") +
        f'\n\n<i>"Sipahi! Chor ko pakdo!"</i> 🔍',
        parse_mode=ParseMode.HTML,
    )

    if sipahi_p.get("is_bot"):
        await _robot_sipahi(cid, ctx, sipahi_p, unknown)
        return

    # Human Sipahi — show buttons in group
    sipahi_tag = " 🤖" if sipahi_p.get("is_bot") else ""
    buttons = [
        [InlineKeyboardButton(
            f"🔎 {p['name']}" + (" 🤖" if p.get("is_bot") else ""),
            callback_data=f"guess_{cid}_{p['id']}"
        )]
        for p in unknown
    ]

    guess_sent = await ctx.bot.send_message(
        cid,
        f"👮 {mention(sipahi_p['name'], sipahi_p['id'])} — <b>Tum Sipahi ho!</b>\n\n"
        f"⬇️ Neeche se Chor ko chunao!\n"
        f"⏳ <b>60 seconds</b> hain tumhare paas!",
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(buttons),
    )
    g["guess_msg_id"] = guess_sent.message_id

    async def _timeout():
        await asyncio.sleep(60)
        if cid in games and games[cid]["phase"] == "guessing":
            try:
                await ctx.bot.edit_message_reply_markup(cid, g["guess_msg_id"], reply_markup=None)
            except:
                pass
            await ctx.bot.send_message(cid,
                f"⏰ <b>Time Out!</b> Sipahi ne jawab nahi diya!\n"
                f"Ye round skip — agla round shuru ho raha hai...",
                parse_mode=ParseMode.HTML)
            await _next_round(cid, ctx, awards={})

    asyncio.create_task(_timeout())

# ─── Robot Sipahi ─────────────────────────────
async def _robot_sipahi(cid, ctx, sipahi_p, unknown):
    think = random.randint(2, 5)
    robot_think = [
        f"🤖 <b>{sipahi_p['name']}</b> clues dhundh raha hai...",
        f"🤖 <b>{sipahi_p['name']}</b> soch raha hai... 🤔",
        f"🤖 <b>{sipahi_p['name']}</b> analyze kar raha hai...",
    ]
    await ctx.bot.send_message(cid, random.choice(robot_think), parse_mode=ParseMode.HTML)
    await asyncio.sleep(think)

    guessed = random.choice(unknown)
    robot_says = [
        f"🤖 <b>{sipahi_p['name']}:</b> \"Maine dekha — <b>{guessed['name']}</b> Chor lag raha hai!\"",
        f"🤖 <b>{sipahi_p['name']}:</b> \"AI analysis: <b>{guessed['name']}</b> suspicious hai!\"",
        f"🤖 <b>{sipahi_p['name']}:</b> \"Mujhe yakeen hai — <b>{guessed['name']}</b> Chor hai!\"",
        f"🤖 <b>{sipahi_p['name']}:</b> \"Pattern match! <b>{guessed['name']}</b> Chor hai! 🎯\"",
    ]
    await ctx.bot.send_message(cid, random.choice(robot_says), parse_mode=ParseMode.HTML)
    await asyncio.sleep(1)
    await _resolve_round(cid, ctx, guessed["id"])

# ─── Human Guess Callback ─────────────────────
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

    await _resolve_round(cid, ctx, guessed_uid)

# ─── Resolve Round ────────────────────────────
async def _resolve_round(cid, ctx, guessed_uid):
    g       = games[cid]
    players = g["players"][:4]
    roles   = g["roles"]
    chor_id = g["chor_id"]
    correct = (guessed_uid == chor_id)

    awards = {}
    for p in players:
        role = roles[p["id"]]
        if correct:
            awards[p["id"]] = POINTS[role]
        else:
            if role == "Sipahi":   awards[p["id"]] = 0
            elif role == "Chor":   awards[p["id"]] = 300
            else:                  awards[p["id"]] = POINTS[role]

    # Add to session scores
    for p in players:
        g["scores"][p["id"]] = g["scores"].get(p["id"], 0) + awards[p["id"]]

    chor_p    = next(p for p in players if p["id"] == chor_id)
    guessed_p = next(p for p in players if p["id"] == guessed_uid)
    sipahi_p  = next(p for p in players if p["id"] == g["sipahi_id"])

    if correct:
        verdict = f"✅ <b>Sahi!</b> {mention(sipahi_p['name'], sipahi_p['id'])} ne Chor pakad liya!"
    else:
        verdict = (
            f"❌ <b>Galat!</b> {guessed_p['name']} Chor nahi tha!\n"
            f"🦹 Asli Chor: <b>{chor_p['name']}</b> bhaag gaya!"
        )

    round_lines = []
    for p in players:
        role = roles[p["id"]]
        pts  = awards[p["id"]]
        tag  = " 🤖" if p.get("is_bot") else ""
        round_lines.append(f"{EMOJI[role]} {p['name']}{tag} — +{pts}")

    await ctx.bot.send_message(
        cid,
        f"<b>Round {g['round']} Result</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"{verdict}\n\n"
        f"<b>Is round ke points:</b>\n"
        + "\n".join(round_lines) +
        f"\n\n<b>Total Scores:</b>\n{scoreboard_text(g)}",
        parse_mode=ParseMode.HTML,
    )

    await _next_round(cid, ctx, awards)

# ─── Next Round or End ────────────────────────
async def _next_round(cid, ctx, awards):
    g = games[cid]

    # Save DB scores for real players
    for p in g["players"]:
        if not p.get("is_bot") and p["id"] in awards:
            db_add(cid, p["id"], p["name"], p.get("username",""), awards[p["id"]])

    if g["round"] >= TOTAL_ROUNDS:
        await _end_game(cid, ctx)
        return

    g["phase"] = "next"
    remaining  = TOTAL_ROUNDS - g["round"]

    await asyncio.sleep(3)
    await ctx.bot.send_message(
        cid,
        f"🔄 <b>Agla Round {g['round']+1}/{TOTAL_ROUNDS} shuru ho raha hai...</b>\n"
        f"⏳ {remaining} rounds baaki hain!",
        parse_mode=ParseMode.HTML,
    )
    await asyncio.sleep(2)
    await _start_round(cid, ctx)

# ─── End Game ────────────────────────────────
async def _end_game(cid, ctx):
    g       = games[cid]
    players = g["players"][:4]

    sorted_p = sorted(players, key=lambda p: g["scores"].get(p["id"], 0), reverse=True)
    winner   = sorted_p[0]
    medals   = ["🥇","🥈","🥉","4️⃣"]

    final_lines = []
    for i, p in enumerate(sorted_p):
        pts = g["scores"].get(p["id"], 0)
        tag = " 🤖" if p.get("is_bot") else ""
        final_lines.append(f"{medals[i]} <b>{p['name']}{tag}</b> — {pts} pts")

    winner_tag = " 🤖" if winner.get("is_bot") else ""
    mode_tag   = "🤖 Robot Mode" if g["mode"] == "robot" else "👥 Friends Mode"

    await ctx.bot.send_message(
        cid,
        f"🏆 <b>GAME KHATAM! {TOTAL_ROUNDS} Rounds Complete!</b>\n"
        f"[{mode_tag}]\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🎉 <b>CHAMPION:</b> {winner['name']}{winner_tag}!\n\n"
        f"<b>Final Leaderboard:</b>\n"
        + "\n".join(final_lines) +
        f"\n\n━━━━━━━━━━━━━━━━━━━━\n"
        f"🔁 /startgame — Dobara khelo!\n"
        f"👤 {OWNER}",
        parse_mode=ParseMode.HTML,
    )

    # Save final win for winner
    if not winner.get("is_bot"):
        db_add(cid, winner["id"], winner["name"], winner.get("username",""), 0, won=True)

    games.pop(cid, None)

# ─── /leaderboard ────────────────────────────
async def cmd_leaderboard(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    rows = db_top(update.effective_chat.id)
    if not rows:
        await update.message.reply_text("📋 Koi scores nahi hain. Pehle khelo! 🎮"); return
    medals = ["🥇","🥈","🥉"] + ["🏅"]*7
    lines  = ["🏆 <b>Leaderboard</b>\n━━━━━━━━━━━━━━━━━━━━"]
    for i,(name,uname,pts,gms,wins) in enumerate(rows):
        u = f"@{uname}" if uname else ""
        lines.append(f"{medals[i]} <b>{name}</b> {u}\n   💰 {pts} pts | 🎮 {gms} games | 🏅 {wins} wins")
    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML)

# ─── /myscore ────────────────────────────────
async def cmd_myscore(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    row, rank = db_me(update.effective_chat.id, update.effective_user.id)
    if not row:
        await update.message.reply_text("❌ Score nahi hai. Pehle game khelo! 🎮"); return
    name,pts,gms,wins = row
    await update.message.reply_text(
        f"📊 <b>Tumhara Score</b>\n━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 <b>{name}</b>\n"
        f"💰 Points: <b>{pts}</b>\n"
        f"🎮 Games: <b>{gms}</b>\n"
        f"🏅 Wins: <b>{wins}</b>\n"
        f"🏆 Rank: <b>#{rank}</b>",
        parse_mode=ParseMode.HTML,
    )

# ─── Main ─────────────────────────────────────
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

    application.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        webhook_url=f"{WEBHOOK_URL.rstrip('/')}/webhook",
        url_path="webhook",
    )

if __name__ == "__main__":
    main()
