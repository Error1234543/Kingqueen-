"""
╔══════════════════════════════════════════════╗
║   Raja Rani Chor Sipahi — Telegram Bot       ║
║   Owner  : @xdsonic                          ║
║   Channel: @nexushubxd                       ║
║   Deploy : Render.com (Webhook Mode)         ║
╚══════════════════════════════════════════════╝
"""

import asyncio
import random
import sqlite3
import os
import logging
from dotenv import load_dotenv
from pyrogram import Client, filters, idle
from pyrogram.types import (
    Message, InlineKeyboardMarkup,
    InlineKeyboardButton, CallbackQuery
)
from pyrogram.enums import ChatType
from pyrogram.errors import FloodWait

# ──────────────────────────────────────────────
#  Logging
# ──────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)
log = logging.getLogger(__name__)

# ──────────────────────────────────────────────
#  Environment
# ──────────────────────────────────────────────
load_dotenv()
API_ID    = int(os.getenv("API_ID", "0"))
API_HASH  = os.getenv("API_HASH", "")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
OWNER     = "@xdsonic"
CHANNEL   = "nexushubxd"          # without @
CHANNEL_LINK = "https://t.me/nexushubxd"

# ──────────────────────────────────────────────
#  Pyrogram Client
# ──────────────────────────────────────────────
app = Client(
    "rrcs_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
)

# ──────────────────────────────────────────────
#  Role Config
# ──────────────────────────────────────────────
ROLES = ["Raja", "Rani", "Chor", "Sipahi"]
EMOJI = {
    "Raja":   "👑",
    "Rani":   "👸",
    "Chor":   "🦹",
    "Sipahi": "👮",
}
POINTS = {
    "Raja":   1000,
    "Rani":   500,
    "Sipahi": 300,
    "Chor":   0,
}

# ──────────────────────────────────────────────
#  In-memory Games  { chat_id: {...} }
# ──────────────────────────────────────────────
games: dict[int, dict] = {}

def fresh_game() -> dict:
    return {
        "phase":        "joining",   # joining | guessing | done
        "players":      [],          # [{"id","name","username"}]
        "roles":        {},          # {user_id: role}
        "raja_id":      None,
        "rani_id":      None,
        "sipahi_id":    None,
        "chor_id":      None,
        "join_msg_id":  None,        # editable join message
        "role_msg_ids": {},          # {user_id: msg_id}  role reveal msgs
        "guess_msg_id": None,        # sipahi guess message id
        "timeout_task": None,
    }

# ──────────────────────────────────────────────
#  SQLite
# ──────────────────────────────────────────────
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
    con.commit(); con.close()

def db_add(chat_id, user_id, name, username, pts, won=False):
    con = sqlite3.connect(DB)
    con.execute("""
        INSERT INTO scores(user_id,chat_id,name,username,points,games,wins)
        VALUES(?,?,?,?,?,1,?)
        ON CONFLICT(user_id,chat_id) DO UPDATE SET
            points  = points + excluded.points,
            games   = games  + 1,
            wins    = wins   + excluded.wins,
            name    = excluded.name,
            username= excluded.username
    """, (user_id, chat_id, name, username, pts, 1 if won else 0))
    con.commit(); con.close()

def db_top(chat_id, n=10):
    con = sqlite3.connect(DB)
    rows = con.execute("""
        SELECT name, username, points, games, wins
        FROM scores WHERE chat_id=?
        ORDER BY points DESC LIMIT ?
    """, (chat_id, n)).fetchall()
    con.close()
    return rows

def db_me(chat_id, user_id):
    con = sqlite3.connect(DB)
    row = con.execute("""
        SELECT name, points, games, wins FROM scores
        WHERE chat_id=? AND user_id=?
    """, (chat_id, user_id)).fetchone()
    rank = con.execute("""
        SELECT COUNT(*)+1 FROM scores
        WHERE chat_id=? AND points>(
            SELECT COALESCE(points,0) FROM scores WHERE chat_id=? AND user_id=?
        )
    """, (chat_id, chat_id, user_id)).fetchone()[0]
    con.close()
    return row, rank

