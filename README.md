# Path of Exile 2 - Chicken Bot
This is a simple bot for Path of Exile 2 that will automatically try to press ESC when the character is about to die. It will also prevent from hitting ESC or SPACE by blocking those keys for 2 seconds while in panic mode.

This bot works only on the solo map clearing.

## How to start

1. Download package
2. Install dependencies with `pip install -r requirements.txt`
3. Run the bot with `python main.py`

OR

Download released .exe file

## How to use

1. Launch bot
2. Set your threshold (it depends on what char and build you have) but do not set lower values than ~20% of your summarized source points (hp, mana, shield)
   e.g. my sorc has 1550 HP and 3800 MP (where dmg hits my mana points first). My threshold is 1070 on HP for chicken bot.
   `1550 + 3800 = 5350 -> * 0.2 = 1070`
   
3. Click start
4. Launch game 

## Notes
I will not be responsible for any bans that you may receive from using this bot. Use it at your own risk.
