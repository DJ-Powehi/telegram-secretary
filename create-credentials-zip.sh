#!/bin/bash
# Script to create credentials zip file

echo "📝 Creating credentials file..."

cat > CREDENTIALS.txt << 'CREDEOF'
# Telegram Secretary Bot - Credentials
# Fill in the values below with your actual credentials

# Telegram API Credentials (from https://my.telegram.org)
TELEGRAM_API_ID=
TELEGRAM_API_HASH=

# Your phone number (with country code, e.g., +5511999999999)
TELEGRAM_PHONE=

# Bot Token (from @BotFather on Telegram)
BOT_TOKEN=

# Your Telegram User ID (get from @userinfobot)
CLIENT_USER_ID=

# Instructions for the other developer:
# 1. Copy these values to their .env file
# 2. DO NOT commit this file to Git!
CREDEOF

echo "✅ CREDENTIALS.txt created"
echo ""
echo "📋 Now please:"
echo "   1. Open CREDENTIALS.txt and fill in your actual values"
echo "   2. Save the file"
echo "   3. Run this script again to create the zip"
echo ""
read -p "Press Enter after you've filled in CREDENTIALS.txt..."

if [ -f CREDENTIALS.txt ]; then
    echo "📦 Creating zip file..."
    zip -j telegram-secretary-credentials.zip CREDENTIALS.txt
    echo "✅ Zip file created: telegram-secretary-credentials.zip"
    echo ""
    echo "📤 To send this file:"
    echo "   - Email it as an attachment"
    echo "   - Upload to Google Drive/Dropbox and share link"
    echo "   - Send via Telegram/WhatsApp"
    echo "   - Use a secure file sharing service"
else
    echo "❌ CREDENTIALS.txt not found!"
fi
