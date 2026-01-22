# 🤖 Telegram Secretary Bot

A personal secretary bot for Telegram that monitors all messages, categorizes them by priority, and helps manage responses.

## Features

- 📥 **Message Capture**: Monitors all incoming messages (private + groups) via Telethon userbot
- 🚨 **Real-Time Warnings**: Immediate alerts for high-priority messages (configurable threshold)
- 📊 **Smart Prioritization**: Scores messages based on mentions, questions, and high-priority senders
- 📝 **Periodic Summaries**: Sends formatted summaries every 4 hours (configurable)
- 🏷️ **Interactive Classification**: Inline buttons to classify messages as High/Medium/Low priority
- 🤖 **AI Topic Summaries**: Optional - Uses local Ollama LLM to generate 3-word topic summaries (works without Ollama, just no topic summaries)
- 🧠 **ML-Ready**: Collects labeled data for future machine learning improvements

## Project Structure

```
telegram-secretary/
├── main.py           # Entry point - runs all components
├── config.py         # Configuration management
├── database.py       # PostgreSQL connection & sessions
├── models.py         # SQLAlchemy database models
├── userbot.py        # Telethon userbot (message capture)
├── bot.py            # Telegram Bot API (client interface)
├── scheduler.py      # APScheduler (periodic summaries)
├── utils.py          # Helper functions (scoring, formatting)
├── requirements.txt  # Python dependencies
├── railway.json      # Railway deployment config
└── .gitignore        # Git ignore rules
```

## Prerequisites

1. **Python 3.11+**
2. **PostgreSQL** database
3. **Telegram API credentials** from https://my.telegram.org
4. **Telegram Bot** from @BotFather

## Setup

### 1. Clone & Install Dependencies

```bash
cd telegram-secretary
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Get Telegram Credentials

1. Go to https://my.telegram.org
2. Log in with your phone number
3. Click "API development tools"
4. Create a new application
5. Copy your `API_ID` and `API_HASH`

### 3. Create a Telegram Bot

1. Message @BotFather on Telegram
2. Send `/newbot` and follow instructions
3. Copy the bot token

### 4. Get Your User ID

1. Message @userinfobot on Telegram
2. Copy your user ID

### 5. Configure Environment

Create a `.env` file (copy from the example below):

```env
# Telegram API (from my.telegram.org)
TELEGRAM_API_ID=12345678
TELEGRAM_API_HASH=your_api_hash_here

# Your phone number (with country code)
TELEGRAM_PHONE=+5511999999999

# Bot token from @BotFather
BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrsTUVwxyz

# Your Telegram user ID
CLIENT_USER_ID=123456789

# PostgreSQL connection string
DATABASE_URL=postgresql://user:pass@localhost:5432/secretary

# Optional settings
SUMMARY_INTERVAL_HOURS=4
MAX_MESSAGES_PER_SUMMARY=15
MIN_PRIORITY_SCORE=1
WARNING_THRESHOLD_SCORE=5
TIMEZONE=America/Sao_Paulo
OLLAMA_HOST=http://localhost:11434

# Optional: Session file as base64 (for Railway deployment)
# Generate with: python -c "import base64; print(base64.b64encode(open('secretary_session.session', 'rb').read()).decode())"
# SESSION_DATA=<base64_encoded_session_file>
```

### 6. First Run (Authentication)

```bash
python main.py
```

On first run, Telethon will prompt for:
1. Your phone number (enter it)
2. The code sent to your Telegram
3. Your 2FA password (if enabled)

A session file will be created - keep it safe!

## Running

### Local Development

```bash
python main.py
```

### Railway Deployment

1. Push code to GitHub
2. Create new project on Railway
3. Add PostgreSQL addon
4. Set environment variables
5. Deploy!

**Important**: Upload your `.session` file to Railway or run the first authentication locally.

## Bot Commands

| Command | Description |
|---------|-------------|
| `/start` | Welcome message and instructions |
| `/summary` | Generate summary immediately |
| `/stats` | View message statistics |
| `/settings` | View current settings |

## Message Scoring

Messages are scored for prioritization:

| Criteria | Points |
|----------|--------|
| Contains @mention | +3 |
| Is a question (?) | +2 |
| Text > 100 chars | +1 |
| High-priority sender | +2 |

## Database Schema

### `messages` table
- Stores all captured messages
- Includes metadata (mention, question, score)
- Tracks labels and when labeled

### `high_priority_users` table
- Users marked as important
- Messages from these users get +2 score

### `user_preferences` table
- Summary interval
- Excluded chats
- Quiet hours

## Security Notes

- ⚠️ **Never commit** `.env`, `.session`, or `.db` files
- ⚠️ **Ollama Privacy**: Optional feature - By default, Ollama runs locally and never sends data externally. Keep `OLLAMA_HOST` set to `localhost` for maximum privacy. **The bot works perfectly without Ollama** - you just won't get AI-generated topic summaries.
- ⚠️ Message text is stored in your database (local SQLite or remote PostgreSQL)
- ⚠️ No message content is logged to console (only character counts)
- ⚠️ Bot only responds to the configured `CLIENT_USER_ID`
- ⚠️ Use local SQLite database for maximum privacy, or ensure remote PostgreSQL is properly secured

## Troubleshooting

### "Missing required environment variable"
Check your `.env` file has all required variables.

### "Database connection failed"
Verify `DATABASE_URL` format: `postgresql://user:pass@host:port/dbname`

### "Flood wait" errors
Telegram rate limiting. The bot handles this automatically with retries.

### Session expired
Delete the `.session` file and re-authenticate.

## Future Improvements (V1+)

- [ ] Configuration via bot commands
- [ ] Quiet hours support
- [ ] Exclude specific chats
- [ ] ML-based priority suggestions
- [ ] Response templates
- [ ] Analytics dashboard

## License

Private project - not for public distribution.

