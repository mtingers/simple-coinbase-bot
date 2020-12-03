# simple-coinbase-bot
A simple Coinbase Pro buy/sell bot.

The primary purpose of this bot is to buy/sell incrementally as the price goes up and down.
It does not do anything too fancy:
1. Buy if there are no outstanding sell orders less than the current target sell price.
2. Target sell price is determined from `sell_at_percent` config option and current
fees (e.g. `current_price * (sell_at_percent+(fees*2)) + current_price)` ).
See [Coinbase Fee structure](https://help.coinbase.com/en/pro/trading-and-funding/trading-rules-and-fees/fees)
3. After a buy is placed, an immediate limit sell order is placed to the calculated target price.

A few other min/max configuration options exist for safety, but the main logic is
above (see [example.conf](example.conf)).

# Getting Started
First, create an API key with view/trade permissions in the
[Coinbase Pro profile](https://pro.coinbase.com/profile/api).

Create virtualenv and install requirements:
```bash
python3 -m venv venv
. venv/bin/activate
```

```bash
# PyPI
pip install SimpleCoinbaseBot
```

```bash
# Or install manually with setup.py
pip install -r requirements.txt
python setup.py install
```

Create a new configuration:
```bash
mkdir etc/ log/ cache/
cp example.conf etc/btc.conf
chmod 700 etc/btc.conf
# edit config etc/btc.conf
```

Run the bot with the new config:
```
simplebot etc/btc.conf
# -or- run the wrapper that will restart the bot if it errors out
persistbot etc/btc.conf
```

# Example Config

See [example.conf](example.conf) for more in depth configuration info.

# Top Command

The `simpeltop` script displays stats from the cache files (recent order completion, profits, open
orders, etc).

Example usage:

```bash
# Use all .cache files in cache/ directory
simpletop cache/
```
![Top Example](/top1.png)
