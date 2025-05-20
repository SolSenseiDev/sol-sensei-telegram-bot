# 🚀 SolSensei – Your Guide in the Solana Ecosystem

**SolSensei** is a modular Telegram-based platform for automating token trading in the **Solana** network.  
The bot provides powerful tools for multi-wallet trading, contract analysis, portfolio tracking, and secure interaction with decentralized protocols. The architecture is built on modern asynchronous Python frameworks with a focus on performance and scalability.

---

## 🔥 Features

- ✅ **Token Scanner**: contract analysis, market cap, volume, holder count, links to DEX Screener  
- 💼 **Portfolio Tracking**: view balances and positions across connected wallets  
- 💱 **Buy/Sell Tokens**: execute token swaps from one or multiple wallets simultaneously  
- 🔁 **Trading Strategies**: DCA support, batch selling, and predefined strategy templates  
- 🔐 **Non-custodial**: private keys stay on the user's side; all transactions are signed locally  
- ⚡ **Optimized RPC Layer**: integrated with an official Solana RPC provider

---

## 🏗 Technologies Used

SolSensei is built using modern Python tooling and reliable server infrastructure:

### Language & Frameworks:
- `Python 3.11+`
- `aiogram v3` — async Telegram framework  
- `asyncio`, `aiohttp`, `httpx` — asynchronous request handling  
- `websockets` — real-time data streams  
- `FastAPI`, `uvicorn` — internal APIs  
- `Jinja2`, `markdown2` — templating engine

### Blockchain Integration:
- `Jupiter Aggregator API` — token swaps  
- `Solana RPC` — official RPC provider  
- `Solscan`, `SolanaFM`, `Tensor API` — metadata and transaction history  
- `solana-py`, `base58`, `borsh`, `construct` — low-level Solana interactions

### Data Storage:
- `PostgreSQL` — main database  
- `SQLAlchemy`, `asyncpg` — ORM and DB drivers  
- `Redis` — caching, pub/sub, task queues

### Security:
- `dotenv` — environment configuration  
- `cryptography`, `hashlib`, `secrets` — secure key handling  
- `ratelimit`, `slowapi` — anti-spam and rate limiting

### Deployment:
- `Docker`, `docker-compose` — containerization  
- `Railway.app`, `Render`, `UptimeRobot` — hosting and monitoring

---

## 🎁 Refer-to-Earn Airdrop System

SolSensei implements a referral-based airdrop system to reward active users and promote community growth.

### 🔗 How it works:

- Each user gets a **unique referral link**  
- New users who join via your link and remain active will earn you points  
- Points accumulate and convert into **airdrop allocations**  
- Top referrers gain access to new features, beta modules, and exclusive bonuses

### 🪂 Eligibility:

- Regular use of SolSensei tools  
- Connected and active wallets  
- Referral activity  
- Participation in testing and feedback

> 📢 Launch dates, reward structure, and rules will be announced in the Telegram channel.

---

## 📬 Contact

- Telegram Bot: [@SolSenseiBot](https://t.me/SolSenseiBot)  
- Twitter: [@SolSensei](https://twitter.com/SolSensei)  
- Email: [solsenseibot@gmail.com](mailto:solsenseibot@gmail.com)

---

> 🧘 SolSensei is more than just a bot — it’s your reliable tool in the Solana world.
