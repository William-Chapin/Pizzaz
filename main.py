#IMPORTS
import discord
from discord.ext import commands as bot_commands
from discord import app_commands
import sqlite3
from datetime import datetime, timedelta
import pytz
import random

#initalize bot
bot = bot_commands.Bot(command_prefix='!', intents=discord.Intents.all())

# database is formatted as below
# users: id, slices, last_claim, started
# bakes: user_id, start_time
# inventory: user_id, item, quantity
# cooldowns: user_id, last_steal
def init_db():
    conn = sqlite3.connect('pizzas.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY, 
                    slices INTEGER,
                    last_claim TEXT,
                    started INTEGER DEFAULT 0

                )''')
    c.execute('''CREATE TABLE IF NOT EXISTS bakes (
                    user_id INTEGER PRIMARY KEY,
                    start_time TEXT
                )''')
    c.execute('''CREATE TABLE IF NOT EXISTS inventory (
                    user_id INTEGER,
                    item TEXT,
                    quantity INTEGER,
                    PRIMARY KEY (user_id, item)
                )''')
    c.execute('''CREATE TABLE IF NOT EXISTS cooldowns (
                    user_id INTEGER PRIMARY KEY,
                    last_steal TEXT
                )''')
    conn.commit()
    conn.close()

# update database 
def update_db_schema():
    conn = sqlite3.connect('pizzas.db')
    c = conn.cursor()
    try:
        c.execute('ALTER TABLE users ADD COLUMN last_claim TEXT')
    except sqlite3.OperationalError:
        pass
    try:
        c.execute('ALTER TABLE users ADD COLUMN started INTEGER DEFAULT 0')
    except sqlite3.OperationalError:
        pass
    try:
        c.execute('CREATE TABLE bakes (user_id INTEGER PRIMARY KEY, start_time TEXT)')
    except sqlite3.OperationalError:
        pass
    try:
        c.execute('CREATE TABLE inventory (user_id INTEGER, item TEXT, quantity INTEGER, PRIMARY KEY (user_id, item))')
    except sqlite3.OperationalError:
        pass
    try:
        c.execute('CREATE TABLE cooldowns (user_id INTEGER PRIMARY KEY, last_steal TEXT)')
    except sqlite3.OperationalError:
        pass
    conn.commit()
    conn.close()

# bot start
@bot.event
async def on_ready():
    init_db()
    update_db_schema()
    print('The bot has started!')

# detects messages to sync new commands
@bot.event
async def on_message(message):
    content = message.content
    author = message.author
    author_id = author.id
    # allows for syncing new commands
    if content == 'sync' and author_id == 458370571797921793:
        synced = await bot.tree.sync()
        print(f'Synced {len(synced)} command(s)')

# slash command to start a user
@bot.tree.command(name='start', description='Start your pizza journey!')
async def start(interaction: discord.Interaction):
    user_id = interaction.user.id
    conn = sqlite3.connect('pizzas.db')
    c = conn.cursor()
    c.execute('SELECT slices, started FROM users WHERE id = ?', (user_id,))
    row = c.fetchone()
    if row is None:
        c.execute('INSERT INTO users (id, slices, started) VALUES (?, ?, ?)', (user_id, 100, 1))
        message = 'Welcome to Pizzaz! Bake pizzas, collect pizza slices, and steal from other users!\nYou have been given 100 pizza slices to start! :pizza:'
    elif row[1] == 0:
        c.execute('UPDATE users SET slices = 100, started = 1 WHERE id = ?', (user_id,))
        message = 'Welcome to Pizzaz! Bake pizzas, collect pizza slices, and steal from other users!\nYou have been given 100 pizza slices to start! :pizza:'
    else:
        message = 'You have already started your journey!'
        embed = discord.Embed(title='Introduction', description=message, color=0xff0000)
        await interaction.response.send_message(embed=embed)
        conn.close()
        return
    conn.commit()
    conn.close()
    embed = discord.Embed(title='Introduction', description=message, color=0x00ff00)
    await interaction.response.send_message(embed=embed)


# claim daily slices

@bot.tree.command(name='daily', description='Claim your daily pizza slices!')
async def daily(interaction: discord.Interaction):
    user_id = interaction.user.id
    conn = sqlite3.connect('pizzas.db')
    c = conn.cursor()
    c.execute('SELECT slices, last_claim, started FROM users WHERE id = ?', (user_id,))
    row = c.fetchone()
    
    if row is None or row[2] == 0:
        embed = discord.Embed(title='Daily Pizza Slices', description='Run the /start command first to get started!', color=0xff0000)
        await interaction.response.send_message(embed=embed)

        conn.close()

        return
    
    est = pytz.timezone('US/Eastern')
    now = datetime.now(est)
    today = now.date()
    
    # next midnight (resets at midnight EST)
    next_midnight = datetime.combine(today + timedelta(days=1), datetime.min.time(), tzinfo=est)
    next_midnight_timestamp = int(next_midnight.timestamp())
    

    if row[0] is None:
        amount = random.randint(1, 20)
        c.execute('INSERT INTO users (id, slices, last_claim) VALUES (?, ?, ?)', (user_id, amount, today.isoformat()))
        slices = amount
    else:
        last_claim = datetime.fromisoformat(row[1]).date() if row[1] else None
        if last_claim == today:

            embed = discord.Embed(
                title='Daily Pizza Slices',
                description=f'You have already claimed your daily pizza slices today!\nCome back <t:{next_midnight_timestamp}:R>!',
                color=0xff0000
            )
            await interaction.response.send_message(embed=embed)
            conn.close()
            return
        amount = random.randint(1, 20)
        slices = row[0] + amount
        c.execute('UPDATE users SET slices = ?, last_claim = ? WHERE id = ?', (slices, today.isoformat(), user_id))
    
    conn.commit()
    conn.close()
    embed = discord.Embed(title='Daily Pizza Slices', description=f'You have claimed {amount} pizza slices!\nYou now have **{slices}** slices :pizza:', color=0x00ff00)
    await interaction.response.send_message(embed=embed)

# check balance of a user
@bot.tree.command(name='balance', description='Show a user\'s pizza slice balance.')
@app_commands.describe(user='The user to check (optional)')
async def balance(interaction: discord.Interaction, user: discord.User = None):
    if user is None:
        user = interaction.user
    user_id = user.id
    conn = sqlite3.connect('pizzas.db')
    c = conn.cursor()
    c.execute('SELECT slices, started FROM users WHERE id = ?', (user_id,))
    row = c.fetchone()
    
    if row is None:
        if user == interaction.user:
            embed = discord.Embed(title='Pizza Slice Balance', description='Run the /start command first to get started!', color=0xff0000)
        else:
            embed = discord.Embed(title='Pizza Slice Balance', description=f'{user.mention} has no pizza slices!', color=0xff0000)
    elif row[1] == 0 and user == interaction.user:
        embed = discord.Embed(title='Pizza Slice Balance', description='Run the /start command first to get started!', color=0xff0000)
    else:
        slices = row[0]
        embed = discord.Embed(title='Pizza Slice Balance', description=f'{user.mention} has **{slices}** pizza slices :pizza:', color=0x00ff00)
    
    await interaction.response.send_message(embed=embed)
    conn.close()

# resets a user (ADMIN COMMAND)
@bot.tree.command(name='reset', description='Resets a user. Scary!')

@app_commands.describe(user='The user to reset')
async def reset(interaction: discord.Interaction, user: discord.User):
    user_id = user.id
    conn = sqlite3.connect('pizzas.db')
    c = conn.cursor()
    # deletes user from all tables
    c.execute('DELETE FROM users WHERE id = ?', (user_id,))
    c.execute('DELETE FROM bakes WHERE user_id = ?', (user_id,))
    c.execute('DELETE FROM inventory WHERE user_id = ?', (user_id,))
    c.execute('DELETE FROM cooldowns WHERE user_id = ?', (user_id,))
    conn.commit()

    conn.close()
    embed = discord.Embed(title='User Reset', description=f'User {user.mention} has been reset and deleted from the database.', color=0xff0000)
    await interaction.response.send_message(embed=embed)

# pizza baking view class
class BakeView(discord.ui.View):
    def __init__(self, user_id):
        super().__init__(timeout=None)

        self.user_id = user_id

    # CHEESE PIZZA
    @discord.ui.button(label="Cheese Pizza (Cost: 4 slices)", style=discord.ButtonStyle.primary)
    async def bake_cheese(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.bake_pizza(interaction, "Cheese Pizza", 4)

    # PINEAPPLE PIZZA

    @discord.ui.button(label="Pineapple Pizza (Cost: 6 slices)", style=discord.ButtonStyle.primary)
    async def bake_pineapple(self, interaction: discord.Interaction, button: discord.ui.Button):

        await self.bake_pizza(interaction, "Pineapple Pizza", 6)

    async def bake_pizza(self, interaction: discord.Interaction, pizza_type: str, cost: int):

        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This button is not for you!", ephemeral=True)
            return

        conn = sqlite3.connect('pizzas.db')
        c = conn.cursor()

        c.execute('SELECT slices FROM users WHERE id = ?', (self.user_id,))
        user_row = c.fetchone()

        if user_row[0] < cost:
            await interaction.response.send_message(f"You do not have enough slices to bake a {pizza_type}!", ephemeral=True)
            conn.close()
            return

        start_time = datetime.now().isoformat()

        c.execute('INSERT INTO bakes (user_id, start_time) VALUES (?, ?)', (self.user_id, start_time))
        c.execute('UPDATE users SET slices = slices - ? WHERE id = ?', (cost, self.user_id))

        conn.commit()
        conn.close()

        next_ready_time = datetime.now() + timedelta(minutes=8)
        next_ready_timestamp = int(next_ready_time.timestamp())
        embed = discord.Embed(title='Bake Pizza', description=f'Your {pizza_type} is baking! It will be ready <t:{next_ready_timestamp}:R>.', color=0x00ff00)
        await interaction.response.edit_message(embed=embed, view=None)


# claim view class for claiming pizzas after they are done baking
class ClaimView(discord.ui.View):
    def __init__(self, user_id):
        super().__init__(timeout=None)
        self.user_id = user_id

    @discord.ui.button(label="Claim Pizza", style=discord.ButtonStyle.success)

    async def claim_pizza(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This button is not for you!", ephemeral=True)
            return

        conn = sqlite3.connect('pizzas.db')
        c = conn.cursor()
        c.execute('SELECT start_time FROM bakes WHERE user_id = ?', (self.user_id,))
        bake_row = c.fetchone()

        if bake_row is None:
            await interaction.response.send_message("You do not have any pizzas baking!", ephemeral=True)
            conn.close()
            return


        start_time = datetime.fromisoformat(bake_row[0])
        now = datetime.now()
        if now < start_time + timedelta(minutes=8):
            remaining_time = (start_time + timedelta(minutes=8) - now).total_seconds()
            await interaction.response.send_message(f'Your pizza is not ready yet! Come back <t:{int((now + timedelta(seconds=remaining_time)).timestamp())}:R>!', ephemeral=True)
            conn.close()
            return


        c.execute('DELETE FROM bakes WHERE user_id = ?', (self.user_id,))


        c.execute('INSERT INTO inventory (user_id, item, quantity) VALUES (?, ?, 1) ON CONFLICT(user_id, item) DO UPDATE SET quantity = quantity + 1', (self.user_id, 'Cheese Pizza'))

        conn.commit()
        conn.close()
        embed = discord.Embed(title='Claim Pizza', description='Your pizza is ready! It has been added to your inventory.', color=0x00ff00)

        await interaction.response.edit_message(embed=embed, view=None)

# bake command, bakes a pizza
@bot.tree.command(name='bake', description='Bake a pizza.')

async def bake(interaction: discord.Interaction):
    user_id = interaction.user.id
    conn = sqlite3.connect('pizzas.db')
    c = conn.cursor()
    c.execute('SELECT slices, started FROM users WHERE id = ?', (user_id,))
    user_row = c.fetchone()

    if user_row is None or user_row[1] == 0:
        embed = discord.Embed(title='Bake Pizza', description='Run the /start command first to get started!', color=0xff0000)
        await interaction.response.send_message(embed=embed, ephemeral=True)
        conn.close()
        return

    c.execute('SELECT start_time FROM bakes WHERE user_id = ?', (user_id,))
    bake_row = c.fetchone()

    if bake_row is not None:
        start_time = datetime.fromisoformat(bake_row[0])
        now = datetime.now()
        if now >= start_time + timedelta(minutes=8):
            view = ClaimView(user_id)
            embed = discord.Embed(title='Claim Pizza', description='Your pizza is ready! Click the button below to claim it.', color=0x00ff00)
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        else:
            remaining_time = (start_time + timedelta(minutes=8) - now).total_seconds()
            embed = discord.Embed(title='Bake Pizza', description=f'Your pizza is still baking! Come back <t:{int((now + timedelta(seconds=remaining_time)).timestamp())}:R>!', color=0xff0000)
            await interaction.response.send_message(embed=embed, ephemeral=True)
        conn.close()
        return


    view = BakeView(user_id)

    embed = discord.Embed(title='Bake Pizza', description='Select the type of pizza you want to bake:', color=0x00ff00)
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

# inventory, goes here after baking a pizza
@bot.tree.command(name='inventory', description='Check your inventory.')
async def inventory(interaction: discord.Interaction):
    user_id = interaction.user.id
    conn = sqlite3.connect('pizzas.db')

    c = conn.cursor()
    c.execute('SELECT item, quantity FROM inventory WHERE user_id = ? AND quantity > 0', (user_id,))
    rows = c.fetchall()
    conn.close()

    if not rows:
        embed = discord.Embed(title='Inventory', description='Your inventory is empty!', color=0xff0000)
    else:
        description = '\n'.join([f'{row[1]}x {row[0]}' for row in rows])
        embed = discord.Embed(title='Inventory', description=description, color=0x00ff00)
    await interaction.response.send_message(embed=embed)

# sell items in inventory (pizzas)
@bot.tree.command(name='sell', description='Sell a pizza from your inventory.')
@app_commands.describe(item='The item to sell')
async def sell(interaction: discord.Interaction, item: str):
    user_id = interaction.user.id
    conn = sqlite3.connect('pizzas.db')
    c = conn.cursor()
    c.execute('SELECT quantity FROM inventory WHERE user_id = ? AND item = ?', (user_id, item))
    row = c.fetchone()

    if row is None or row[0] == 0:
        embed = discord.Embed(title='Sell Pizza', description=f'You do not have any {item} to sell!', color=0xff0000)
        await interaction.response.send_message(embed=embed, ephemeral=True)
        conn.close()
        return

    # PRICES
    if item == 'Cheese Pizza':
        price = 10
    elif item == 'Pineapple Pizza':
        price = 15
    else:
        # default if something breaks
        price = 10

    c.execute('UPDATE inventory SET quantity = quantity - 1 WHERE user_id = ? AND item = ?', (user_id, item))
    c.execute('UPDATE users SET slices = slices + ? WHERE id = ?', (price, user_id))
    conn.commit()
    conn.close()
    embed = discord.Embed(title='Sell Pizza', description=f'You have sold 1 {item} for {price} slices!', color=0x00ff00)
    await interaction.response.send_message(embed=embed, ephemeral=True)

# auto complete items in inventory for selling
@sell.autocomplete('item')
async def sell_autocomplete(interaction: discord.Interaction, current: str):
    user_id = interaction.user.id
    conn = sqlite3.connect('pizzas.db')
    c = conn.cursor()
    c.execute('SELECT item FROM inventory WHERE user_id = ?', (user_id,))
    rows = c.fetchall()
    conn.close()

    choices = [app_commands.Choice(name=row[0], value=row[0]) for row in rows if current.lower() in row[0].lower()]
    return choices

# steal slices from other people
@bot.tree.command(name='steal', description='Steal pizza slices from another user.')
@app_commands.describe(target='The user to steal from')
async def steal(interaction: discord.Interaction, target: discord.User):
    user_id = interaction.user.id
    target_id = target.id

    if user_id == target_id:
        embed = discord.Embed(title='Steal Pizza Slices', description='You cannot steal from yourself!', color=0xff0000)
        await interaction.response.send_message(embed=embed)
        return
    
    conn = sqlite3.connect('pizzas.db')
    c = conn.cursor()

    c.execute('SELECT started FROM users WHERE id = ?', (user_id,))
    row = c.fetchone()
    if row is None or row[0] == 0:
        embed = discord.Embed(title='Steal Pizza Slices', description='Run the /start command first to get started!', color=0xff0000)
        await interaction.response.send_message(embed=embed)
        conn.close()
        return

    c.execute('SELECT slices FROM users WHERE id = ?', (target_id,))
    target_row = c.fetchone()
    if target_row is None or target_row[0] <= 100:
        embed = discord.Embed(title='Steal Pizza Slices', description=f'{target.mention} caught you trying to steal from the poor!', color=0xff0000)
        await interaction.response.send_message(embed=embed)
        conn.close()
        return

    c.execute('SELECT last_steal FROM cooldowns WHERE user_id = ?', (user_id,))
    cooldown_row = c.fetchone()
    now = datetime.now()
    if cooldown_row is not None:
        last_steal = datetime.fromisoformat(cooldown_row[0])
        if now < last_steal + timedelta(hours=3):
            remaining_time = (last_steal + timedelta(hours=3) - now).total_seconds()
            embed = discord.Embed(title='Steal Pizza Slices', description=f'You can steal again <t:{int((now + timedelta(seconds=remaining_time)).timestamp())}:R>!', color=0xff0000)
            await interaction.response.send_message(embed=embed)
            conn.close()
            return

    amount = random.randint(1, 15)
    success = random.choice([True, False])

    if success:
        c.execute('UPDATE users SET slices = slices - ? WHERE id = ?', (amount, target_id))
        c.execute('UPDATE users SET slices = slices + ? WHERE id = ?', (amount, user_id))
        result_message = f'{interaction.user.mention} has successfully stolen {amount} pizza slices from {target.mention}!'
    else:
        # caught
        c.execute('UPDATE users SET slices = slices + ? WHERE id = ?', (amount, target_id))
        c.execute('UPDATE users SET slices = slices - ? WHERE id = ?', (amount, user_id))
        result_message = f'{interaction.user.mention} tried to steal from {target.mention} but got caught! {target.mention} has gained {amount} pizza slices and {interaction.user.mention} has lost {amount} pizza slices!'

    c.execute('INSERT INTO cooldowns (user_id, last_steal) VALUES (?, ?) ON CONFLICT(user_id) DO UPDATE SET last_steal = ?', (user_id, now.isoformat(), now.isoformat()))
    conn.commit()
    conn.close()

    embed = discord.Embed(title='Steal Attempt', description=result_message, color=0x00ff00 if success else 0xff0000)
    await interaction.response.send_message(content=target.mention, embed=embed)

# MORE FEATURES TO COME SOON
# MORE FEATURES TO COME SOON
# MORE FEATURES TO COME SOON

# REPLACE WITH YOUR BOT TOKEN
# CREATE A BOT AT https://discord.com/developers
bot.run('REPLACE WITH YOUR TOKEN')