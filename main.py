import os
from os.path import dirname, join

import discord
from dotenv import load_dotenv

from keep_alive import keep_alive

client = discord.Client(intents=discord.Intents.default())

load_dotenv(verbose=True)

@client.event
async def on_ready():
    print("ログインしました")


keep_alive()

TOKEN = os.getenv("DISCORD_TOKEN")
if TOKEN:
    client.run(TOKEN)
else:
    print("Tokenが見つかりませんでした")
