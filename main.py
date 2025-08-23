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
            return [row for row in rows if "".join(row).strip() != ""]

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

# ===== GAS仕様 extractEventIds (Python版) =====
def extract_event_ids(row):
    try:
        nums = [int(v) for v in row if v.strip() != ""]
    except ValueError:
        nums = []

    # D列に出す注記
    start = -1
    for i in range(len(nums) - 1):
        if nums[i] == 999999 and nums[i + 1] == 0:
            start = i

    monthly_note = ""
    if start != -1:
        segment = nums[start:]
        monthly_note = parse_schedule(segment)

    # 末尾から逆走査
    ids = []
    for i in range(len(nums) - 2, -1, -1):
        val = nums[i]
        is_valid = (50 <= val <= 60) or (100 <= val <= 199) or (val >= 1000)
        if is_valid:
            ids.insert(0, val)
        else:
            break

    return {"ids": ids, "monthlyNote": monthly_note}

# ===== GAS仕様 parseSchedule (Python版) =====
def parse_schedule(row):
    if len(row) < 3 or row[0] != 999999 or row[1] != 0:
        return ""

    DAYS = [("日", 1), ("月", 2), ("火", 4), ("水", 8),
            ("木", 16), ("金", 32), ("土", 64)]

    def fmt_time(t):
        n = int(t)
        return f"{n//100:02d}:{n%100:02d}"

    def fmt_mmdd(d):
        s = str(d).zfill(4)
        return f"{s[:2]}/{s[2:]}"

    def decode_days(bit):
        b = int(bit)
        return "・".join(name for name, val in DAYS if (b & val) == val)

    out = []

    # --- 1) 毎月○日 ---
    if row[2] == 1 and row[3] == 0 and row[4] > 0:
        n = row[4]
        days = row[5:5+n]
        if len(days) == n:
            out.append(f"{','.join(map(str, days))}日")
        return "\n".join(out)

    # --- 2) 時間のみ ---
    if row[2] == 1 and row[3] == 0 and row[4] == 0 and row[5] == 0 and row[6] >= 1:
        n = row[6]
        times = [f"{fmt_time(row[7+i*2])}～{fmt_time(row[8+i*2])}" for i in range(n)]
        if times:
            out.append(" & ".join(times))
        return "\n".join(out)

    # --- 3) 複数日付範囲 ---
    if row[2] >= 1 and row[3] == 1:
        period_count = row[2]
        p = 4
        for _ in range(period_count):
            if row[p] == 1:
                p += 1
            s_date, s_time, e_date, e_time = row[p:p+4]
            p += 4
            if row[p] == 0 and row[p+1] == 0 and (row[p+2] == 0 or row[p+2] == 3):
                time_count = row[p+2]
                p += 3
                times = [f"{fmt_time(row[p+i*2])}～{fmt_time(row[p+i*2+1])}" for i in range(time_count)]
                p += time_count * 2
                period_str = f"{fmt_mmdd(s_date)}({fmt_time(s_time)})～{fmt_mmdd(e_date)}({fmt_time(e_time)})"
                out.append(f"{period_str} {' & '.join(times)}" if times else period_str)
            else:
                while p < len(row) and row[p] != 999999:
                    p += 1
        return "\n".join(out)

    # --- 4) 曜日指定 ---
    if row[2] >= 1 and row[3] == 0 and row[4] == 0:
        block_count = row[2]
        p = 5
        for _ in range(block_count):
            day_id = row[p]; p += 1
            time_count = row[p]; p += 1
            times = [f"{fmt_time(row[p+i*2])}～{fmt_time(row[p+i*2+1])}" for i in range(time_count)]
            p += time_count * 2
            if row[p] == 0 and row[p+1] == 0:
                p += 2
            label = decode_days(day_id)
            label_out = f"{label}曜日" if "・" not in label else label
            if time_count > 0:
                out.append(f"{label_out} {' & '.join(times)}")
            else:
                out.append(f"毎週{label_out}")
        return "\n".join(out)

    # --- 5) 日付時間指定型 ---
    if row[2] >= 1 and row[3] == 0 and row[4] > 0:
        block_count = row[2]
        p = 4
        for _ in range(block_count):
            date_count = row[p]; p += 1
            dates = row[p:p+date_count]; p += date_count
            if row[p] == 0:
                p += 1
            time_block_count = row[p]; p += 1
            times = [f"{fmt_time(row[p+i*2])}～{fmt_time(row[p+i*2+1])}" for i in range(time_block_count)]
            p += time_block_count * 2
            if row[p] == 0:
                p += 1
            out.append(f"{','.join(map(str, dates))}日 {' & '.join(times)}")
        return "\n".join(out)

    return ""

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

        sale_url = "https://shibanban2.github.io/bc-event/token/sale.tsv"
        rows = await fetch_tsv(sale_url)
        stage_map = await load_stage_map()

        found_rows = []
        for row in rows:
            ev = extract_event_ids(row)
            if sale_id in ev["ids"]:
                name = stage_map.get(sale_id, "")
                id_with_name = f"{sale_id}　{name}" if name else str(sale_id)
                # GAS同様、monthlyNote 付き
                found_rows.append(f"[{id_with_name}]\n{ev['monthlyNote']}")

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