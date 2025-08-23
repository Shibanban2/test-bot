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

# ===== TSV 読み込み処理 =====
async def fetch_tsv(url):
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            text = await resp.text()
            rows = [line.split("\t") for line in text.strip().split("\n")]

            processed = []
            for row in rows:
                if "".join(row).strip() == "":
                    continue
                # 末尾が "0" または "1" でなければ追加
                if row[-1] not in ("0", "1"):
                    row = row + ["0"]
                processed.append(row)
            return processed

# ===== stage.tsv を dict 化 =====
async def load_stage_map():
    url = "https://shibanban2.github.io/bc-event/token/stage.tsv"
    rows = await fetch_tsv(url)
    stage_map = {}
    for row in rows:
        if len(row) >= 2:
            try:
                stage_id = int(row[0])
                stage_name = row[1]
                stage_map[stage_id] = stage_name
            except ValueError:
                continue
    return stage_map

# ===== ID 抽出 (逆順, GAS 仕様) =====
def extract_ids(row):
    nums = []
    for v in row:
        try:
            nums.append(int(v))
        except ValueError:
            continue

    ids = []
    for i in range(len(nums) - 2, -1, -1):  # 後ろから2つ目から逆順
        val = nums[i]
        is_valid = (50 <= val <= 60) or (100 <= val <= 199) or (val >= 1000)
        if is_valid:
            ids.insert(0, val)  # unshift
        else:
            break
    return ids

# ===== parseSchedule (GASのD列相当) =====
def parse_schedule(row):
    """
    row: sale.tsv の 1行 (list[str])
    """
    # 形式: startDate startTime endDate endTime minVer maxVer ... の想定
    try:
        start_date, start_time, end_date, end_time, min_ver, max_ver = row[:6]
    except ValueError:
        return ""

    def fmt_date(d, t):
        yyyy, mm, dd = d[:4], d[4:6], d[6:8]
        return f"{yyyy}/{mm}/{dd}({t})"

    start_fmt = fmt_date(start_date, start_time)
    end_fmt = fmt_date(end_date, end_time)
    version_str = f"v:{min_ver}-{max_ver}"

    # D列相当は、ここでは「row[6:] を空白区切りで連結」して返すイメージ
    d_col = " ".join(row[6:]).strip()
    return f"{start_fmt}〜{end_fmt}\n{version_str}\n{d_col}"

# ===== Discord Bot =====
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
        try:
            sale_id = int(sale_id)
        except ValueError:
            await message.channel.send("IDは数値で入力してください")
            return

        # TSV 読み込み
        sale_url = "https://shibanban2.github.io/bc-event/token/sale.tsv"
        rows = await fetch_tsv(sale_url)
        stage_map = await load_stage_map()

        found_rows = []
        for row in rows:
            ids = extract_ids(row)
            if sale_id in ids:
                # 名前付与
                names = [stage_map.get(eid, "") for eid in ids]
                id_with_name = ", ".join(
                    f"{eid} {names[i]}" if names[i] else str(eid)
                    for i, eid in enumerate(ids)
                )
                schedule_info = parse_schedule(row)
                found_rows.append(f"[{id_with_name}]\n{schedule_info}")

        if found_rows:
            reply = "\n\n".join(found_rows)
            await message.channel.send(f"```\n{reply}\n```")
        else:
            await message.channel.send(f"ID {sale_id} は見つかりませんでした")

# ===== 実行 =====
keep_alive()
TOKEN = os.getenv("DISCORD_TOKEN")
if TOKEN:
    client.run(TOKEN)
else:
    print("Tokenが見つかりませんでした")