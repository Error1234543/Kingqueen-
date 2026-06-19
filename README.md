# 🎮 Raja Rani Chor Sipahi — Telegram Bot

> **Owner:** @xdsonic | **Channel:** @nexushubxd

---

## ✨ Features
- ✅ Group-only game (koi DM nahi)
- ✅ Channel join check before playing
- ✅ Roles group mein hi reveal
- ✅ Sipahi ko group mein buttons milte hain
- ✅ 60 second auto timeout
- ✅ SQLite leaderboard with wins tracking
- ✅ One game per group
- ✅ Render.com ready (Worker service)

---

## 🚀 Render Pe Deploy Karo (Free)

### Step 1 — Telegram Credentials
1. **API_ID & API_HASH** → https://my.telegram.org/apps pe jao
   - Login karo → "API Development Tools"
   - App banao → `api_id` aur `api_hash` copy karo

2. **BOT_TOKEN** → Telegram pe @BotFather pe jao
   - `/newbot` command do
   - Naam rakho: `Raja Rani Bot` (ya jo chahte ho)
   - Token copy karo

### Step 2 — GitHub pe Upload
1. GitHub.com pe naya repository banao
2. Ye sab files upload karo:
   - `main.py`
   - `requirements.txt`
   - `Procfile`
   - `render.yaml`

### Step 3 — Render Deploy
1. **render.com** pe jao → Sign Up (GitHub se)
2. "New +" → **"Background Worker"** chunao
3. Apna GitHub repo connect karo
4. Ye settings:
   - **Name:** `rrcs-bot`
   - **Runtime:** `Python 3`
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `python main.py`
5. **"Environment Variables"** mein ye daalo:
   ```
   API_ID     = tumhara_api_id
   API_HASH   = tumhara_api_hash
   BOT_TOKEN  = tumhara_bot_token
   ```
6. **"Create Worker"** click karo
7. Deploy ho jaega — Logs mein `Bot start ho raha hai...` dikhega ✅

---

## ⚙️ BotFather Setup
Bot create karne ke baad:

1. @BotFather → `/setcommands` → apna bot chunao
2. Ye paste karo:
```
startgame - Naya game shuru karo
join - Game mein shamil ho
leaderboard - Top 10 scores dekho
myscore - Apna score dekho
help - Help dekho
```

3. `/setprivacy` → apna bot → **Disable** karo
   _(Taake bot group messages padh sake)_

---

## 🎮 Game Flow
```
/startgame  →  Players /join (minimum 4)
    ↓
Roles assign (group mein hi dikhte hain)
Raja publicly reveal hota hai
    ↓
Sipahi ko group mein buttons milte hain
Sipahi choose karta hai — Chor kaun hai?
    ↓
Result + Points sabko dikhte hain
Scores SQLite mein save
```

---

## 📁 Files
| File | Kaam |
|------|------|
| `main.py` | Pura bot code |
| `requirements.txt` | Python dependencies |
| `Procfile` | Render ko batata hai kaise chalana |
| `render.yaml` | Auto-config for Render |
| `.env.example` | Credentials template |
| `scores.db` | Auto-create hota hai |

---

## 📊 Commands
| Command | Description |
|---------|-------------|
| `/startgame` | Group mein naya game (group only) |
| `/join` | Game mein shamil ho |
| `/leaderboard` | Top 10 players |
| `/myscore` | Personal stats |
| `/help` | Help message |

---

## ❓ Problems?
- **Bot respond nahi kar raha** → Render logs dekho
- **Channel check fail** → Bot ko channel admin banao (ya member check off karo)
- **Score save nahi** → `scores.db` Render pe ephemeral hai — restart pe reset ho sakta hai

> Render free tier mein disk persist nahi hoti. Production ke liye paid plan lao ya external DB use karo.
