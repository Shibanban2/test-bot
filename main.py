import os
from os.path import dirname, join

import discord
from dotenv import load_dotenv

from keep_alive import keep_alive

intents = discord.Intents.default()
intents.messages = True   # メッセージ受信のIntentを有効化
intents.message_content = True  # メッセージ内容を受け取れるようにする
client = discord.Client(intents=intents)

load_dotenv(verbose=True)

@client.event
async def on_ready():
    print("ログインしました")

@client.event
async def on_message(message):
    # Bot自身のメッセージは無視
    if message.author == client.user:
        return

    # メッセージが "event" の場合に返信
    if message.content.lower() == "event":
        await message.channel.send("イベントだよ！")

keep_alive()

TOKEN = os.getenv("DISCORD_TOKEN")
if TOKEN:
    client.run(TOKEN)
else:
    print("Tokenが見つかりませんでした")