# ──────────────────────────────────────────────
#  Channel membership check
# ──────────────────────────────────────────────
async def is_member(client: Client, user_id: int) -> bool:
    try:
        member = await client.get_chat_member(CHANNEL, user_id)
        return member.status.name not in ("BANNED", "LEFT", "RESTRICTED")
    except Exception:
        return False

def join_channel_kb():
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("📢 Channel Join Karo", url=CHANNEL_LINK),
        InlineKeyboardButton("✅ Joined!", callback_data="check_join"),
    ]])

# ──────────────────────────────────────────────
#  Helpers
# ──────────────────────────────────────────────
def link(name: str, uid: int) -> str:
    return f"[{name}](tg://user?id={uid})"

def build_join_text(game: dict) -> str:
    count   = len(game["players"])
    needed  = max(0, 4 - count)
    plist   = "\n".join(f"  ▸ {p['name']}" for p in game["players"])
    bar_filled = "🟩" * count + "⬜" * (4 - count)
    return (
        f"🎮 **Raja Rani Chor Sipahi**\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"👥 Players: {bar_filled} **{count}/4**\n\n"
        f"{plist if plist else '  _Abhi koi nahi..._'}\n\n"
        f"{'⏳ ' + str(needed) + ' aur chahiye!' if needed else '🚀 Sab aa gaye, starting...'}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📢 Channel: {CHANNEL_LINK}\n"
        f"👤 Owner: {OWNER}"
    )

def join_kb():
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("✋ Join Game", callback_data="join_game")
    ]])

# ──────────────────────────────────────────────
#  /start
# ──────────────────────────────────────────────
@app.on_message(filters.command("start") & filters.private)
async def cmd_start_pm(_, msg: Message):
    await msg.reply(
        f"👋 **Assalam o Alaikum!**\n\n"
        f"Mujhe apne **group mein add karo** aur wahan `/startgame` likho!\n\n"
        f"📢 Humara channel: {CHANNEL_LINK}\n"
        f"👤 Owner: {OWNER}"
    )

# ──────────────────────────────────────────────
#  /help
# ──────────────────────────────────────────────
@app.on_message(filters.command("help"))
async def cmd_help(_, msg: Message):
    text = (
        f"🎮 **Raja Rani Chor Sipahi**\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"**Commands:**\n"
        f"🟢 `/startgame` — Naya game shuru karo\n"
        f"✋ `/join` — Game mein shamil ho\n"
        f"🏆 `/leaderboard` — Top 10 scores\n"
        f"📊 `/myscore` — Apna score dekho\n"
        f"❓ `/help` — Ye message\n\n"
        f"**Roles & Points:**\n"
        f"👑 Raja → **1000 pts**\n"
        f"👸 Rani → **500 pts**\n"
        f"👮 Sipahi → **300 pts** _(agar sahi pakde)_\n"
        f"🦹 Chor → **0 pts** _(agar pakda jaye)_\n\n"
        f"**Twist:**\n"
        f"❌ Agar Sipahi galat pakde:\n"
        f"   Chor → +300 | Sipahi → 0\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📢 {CHANNEL_LINK} | 👤 {OWNER}"
    )
    await msg.reply(text, disable_web_page_preview=True)

# ──────────────────────────────────────────────
#  Check join callback (after channel join)
# ──────────────────────────────────────────────
@app.on_callback_query(filters.regex("^check_join$"))
async def cb_check_join(client: Client, cb: CallbackQuery):
    if await is_member(client, cb.from_user.id):
        await cb.answer("✅ Shukriya join karne ka! Ab game khelo.", show_alert=True)
        await cb.message.delete()
    else:
        await cb.answer("❌ Abhi tak join nahi kiya!", show_alert=True)

