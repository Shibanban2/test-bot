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

# ---------- TSV 読み込み ----------
async def fetch_tsv(url):
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            text = await resp.text()
            rows = [line.split("\t") for line in text.strip().split("\n")]

            # 各行の末尾に "0" を追加（空欄の行は無視）
            processed = []
            for row in rows:
                if "".join(row).strip() == "":
                    continue
                row = row + ["0"]
                processed.append(row)

            return processed

# ---------- ステージ名辞書 ----------
def load_stage_dict(path="stage.tsv"):
    stage_dict = {}
    if not os.path.exists(path):
        return stage_dict

    with open(path, "r", encoding="utf-8") as f:
        lines = [line.strip() for line in f if line.strip()]

    # 偶数行が ID、奇数行が名前
    for i in range(0, len(lines), 2):
        try:
            stage_id = int(lines[i])
            stage_name = lines[i + 1] if i + 1 < len(lines) else ""
            stage_dict[stage_id] = stage_name
        except ValueError:
            continue
    return stage_dict

stage_dict = load_stage_dict()

# ---------- 逆順で ID 抽出 ----------
def extract_ids(row):
    nums = []
    for v in row:
        try:
            nums.append(int(v))
        except ValueError:
            continue

    ids = []
    for i in range(len(nums) - 2, -1, -1):
        val = nums[i]
        is_valid = (50 <= val <= 60) or (100 <= val <= 199) or (val >= 1000)
        if is_valid:
            ids.insert(0, val)  # unshift 相当
        else:
            break
    return ids

# ---------- Discord イベント ----------
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
        url = "https://shibanban2.github.io/bc-event/token/sale.tsv"
        rows = await fetch_tsv(url)

        found_rows = []
        for row in rows:
            if sale_id in row:
                ids = extract_ids(row)
                # ID → 名前に変換
                names = [stage_dict.get(i, "") for i in ids]
                # 出力整形
                found_rows.append(
                    f"[{', '.join(str(i) for i in ids)} {', '.join(n for n in names if n)}]\n"
                    f"{row[0][:4]}/{row[0][4:6]}/{row[0][6:8]}({row[1]})〜"
                    f"{row[2][:4]}/{row[2][4:6]}/{row[2][6:8]}({row[3]})\n"
                    f"v:{row[4]}-{row[5]}\n"
                    f"{row[3]}"  # D列相当
                )

        if found_rows:
            reply = "\n\n".join(found_rows)
            await message.channel.send(f"```\n{reply}\n```")
        else:
            await message.channel.send(f"ID {sale_id} は見つかりませんでした")

# ---------- 実行 ----------
keep_alive()

TOKEN = os.getenv("DISCORD_TOKEN")
if TOKEN:
    client.run(TOKEN)
else:
    print("Tokenが見つかりませんでした")