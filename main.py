"""
Raja Rani Chor Sipahi - Telegram Bot
Owner  : @xdsonic
Channel: @nexushubxd
Library: python-telegram-bot (webhook mode)
"""

import asyncio
import random
import sqlite3
import os
import logging
from dotenv import load_dotenv
from telegram import (
    Update, InlineKeyboardMarkup, InlineKeyboardButton
)
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    ContextTypes
)
from telegram.constants import ParseMode

# --- Logging ---
logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(message)s",
    level=logging.INFO
)
log = logging.getLogger(__name__)

# --- Environment ---
load_dotenv()
BOT_TOKEN    = os.getenv("BOT_TOKEN", "")
WEBHOOK_URL  = os.getenv("WEBHOOK_URL", "")   # e.g. https://kingqueen-a7rj.onrender.com
PORT         = int(os.getenv("PORT", 8080))
OWNER        = "@xdsonic"
CHANNEL      = "@nexushubxd"
CHANNEL_LINK = "https://t.me/nexushubxd"

# --- Role Config ---
ROLES  = ["Raja", "Rani", "Chor", "Sipahi"]
EMOJI  = {"Raja": "👑", "Rani": "👸", "Chor": "🦹", "Sipahi": "👮"}
POINTS = {"Raja": 1000, "Rani": 500, "Sipahi": 300, "Chor": 0}

# --- In-memory Games ---
games: dict = {}

def fresh_game():
    return {
        "phase":        "joining",
        "players":      [],
        "roles":        {},
        "raja_id":      None,
        "rani_id":      None,
        "sipahi_id":    None,
        "chor_id":      None,
        "join_msg_id":  None,
        "guess_msg_id": None,
        "timeout_job":  None,
    }

# --- SQLite ---
DB = "scores.db"

def db_init():
    con = sqlite3.connect(DB)
    con.execute("""
        CREATE TABLE IF NOT EXISTS scores (
            user_id  INTEGER,
            chat_id  INTEGER,
            name     TEXT,
            username TEXT DEFAULT '',
            points   INTEGER DEFAULT 0,
            games    INTEGER DEFAULT 0,
            wins     INTEGER DEFAULT 0,
            PRIMARY KEY(user_id, chat_id)
        )
    """)
    con.commit()
    con.close()

def db_add(chat_id, user_id, name, username, pts, won=False):
    con = sqlite3.connect(DB)
    con.execute("""
        INSERT INTO scores(user_id,chat_id,name,username,points,games,wins)
        VALUES(?,?,?,?,?,1,?)
        ON CONFLICT(user_id,chat_id) DO UPDATE SET
            points=points+excluded.points,
            games=games+1,
            wins=wins+excluded.wins,
            name=excluded.name,
            username=excluded.username
    """, (user_id, chat_id, name, username, pts, 1 if won else 0))
    con.commit()
    con.close()

def db_top(chat_id, n=10):
    con = sqlite3.connect(DB)
    rows = con.execute("""
        SELECT name,username,points,games,wins FROM scores
        WHERE chat_id=? ORDER BY points DESC LIMIT ?
    """, (chat_id, n)).fetchall()
    con.close()
    return rows

def db_me(chat_id, user_id):
    con = sqlite3.connect(DB)
    row = con.execute(
        "SELECT name,points,games,wins FROM scores WHERE chat_id=? AND user_id=?",
        (chat_id, user_id)
    ).fetchone()
    rank = con.execute("""
        SELECT COUNT(*)+1 FROM scores WHERE chat_id=? AND points>(
            SELECT COALESCE(points,0) FROM scores WHERE chat_id=? AND user_id=?
        )
    """, (chat_id, chat_id, user_id)).fetchone()[0]
    con.close()
    return row, rank

# --- Channel Check ---
async def is_member(bot, user_id):
    try:
        member = await bot.get_chat_member(CHANNEL, user_id)
        return member.status.name not in ("LEFT", "BANNED", "RESTRICTED")
    except Exception:
        return False