# ──────────────────────────────────────────────
#  /startgame
# ──────────────────────────────────────────────
@app.on_message(filters.command("startgame") & filters.group)
async def cmd_startgame(client: Client, msg: Message):
    cid = msg.chat.id
    uid = msg.from_user.id

    # Channel check
    if not await is_member(client, uid):
        await msg.reply(
            f"⚠️ **Pehle hamara channel join karo!**\n{CHANNEL_LINK}",
            reply_markup=join_channel_kb(),
            disable_web_page_preview=True,
        )
        return

    if cid in games and games[cid]["phase"] != "done":
        await msg.reply(
            "⚠️ Pehle se ek game chal rahi hai!\n"
            "Join karo: `/join` ya neeche button dabao."
        )
        return

    games[cid] = fresh_game()
    g = games[cid]
    g["players"].append({
        "id": uid,
        "name": msg.from_user.full_name,
        "username": msg.from_user.username or "",
    })

    sent = await msg.reply(build_join_text(g), reply_markup=join_kb())
    g["join_msg_id"] = sent.id

# ──────────────────────────────────────────────
#  /join command
# ──────────────────────────────────────────────
@app.on_message(filters.command("join") & filters.group)
async def cmd_join(client: Client, msg: Message):
    await _do_join(client, msg.chat.id, msg.from_user, source_msg=msg)

# ──────────────────────────────────────────────
#  Join via button
# ──────────────────────────────────────────────
@app.on_callback_query(filters.regex("^join_game$"))
async def cb_join(client: Client, cb: CallbackQuery):
    await cb.answer()
    await _do_join(client, cb.message.chat.id, cb.from_user)

# ──────────────────────────────────────────────
#  Core join logic
# ──────────────────────────────────────────────
async def _do_join(client, cid, user, source_msg=None):
    # Channel check
    if not await is_member(client, user.id):
        kb = join_channel_kb()
        if source_msg:
            await source_msg.reply(
                f"⚠️ Pehle channel join karo: {CHANNEL_LINK}",
                reply_markup=kb, disable_web_page_preview=True,
            )
        return

    if cid not in games or games[cid]["phase"] != "joining":
        if source_msg:
            await source_msg.reply("❌ Koi active game nahi hai. `/startgame` se shuru karo!")
        return

    g = games[cid]
    ids = [p["id"] for p in g["players"]]

    if user.id in ids:
        if source_msg:
            await source_msg.reply("⚠️ Tum pehle se join kar chuke ho!")
        return

    g["players"].append({
        "id": user.id,
        "name": user.full_name,
        "username": user.username or "",
    })

    count = len(g["players"])

    # Update the join message
    try:
        await client.edit_message_text(
            cid, g["join_msg_id"],
            build_join_text(g),
            reply_markup=join_kb() if count < 4 else None,
        )
    except Exception:
        pass

    if count >= 4:
        await _start_round(client, cid)

