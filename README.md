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
cp bot1-example.conf bot1.conf
chmod 700 bot1-example.conf
# edit config
python bot1.py bot1.conf
```

# Example Config

```txt
[auth]
key = xyz
passphrase = 123
b64secret = abc

[general]
# sell_at_percent will set a target price from the buy price
# this percent adds fees in (fees+sell_at_percent) to find the
# target sell price
sell_at_percent = 1.0
coin = BTC-USD
logfile = bot1.log
mail_host = mail.example.com
mail_from = foo@example.com
mail_to = email1@example.com, email2@example.com
sleepsecs = 60
buy_wallet_percent = 10.0
# Enable Coinbase API response debug logging
debug_log_response = False
debug_log_response_file = debug1.log
```