def channel_kb():
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("📢 Channel Join Karo", url=CHANNEL_LINK),
        InlineKeyboardButton("✅ Joined!", callback_data="check_join"),
    ]])

def mention(name, uid):
    return f"[{name}](tg://user?id={uid})"

def join_text(game):
    count = len(game["players"])
    bar   = "🟩" * count + "⬜" * (4 - count)
    plist = "\n".join(f"  • {p['name']}" for p in game["players"])
    need  = f"{4-count} aur chahiye!" if count < 4 else "Sab aa gaye!"
    return (
        f"🎮 *Raja Rani Chor Sipahi*\n"
        f"{'━'*22}\n"
        f"Players: {bar} *{count}/4*\n\n"
        f"{plist or '_Abhi koi nahi..._'}\n\n"
        f"⏳ {need}\n"
        f"{'━'*22}\n"
        f"📢 {CHANNEL_LINK}\n"
        f"👤 Owner: {OWNER}"
    )

def join_kb():
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("✋ Join Game", callback_data="join_game")
    ]])

# ═══════════════════════════════════════
#  /start
# ═══════════════════════════════════════

async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    # Pre-process the variables to handle backslashes safely outside the f-string
    escaped_channel = CHANNEL_LINK.replace('.', '\\.')
    escaped_owner = OWNER.replace('.', '\\.')
    
    text = (
        f"👋 *Assalam o Alaikum, {user.first_name}\\!*\n\n"
        f"🎮 Main hoon *Raja Rani Chor Sipahi Bot\\!*\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"*Kaise khelen\\?*\n"
        f"1\\. Mujhe apne group mein add karo\n"
        f"2\\. `/startgame` likho\n"
        f"3\\. 4 players `/join` karen\n"
        f"4\\. Khel shuru\\!\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"*Roles & Points\\:*\n"
        f"👑 Raja → *1000 pts*\n"
        f"👸 Rani → *500 pts*\n"
        f"👮 Sipahi → *300 pts* _\\(sahi pakde toh\\)_\n"
        f"🦹 Chor → *0 pts* _\\(pakda jaye toh\\)_\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📢 {escaped_channel}\n"
        f"👤 Owner\\: {escaped_owner}"
    )
    
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Group mein Add Karo", url=f"https://t.me/Sonicdmbot?startgroup=true")],
        [InlineKeyboardButton("📢 Channel Join Karo", url=CHANNEL_LINK)],
        [InlineKeyboardButton("❓ Help", callback_data="show_help")],
    ])
    
    await update.message.reply_text(
        text, 
        parse_mode=ParseMode.MARKDOWN_V2,
        reply_markup=kb, 
        disable_web_page_preview=True
    )



# ═══════════════════════════════════════
#  /help
# ═══════════════════════════════════════
async def cmd_help(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text = (
        "🎮 *Raja Rani Chor Sipahi — Help*\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "*Commands:*\n"
        "🟢 /startgame — Naya game shuru karo\n"
        "✋ /join — Game mein shamil ho\n"
        "🏆 /leaderboard — Top 10 scores\n"
        "📊 /myscore — Apna score dekho\n"
        "❓ /help — Ye message\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "*Game Rules:*\n"
        "• Minimum 4 players chahiye\n"
        "• Roles randomly assign hote hain\n"
        "• Raja publicly reveal hota hai\n"
        "• Sipahi Chor ko identify karta hai\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "*Points System:*\n"
        "👑 Raja → *1000 pts*\n"
        "👸 Rani → *500 pts*\n"
        "👮 Sipahi → *300 pts* _(sahi pakde toh)_\n"
        "🦹 Chor → *0 pts* _(pakda jaye toh)_\n\n"
        "*Twist:*\n"
        "❌ Sipahi galat pakde:\n"
        "   Chor → +300 | Sipahi → 0\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"📢 {CHANNEL_LINK} | 👤 {OWNER}"
    )
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN,
                                    disable_web_page_preview=True)

