#!/bin/bash
set -e

# Ask for BOT_TOKEN
read -p "Enter your Telegram Bot Token: " BOT_TOKEN
VPS_IP=$(curl -s ifconfig.me)

echo "📦 Updating system..."
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3 python3-pip python3-venv ffmpeg nginx

echo "📂 Setting up project..."
cd ~/ || exit
rm -rf telegram-video-bot
git clone https://github.com/YOUR_GITHUB/telegram-video-bot.git
cd telegram-video-bot

python3 -m venv bot_env
source bot_env/bin/activate
pip install -r bot/requirements.txt

echo "🔑 Writing config..."
cat > bot/config.py <<EOF
BOT_TOKEN = "$BOT_TOKEN"
VPS_IP = "$VPS_IP"
EOF

echo "⚙️ Installing systemd service..."
sudo cp video-bot.service /etc/systemd/system/video-bot.service
sudo systemctl daemon-reload
sudo systemctl enable video-bot
sudo systemctl restart video-bot

sudo touch /var/log/video-bot.log
sudo chown $USER:$USER /var/log/video-bot.log

echo "✅ Done! Bot running. Check logs: sudo journalctl -u video-bot -f"