# ──────────────────────────────────────────────
#  Game Round
# ──────────────────────────────────────────────
async def _start_round(client: Client, cid: int):
    g = games[cid]
    g["phase"] = "guessing"

    players = g["players"][:4]
    shuffled = players[:]
    random.shuffle(shuffled)

    # Assign roles
    for p, role in zip(shuffled, ROLES):
        g["roles"][p["id"]] = role
        if role == "Raja":   g["raja_id"]   = p["id"]
        if role == "Rani":   g["rani_id"]   = p["id"]
        if role == "Sipahi": g["sipahi_id"] = p["id"]
        if role == "Chor":   g["chor_id"]   = p["id"]

    # Build roles reveal (hidden, spoiler style) — shown in group
    role_lines = []
    for p in players:
        role = g["roles"][p["id"]]
        if role == "Raja":
            # Raja is always public
            role_lines.append(f"👑 {link(p['name'], p['id'])} — **Raja** _(Revealed!)_")
        else:
            role_lines.append(f"❓ {link(p['name'], p['id'])} — _Role Hidden_")

    raja_p = next(p for p in players if p["id"] == g["raja_id"])

    await client.send_message(
        cid,
        f"🎭 **Roles Assign Ho Gaye!**\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"{'chr(10)'.join(role_lines)}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"👑 **Raja Reveal:** {link(raja_p['name'], raja_p['id'])}\n\n"
        f"👑 Raja kehte hain:\n"
        f"_\"Sipahi! Chor ko pakdo!\"_ 🔍\n\n"
        f"⏳ Sipahi ke paas **60 seconds** hain...",
        disable_web_page_preview=True,
    )

    # Sipahi guess buttons — only unknown players (not Raja, not Sipahi)
    sipahi_p = next(p for p in players if p["id"] == g["sipahi_id"])
    unknown  = [p for p in players if p["id"] not in (g["raja_id"], g["sipahi_id"])]

    buttons = [
        [InlineKeyboardButton(
            f"🔎 {p['name']}",
            callback_data=f"guess_{cid}_{p['id']}"
        )]
        for p in unknown
    ]
    buttons.append([
        InlineKeyboardButton("⏩ Koi nahi (Skip)", callback_data=f"guess_{cid}_skip")
    ])

    guess_sent = await client.send_message(
        cid,
        f"👮 {link(sipahi_p['name'], sipahi_p['id'])} — **Tum Sipahi ho!**\n\n"
        f"Inme se kaun **Chor 🦹** hai?\n"
        f"👇 Neeche se chunao:\n\n"
        f"_Ye sirf Sipahi ke liye hai — koi hint mat do!_ 🤫",
        reply_markup=InlineKeyboardMarkup(buttons),
        disable_web_page_preview=True,
    )
    g["guess_msg_id"] = guess_sent.id

    # Timeout
    async def _timeout():
        await asyncio.sleep(60)
        if cid in games and games[cid]["phase"] == "guessing":
            games[cid]["phase"] = "done"
            try:
                await client.edit_message_reply_markup(cid, g["guess_msg_id"], reply_markup=None)
            except Exception:
                pass
            await client.send_message(
                cid,
                f"⏰ **Time Out!**\n"
                f"👮 Sipahi ne 60 seconds mein jawab nahi diya!\n"
                f"Game khatam — `/startgame` se dobara khelo!\n\n"
                f"📢 {CHANNEL_LINK} | 👤 {OWNER}",
                disable_web_page_preview=True,
            )
            games.pop(cid, None)

    g["timeout_task"] = asyncio.create_task(_timeout())