# ═══════════════════════════════════════
#  Help via button
# ═══════════════════════════════════════
async def cb_show_help(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    cb = update.callback_query
    await cb.answer()
    text = (
        "🎮 *Raja Rani Chor Sipahi — Help*\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "*Commands:*\n"
        "🟢 /startgame — Naya game shuru karo\n"
        "✋ /join — Game mein shamil ho\n"
        "🏆 /leaderboard — Top 10 scores\n"
        "📊 /myscore — Apna score dekho\n\n"
        "*Points:*\n"
        "👑 Raja=1000 | 👸 Rani=500\n"
        "👮 Sipahi=300 | 🦹 Chor=0\n\n"
        f"📢 {CHANNEL_LINK} | 👤 {OWNER}"
    )
    await cb.edit_message_text(text, parse_mode=ParseMode.MARKDOWN,
                               disable_web_page_preview=True)

# ═══════════════════════════════════════
#  Check join
# ═══════════════════════════════════════
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
        await update.message.reply_text(
            "⚠️ Ye command sirf groups mein kaam karti hai!\n"
            "Apne group mein `/startgame` likho."
        )
        return

    if not await is_member(ctx.bot, user.id):
        await update.message.reply_text(
            f"⚠️ *Pehle hamara channel join karo!*\n{CHANNEL_LINK}",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=channel_kb(),
            disable_web_page_preview=True,
        )
        return

    cid = chat.id
    if cid in games and games[cid]["phase"] != "done":
        await update.message.reply_text("⚠️ Ek game pehle se chal rahi hai! `/join` karo.")
        return

    games[cid] = fresh_game()
    g = games[cid]
    g["players"].append({
        "id": user.id,
        "name": user.full_name,
        "username": user.username or "",
    })

    sent = await update.message.reply_text(
        join_text(g), parse_mode=ParseMode.MARKDOWN,
        reply_markup=join_kb(), disable_web_page_preview=True
    )
    g["join_msg_id"] = sent.message_id

# ═══════════════════════════════════════
#  /join
# ═══════════════════════════════════════
async def cmd_join(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await _do_join(update.effective_chat.id, update.effective_user, ctx, update)

# ═══════════════════════════════════════
#  Join via button
# ═══════════════════════════════════════
async def cb_join(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    cb = update.callback_query
    await cb.answer()
    await _do_join(cb.message.chat.id, cb.from_user, ctx, update)

# ═══════════════════════════════════════
#  Core join logic
# ═══════════════════════════════════════
async def _do_join(cid, user, ctx, update):
    if not await is_member(ctx.bot, user.id):
        if update.message:
            await update.message.reply_text(
                f"⚠️ Pehle channel join karo!\n{CHANNEL_LINK}",
                reply_markup=channel_kb(),
                disable_web_page_preview=True,
            )
        return

    if cid not in games or games[cid]["phase"] != "joining":
        if update.message:
            await update.message.reply_text("❌ Koi active game nahi! `/startgame` se shuru karo.")
        return

    g = games[cid]
    ids = [p["id"] for p in g["players"]]

    if user.id in ids:
        if update.message:
            await update.message.reply_text("⚠️ Tum pehle se join kar chuke ho!")
        return

    g["players"].append({
        "id": user.id,
        "name": user.full_name,
        "username": user.username or "",
    })

    count = len(g["players"])
    try:
        await ctx.bot.edit_message_text(
            chat_id=cid,
            message_id=g["join_msg_id"],
            text=join_text(g),
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=join_kb() if count < 4 else None,
            disable_web_page_preview=True,
        )
    except Exception:
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
        if role == "Rani":   g["rani_id"]   = p["id"]
        if role == "Sipahi": g["sipahi_id"] = p["id"]
        if role == "Chor":   g["chor_id"]   = p["id"]

    raja_p   = next(p for p in players if p["id"] == g["raja_id"])
    sipahi_p = next(p for p in players if p["id"] == g["sipahi_id"])
    unknown  = [p for p in players if p["id"] not in (g["raja_id"], g["sipahi_id"])]

    role_lines = []
    for p in players:
        role = g["roles"][p["id"]]
        if role == "Raja":
            role_lines.append(f"👑 {mention(p['name'], p['id'])} — *Raja* \\(Revealed\\!\\)")
        else:
            role_lines.append(f"❓ {mention(p['name'], p['id'])} — _Role Hidden_")

    await ctx.bot.send_message(
        cid,
        f"🎭 *Roles Assign Ho Gaye\\!*\n"
        f"{'━'*22}\n\n"
        + "\n".join(role_lines) +
        f"\n\n{'━'*22}\n"
        f"👑 *Raja:* {mention(raja_p['name'], raja_p['id'])}\n\n"
        f"👑 Raja kehte hain:\n"
        f'_"Sipahi\\! Chor ko pakdo\\!"_ 🔍\n\n'
        f"⏳ Sipahi ke paas *60 seconds* hain\\.\\.\\.",
        parse_mode=ParseMode.MARKDOWN_V2,
        disable_web_page_preview=True,
    )

    buttons = [
        [InlineKeyboardButton(f"🔎 {p['name']}", callback_data=f"guess_{cid}_{p['id']}")]
        for p in unknown
    ]

    guess_sent = await ctx.bot.send_message(
        cid,
        f"👮 {mention(sipahi_p['name'], sipahi_p['id'])} — *Tum Sipahi ho\\!*\n\n"
        f"Inme se kaun *Chor* 🦹 hai?\n"
        f"Neeche button dabao — 60 seconds hain\\!",
        parse_mode=ParseMode.MARKDOWN_V2,
        reply_markup=InlineKeyboardMarkup(buttons),
        disable_web_page_preview=True,
    )
    g["guess_msg_id"] = guess_sent.message_id

    # Timeout
    async def _timeout():
        await asyncio.sleep(60)
        if cid in games and games[cid]["phase"] == "guessing":
            games[cid]["phase"] = "done"
            try:
                await ctx.bot.edit_message_reply_markup(cid, g["guess_msg_id"], reply_markup=None)
            except Exception:
                pass
            await ctx.bot.send_message(
                cid,
                f"⏰ *Time Out!*\nSipahi ne jawab nahi diya!\n"
                f"Game khatam — /startgame se dobara khelo!\n\n"
                f"📢 {CHANNEL_LINK} | 👤 {OWNER}",
                parse_mode=ParseMode.MARKDOWN,
                disable_web_page_preview=True,
            )
            games.pop(cid, None)

    asyncio.create_task(_timeout())

# ═══════════════════════════════════════
#  Sipahi Guess
# ═══════════════════════════════════════
async def cb_guess(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    cb  = update.callback_query
    data = cb.data.split("_")
    cid         = int(data[1])
    guessed_uid = int(data[2])

    if cid not in games:
        await cb.answer("Game nahi mili!", show_alert=True)
        return

    g = games[cid]

    if cb.from_user.id != g["sipahi_id"]:
        await cb.answer("Sirf Sipahi choose kar sakta hai! 👮", show_alert=True)
        return

    if g["phase"] != "guessing":
        await cb.answer("Game active nahi hai!", show_alert=True)
        return

    await cb.answer("✅ Jawab darz ho gaya!")
    g["phase"] = "done"

    try:
        await ctx.bot.edit_message_reply_markup(cid, g["guess_msg_id"], reply_markup=None)
    except Exception:
        pass

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
        result_lines.append(f"{EMOJI[role]} {mention(p['name'], p['id'])} — *{role}* → \\+*{pts}* pts")

    chor_p    = next(p for p in players if p["id"] == chor_id)
    guessed_p = next(p for p in players if p["id"] == guessed_uid)

    if correct:
        verdict = (
            f"✅ *Sipahi ne sahi pakda\\!* 🎯\n"
            f"🦹 Chor tha: {mention(chor_p['name'], chor_p['id'])}\n"
        )
    else:
        verdict = (
            f"❌ *Sipahi ne galat pakda\\!* 😱\n"
            f"{mention(guessed_p['name'], guessed_p['id'])} Chor nahi tha\\!\n"
            f"🦹 Asli Chor: {mention(chor_p['name'], chor_p['id'])} — \\+300 mil gaye\\! 😈\n"
        )

    await ctx.bot.send_message(
        cid,
        f"🏁 *Game Over\\!*\n"
        f"{'━'*22}\n\n"
        f"{verdict}\n"
        f"*Scores:*\n"
        + "\n".join(result_lines) +
        f"\n\n{'━'*22}\n"
        f"🔁 /startgame \\| 🏆 /leaderboard\n"
        f"📢 {CHANNEL_LINK} \\| 👤 {OWNER}",
        parse_mode=ParseMode.MARKDOWN_V2,
        disable_web_page_preview=True,
    )

    for p in players:
        role = roles[p["id"]]
        won  = correct and role in ("Raja", "Rani", "Sipahi")
        db_add(cid, p["id"], p["name"], p.get("username",""), awards[p["id"]], won)

    games.pop(cid, None)

# ═══════════════════════════════════════
#  /leaderboard
# ═══════════════════════════════════════
async def cmd_leaderboard(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    cid  = update.effective_chat.id
    rows = db_top(cid)
    if not rows:
        await update.message.reply_text("📋 Koi scores nahi hain. Pehle khelo! 🎮")
        return

    medals = ["🥇","🥈","🥉"] + ["🏅"]*7
    lines  = [f"🏆 *Leaderboard*\n{'━'*22}"]
    for i, (name, uname, pts, gms, wins) in enumerate(rows):
        u = f"@{uname}" if uname else ""
        lines.append(f"{medals[i]} *{name}* {u}\n   💰 {pts} pts | 🎮 {gms} | 🏅 {wins} wins")
    lines.append(f"\n📢 {CHANNEL_LINK} | 👤 {OWNER}")
    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN,
                                    disable_web_page_preview=True)

# ═══════════════════════════════════════
#  /myscore
# ═══════════════════════════════════════
async def cmd_myscore(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    cid      = update.effective_chat.id
    uid      = update.effective_user.id
    row, rank = db_me(cid, uid)
    if not row:
        await update.message.reply_text("❌ Score nahi hai. Pehle game khelo! 🎮")
        return
    name, pts, gms, wins = row
    await update.message.reply_text(
        f"📊 *Tumhara Score*\n"
        f"{'━'*22}\n"
        f"👤 *{name}*\n"
        f"💰 Points : *{pts}*\n"
        f"🎮 Games  : *{gms}*\n"
        f"🏅 Wins   : *{wins}*\n"
        f"🏆 Rank   : *#{rank}*\n"
        f"{'━'*22}\n"
        f"📢 {CHANNEL_LINK} | 👤 {OWNER}",
        parse_mode=ParseMode.MARKDOWN,
    )

# ═══════════════════════════════════════
#  Main
# ═══════════════════════════════════════
def main():
    db_init()
    log.info("Bot start ho raha hai...")

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start",       cmd_start))
    app.add_handler(CommandHandler("help",        cmd_help))
    app.add_handler(CommandHandler("startgame",   cmd_startgame))
    app.add_handler(CommandHandler("join",        cmd_join))
    app.add_handler(CommandHandler("leaderboard", cmd_leaderboard))
    app.add_handler(CommandHandler("myscore",     cmd_myscore))

    app.add_handler(CallbackQueryHandler(cb_check_join, pattern="^check_join$"))
    app.add_handler(CallbackQueryHandler(cb_show_help,  pattern="^show_help$"))
    app.add_handler(CallbackQueryHandler(cb_join,       pattern="^join_game$"))
    app.add_handler(CallbackQueryHandler(cb_guess,      pattern=r"^guess_-?\d+_\d+$"))

    webhook_url = WEBHOOK_URL.rstrip("/")
    log.info(f"Webhook: {webhook_url}/webhook")

    app.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        webhook_url=f"{webhook_url}/webhook",
        url_path="webhook",
    )

if __name__ == "__main__":
    main()
