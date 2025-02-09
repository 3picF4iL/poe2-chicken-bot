# Path of Exile 2 - Chicken Bot

**Path of Exile 2 - Chicken Bot** is a simple automation tool designed for solo map clearing in *Path of Exile 2*. The bot continuously monitors your character's resource levels (HP, Mana, Shield) and automatically triggers a panic mode by simulating an ESC key press when these levels fall below a specified threshold. During panic mode, the bot also blocks the ESC and SPACE keys for 2 seconds to prevent any accidental interruption of the escape process.

## Requirements

- **Operating System:** Windows
- **Administrator Privileges:** Required for reading process memory and controlling the keyboard.
- **Python 3.x**

## Installation

1. **Download the package.**
2. **Install dependencies:**

   ```bash
   pip install -r requirements.txt
   ```

3.	**Run the bot:**

    ```bash
    python main.py
    ```

Alternatively, you can download the released executable (.exe) file.

## How to Use
1.	Launch the bot.
2.	Set your resource threshold:
    The threshold value depends on your character build and total resource pool (HP, Mana, Shield).
    It is recommended not to set the threshold lower than approximately 20% of your total resource points.
    Example:
    If your character has 1550 HP and 3800 Mana (with damage applied to mana first), the total resource pool is 5350. In this case, a threshold of around 1070 (20% of 5350) is recommended.
3.	Click the Start button.
4.	Launch the game.

## Disclaimer

Use at Your Own Risk!
The author is not responsible for any bans or adverse consequences resulting from the use of this bot. Use it only in controlled environments and during solo map clearing