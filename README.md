# 🚀 SolSensei – Smart Trading Bot for Solana

**SolSensei** is a powerful trading bot designed for analyzing and interacting with tokens on the **Solana** blockchain. It features fast contract scanning, wallet management tools, and a Telegram interface for seamless user experience.

---

## 🔥 Features

- ✅ **Token Scanner**: contract address checks, market cap, liquidity, and holder count  
- 📊 **Early Buyer Analysis**: calculates how much supply was bought in the first 20 transactions  
- 🧠 **Wallet Insights**: shows the creator wallet and top holders  
- 💬 **Telegram Bot Interface**: simple commands to scan and monitor tokens directly in chat  
- 🔁 **SOL Sweep Tool**: withdraw all SOL from connected wallets to a specified address  
- ⚡ **Fast RPC via Helius**: optimized for real-time scans with low latency

---

## 🛠️ Tech Stack

- **Solana RPC / Helius / Solscan API**  
- **Python**: `asyncio`, `aiogram v3`, `requests`, `websockets`  
- **PostgreSQL**: for persistent storage  
- **Redis**: for caching and pub/sub  
- **Docker**: for deployment and containerization  
- **WebSocket Server**: for real-time frontend interaction

---

## ⚡ Getting Started

```bash
# 1. Clone the repository
git clone https://github.com/yourname/solsensei-bot.git
cd solsensei-bot

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure environment variables
cp .env.example .env
nano .env

# 4. Start the bot
python main.py
