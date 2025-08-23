import os
import discord
import aiohttp
from dotenv import load_dotenv
from keep_alive import keep_alive

intents = discord.Intents.default()
intents.messages = True
intents.message_content = True
client = discord.Client(intents=intents)

load_dotenv(verbose=True)

# -------------------- TSV 読み込み --------------------
async def fetch_tsv(url):
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            text = await resp.text()
            rows = [line.split("\t") for line in text.strip().split("\n")]
            # 末尾に "0" を追加
            processed = []
            for row in rows:
                if "".join(row).strip() == "":
                    continue
                row = row + ["0"]
                processed.append(row)
            return processed

async def fetch_stage_map(url):
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            text = await resp.text()
            stage_map = {}
            for line in text.strip().split("\n"):
                if line.strip() == "":
                    continue
                id_str, name = line.strip().split("\t")
                stage_map[int(id_str)] = name
            return stage_map

# -------------------- 日付・時間・バージョン整形 --------------------
def format_time(t):
    n = int(t)
    hh = str(n // 100).zfill(2)
    mm = str(n % 100).zfill(2)
    return f"{hh}:{mm}"

def format_date(date_num, time_num):
    d = str(date_num).zfill(8)
    t = str(time_num).zfill(4)
    return f"{d[:4]}/{d[4:6]}/{d[6:]}({format_time(t)})"

def format_ver(min_ver, max_ver):
    return f"v:{min_ver}-{max_ver}"

# -------------------- ID抽出 --------------------
def extract_ids(row):
    nums = [int(x) for x in row if x.isdigit()]
    ids = []
    for val in reversed(nums[:-1]):
        if val >= 50 and (val <= 60 or (val >= 100 and val <= 199) or val >= 1000):
            ids.insert(0, val)
        else:
            break
    return ids

# -------------------- Discord イベント --------------------
@client.event
async def on_ready():
    print("ログインしました")

@client.event
async def on_message(message):
    if message.author == client.user:
        return

    if message.content.lower() == "ping":
        await message.channel.send("Pong.")

    if message.content.startswith("sale "):
        _, sale_id = message.content.split(" ", 1)
        sale_url = "https://shibanban2.github.io/bc-event/token/sale.tsv"
        stage_url = "https://shibanban2.github.io/bc-event/token/stage.tsv"

        rows = await fetch_tsv(sale_url)
        stage_map = await fetch_stage_map(stage_url)

        found = []
        for row in rows:
            ids = extract_ids(row)
            if int(sale_id) in ids:
                # 日付は row[0]〜row[3]、D列は row[-1]
                start_date = int(row[0])
                start_time = int(row[1])
                end_date = int(row[2])
                end_time = int(row[3])
                title = stage_map.get(int(sale_id), "")
                ver_str = format_ver(row[4], row[5])
                note = row[-1]
                text = f"[{sale_id} {title}]\n{format_date(start_date, start_time)}〜{format_date(end_date, end_time)}\n{ver_str}\n{note}"
                found.append(text)

        if found:
            reply = "\n\n".join(found)
            await message.channel.send(f"```\n{reply}\n```")
        else:
            await message.channel.send(f"ID {sale_id} は見つかりませんでした")

keep_alive()

TOKEN = os.getenv("DISCORD_TOKEN")
if TOKEN:
    client.run(TOKEN)
else:
    print("Tokenが見つかりませんでした")