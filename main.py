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
                stage_name = row[1]  # 2列目そのまま
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

# ===== parseSchedule (Python移植版) =====
def parse_schedule(row):
    try:
        start_date, start_time, end_date, end_time, min_ver, max_ver = row[:6]
    except ValueError:
        return ""

    def fmt_date(d, t):
        yyyy, mm, dd = d[:4], d[4:6], d[6:8]
        hh = str(int(t) // 100).zfill(2)
        mi = str(int(t) % 100).zfill(2)
        return f"{yyyy}/{mm}/{dd}({hh}:{mi})"

    start_fmt = fmt_date(start_date, start_time)
    end_fmt = fmt_date(end_date, end_time)
    version_str = f"v:{min_ver}-{max_ver}"

    # GASと同じく、999999 以降を渡して解析
    nums = []
    for v in row[6:]:
        try:
            nums.append(int(v))
        except ValueError:
            continue

    sched_text = parse_schedule_core(nums) if nums else ""
    return f"{start_fmt}〜{end_fmt}\n{version_str}\n{sched_text}"

# ===== parseSchedule の本体 (GAS移植) =====
def parse_schedule_core(row):
    if len(row) < 2 or row[0] != 999999 or row[1] != 0:
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
        arr = [name for name, val in DAYS if (b & val) == val]
        return "・".join(arr)

    out = []

    # 例: 曜日指定 (毎週月曜など)
    if row[2] >= 1 and row[3] == 0 and row[4] == 0:
        block_count = row[2]
        p = 5
        for _ in range(block_count):
            day_id = row[p]; p += 1
            time_count = row[p]; p += 1
            times = []
            for _ in range(time_count):
                s, e = row[p], row[p+1]; p += 2
                times.append(f"{fmt_time(s)}～{fmt_time(e)}")
            if row[p] == 0 and row[p+1] == 0:
                p += 2
            label = decode_days(day_id)
            label_out = f"{label}曜日" if "・" not in label else label
            out.append(f"毎週{label_out}" if not times else f"{label_out} {' & '.join(times)}")
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
            ids = extract_ids(row)
            if sale_id in ids:
                schedule_info = parse_schedule(row)
                # ここで IDs を分解して1つずつ出力
                for eid in ids:
                    name = stage_map.get(eid, "")
                    id_with_name = f"{eid}　{name}" if name else str(eid)
                    found_rows.append(f"[{id_with_name}]\n{schedule_info}")

        if found_rows:
            reply = "\n\n".join(found_rows)
            await message.channel.send(reply)
        else:
            await message.channel.send(f"ID {sale_id} は見つかりませんでした")

# ===== 実行 =====
keep_alive()
TOKEN = os.getenv("DISCORD_TOKEN")
if TOKEN:
    client.run(TOKEN)
else:
    print("Tokenが見つかりませんでした")