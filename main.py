import os
import discord
import aiohttp
import asyncio
from dotenv import load_dotenv

from keep_alive import keep_alive

intents = discord.Intents.default()
intents.messages = True
intents.message_content = True
client = discord.Client(intents=intents)

load_dotenv(verbose=True)

async def fetch_tsv(url):
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            text = await resp.text()
            rows = [line.split("\t") for line in text.strip().split("\n")]
            return rows

@client.event
async def on_ready():
    print("ログインしました")

@client.event
async def on_message(message):
    if message.author == client.user:
        return

    if message.content.lower() == "event":
        await message.channel.send("イベントだよ！")

    if message.content.startswith("sale "):
        _, sale_id = message.content.split(" ", 1)
        url = "https://shibanban2.github.io/bc-event/token/sale.tsv"
        rows = await fetch_tsv(url)

        found = None
        for row in rows:
            if sale_id in row:  # 行にそのIDが含まれていれば
                found = "\t".join(row)
                break

        if found:
            await message.channel.send(found)
        else:
            await message.channel.send(f"ID {sale_id} は見つかりませんでした")

keep_alive()

TOKEN = os.getenv("DISCORD_TOKEN")
if TOKEN:
    client.run(TOKEN)
else:
    print("Tokenが見つかりませんでした")