# ──────────────────────────────────────────────
#  Sipahi Guess
# ──────────────────────────────────────────────
@app.on_callback_query(filters.regex(r"^guess_(-?\d+)_(.+)$"))
async def cb_guess(client: Client, cb: CallbackQuery):
    cid         = int(cb.matches[0].group(1))
    guessed_raw = cb.matches[0].group(2)

    if cid not in games:
        await cb.answer("❌ Game nahi mili!", show_alert=True); return

    g = games[cid]

    if cb.from_user.id != g["sipahi_id"]:
        await cb.answer("❌ Sirf Sipahi choose kar sakta hai! 👮", show_alert=True); return

    if g["phase"] != "guessing":
        await cb.answer("❌ Game active nahi hai!", show_alert=True); return

    await cb.answer("✅ Jawab darz ho gaya!")

    # Cancel timeout
    if g["timeout_task"]:
        g["timeout_task"].cancel()

    g["phase"] = "done"

    # Remove buttons
    try:
        await client.edit_message_reply_markup(cid, g["guess_msg_id"], reply_markup=None)
    except Exception:
        pass

    players  = g["players"][:4]
    roles    = g["roles"]
    chor_id  = g["chor_id"]

    guessed_id = None if guessed_raw == "skip" else int(guessed_raw)
    correct    = (guessed_id == chor_id)

    # Award points
    awards = {}
    for p in players:
        role = roles[p["id"]]
        if correct:
            awards[p["id"]] = POINTS[role]
        else:
            if role == "Sipahi": awards[p["id"]] = 0
            elif role == "Chor": awards[p["id"]] = 300
            else:                awards[p["id"]] = POINTS[role]

    # Build result
    result_lines = []
    for p in players:
        role = roles[p["id"]]
        pts  = awards[p["id"]]
        result_lines.append(
            f"{EMOJI[role]} {link(p['name'], p['id'])} — **{role}** → +**{pts}** pts"
        )

    chor_p   = next(p for p in players if p["id"] == chor_id)
    sipahi_p = next(p for p in players if p["id"] == g["sipahi_id"])

    if correct:
        verdict = (
            f"✅ **Sipahi ne sahi pakda!** 🎯\n"
            f"🦹 **Chor tha:** {link(chor_p['name'], chor_p['id'])}\n"
        )
    elif guessed_raw == "skip":
        verdict = (
            f"⏩ **Sipahi ne skip kiya!** 😅\n"
            f"🦹 **Asli Chor tha:** {link(chor_p['name'], chor_p['id'])}\n"
            f"Chor bhaag gaya — Chor ko +300 mil gaye! 😈\n"
        )
    else:
        guessed_p = next(p for p in players if p["id"] == guessed_id)
        verdict = (
            f"❌ **Sipahi ne galat pakda!** 😱\n"
            f"🤷 **{link(guessed_p['name'], guessed_p['id'])}** Chor nahi tha!\n"
            f"🦹 **Asli Chor tha:** {link(chor_p['name'], chor_p['id'])}\n"
            f"Chor bhaag gaya — Chor ko +300 mil gaye! 😈\n"
        )

    await client.send_message(
        cid,
        f"🏁 **Game Over!**\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"{verdict}\n"
        f"**Scores:**\n"
        + "\n".join(result_lines) +
        f"\n\n━━━━━━━━━━━━━━━━━━━━\n"
        f"🔁 `/startgame` — Dobara khelo!\n"
        f"🏆 `/leaderboard` — Top scores dekho\n"
        f"📢 {CHANNEL_LINK} | 👤 {OWNER}",
        disable_web_page_preview=True,
    )

    # Save to DB
    for p in players:
        role = roles[p["id"]]
        won  = correct and role in ("Raja", "Rani", "Sipahi")
        db_add(cid, p["id"], p["name"], p.get("username",""), awards[p["id"]], won)

    games.pop(cid, None)

# ──────────────────────────────────────────────
#  /leaderboard
# ──────────────────────────────────────────────
@app.on_message(filters.command("leaderboard") & filters.group)
async def cmd_leaderboard(_, msg: Message):
    rows = db_top(msg.chat.id)
    if not rows:
        await msg.reply("📋 Koi scores nahi hain abhi. Pehle khelo! 🎮"); return

    medals = ["🥇","🥈","🥉"] + ["🏅"]*7
    lines  = [f"🏆 **Leaderboard — {msg.chat.title}**\n━━━━━━━━━━━━━━━━━━━━"]
    for i, (name, uname, pts, gms, wins) in enumerate(rows):
        u = f"@{uname}" if uname else ""
        lines.append(
            f"{medals[i]} **{name}** {u}\n"
            f"   💰 {pts} pts | 🎮 {gms} games | 🏅 {wins} wins"
        )
    lines.append(f"\n📢 {CHANNEL_LINK} | 👤 {OWNER}")
    await msg.reply("\n".join(lines), disable_web_page_preview=True)

# ──────────────────────────────────────────────
#  /myscore
# ──────────────────────────────────────────────
@app.on_message(filters.command("myscore") & filters.group)
async def cmd_myscore(_, msg: Message):
    row, rank = db_me(msg.chat.id, msg.from_user.id)
    if not row:
        await msg.reply("❌ Tumhara score nahi hai. Pehle game khelo! 🎮"); return
    name, pts, gms, wins = row
    await msg.reply(
        f"📊 **Tumhara Score**\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 **{name}**\n"
        f"💰 Points : **{pts}**\n"
        f"🎮 Games  : **{gms}**\n"
        f"🏅 Wins   : **{wins}**\n"
        f"🏆 Rank   : **#{rank}**\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📢 {CHANNEL_LINK} | 👤 {OWNER}"
    )

# ──────────────────────────────────────────────
#  Run
# ──────────────────────────────────────────────
if __name__ == "__main__":
    db_init()
    log.info("🚀 Bot start ho raha hai...")
    app.run()
