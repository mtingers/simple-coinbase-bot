# simple-coinbase-bot
A simple Coinbase buy/sell bot.

This bot doesn't do anything fancy:
1. Buy if no outstanding sell order is <= target price
2. Target price is determined from `sell_at_percent` config option and current
fees (e.g. `current_price * (sell_at_percent+(fees*2)) + current_price)` )
3. After a buy is placed, an immediate limit sell order is set at target price for
the size amount from the buy response completed order.

# Getting Started

```bash
python3 -m venv venv
. venv/bin/activate
pip install -r requirements.txt
```
```bash
cp example.conf btc.conf
chmod 700 btc.conf
# edit config btc.conf
```

Run:
```
python simplebot.py btc.conf
```

# Example Config

See [example.conf](example.conf) for more in depth configuration info.

# Top Command

The `top.py` script displays stats from the cache files (recent order completion, profits, open orders etc).

Example usage:

```bash
# Use all .cache files in cache/ directory
python top.py cache/
```
![Top Example](/top1.png)
