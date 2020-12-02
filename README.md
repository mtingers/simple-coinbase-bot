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
cp simplebot-example.conf simplebot.conf
chmod 700 simplebot.conf
# edit config simplebot.conf
```

Run:
```
python simplebot.py simplebot.conf
```

# Example Config

```txt
[auth]
key = xyz
passphrase = 123
b64secret = abc

[general]
# How many seconds to sleep between polling. You should probably
# keep around 60 seconds to avoid polling too often (it's not a realtime
# order-book tracker)
sleep_seconds = 60
log_file = log/simplebot.log
cache_file = cache/simplebot.cache


[market]
coin = BTC-USD

# The price increase to sell at from the bought price.
# Fees are added in to this total and accounted for.
# Example:
# bought_price = 100.0, sell_at_percent = 1.0
# sell_price = bought_price + (bought_price * (sell_at_percent/100.0 + fees))
sell_at_percent = 1.0

# How much of your total USD wallet can be used each buy.
buy_wallet_percent = 7.5


[limits]
# Limits to avoid buying in too much in a specific range or time period

# Maximum number of outstanding sell orders. If reached, no more buys can be placed.
max_sells_outstanding = 15

# Maximum amount of buys per hour
max_buys_per_hour = 10


[notify]
mail_host = mail.example.com
mail_from = foo@example.com
mail_to = email1@example.com, email2@example.com


[debug]
# Enable Coinbase API response debug logging
debug_log_response = False
debug_log_response_file = debug1.log
```

# Top Command

The `top.py` script displays stats from the cache files (recent order completion, profits, open orders etc).

Example usage:

```bash
# Use all .cache files in cache/ directory
python top.py cache/

                                                                                 2020-12-02 04:52:15-UTC
---------------------------------------------------------------------------------------------------------
   Coin         Profits            Open            Done           Error        Avg-Time      Avg-Profit
---------------------------------------------------------------------------------------------------------
BTC-USD           $6.55              10               7               0        03:07:57           $0.94
ETH-USD           $3.46               9               8               0        01:16:55           $0.43
LTC-USD           $3.64              10              14               0        01:17:57           $0.26
REP-USD           $1.08               5              11               0        01:19:37           $0.10
XLM-USD           $2.11              10               5               0        00:41:23           $0.42
XRP-USD           $0.29               2               1               1        02:23:11           $0.29
---------------------------------------------------------------------------------------------------------
    all          $17.13              46              46               1        01:41:10           $0.41
---------------------------------------------------------------------------------------------------------

Recently completed:
    LTC-USD $0.22 duration:00:06:52 ago:01:14:54
    LTC-USD $0.22 duration:00:58:42 ago:01:11:45
```

