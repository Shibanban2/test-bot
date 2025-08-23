import os
import discord
import aiohttp
from dotenv import load_dotenv
from keep_alive import keep_alive
from datetime import datetime

intents = discord.Intents.default()
intents.messages = True
intents.message_content = True
client = discord.Client(intents=intents)

load_dotenv(verbose=True)

PREFIX = "s."

# =========================
# 共通：数字フォーマット系
# =========================
def _fmt_time_str(t_str: str) -> str:
    try:
        n = int(t_str)
    except (ValueError, TypeError):
        n = 0
    s = str(n).zfill(4)
    return f"{s[:2]}:{s[2:]}"

def _fmt_date_str(d_str: str) -> str:
    s = str(d_str).zfill(8)
    return f"{s[:4]}/{s[4:6]}/{s[6:8]}"

def _fmt_date_range_line(row_tokens):
    if len(row_tokens) < 4:
        return "????/??/??(00:00)〜????/??/??(00:00)"
    sd, st, ed, et = row_tokens[0], row_tokens[1], row_tokens[2], row_tokens[3]
    return f"{_fmt_date_str(sd)}({_fmt_time_str(st)})〜{_fmt_date_str(ed)}({_fmt_time_str(et)})"

def _version_line(row_tokens):
    minv = row_tokens[4] if len(row_tokens) > 4 else ""
    maxv = row_tokens[5] if len(row_tokens) > 5 else ""
    return f"v:{minv}-{maxv}"

# GAS 準拠のフォーマット関数
def format_date(d):
    if str(d) == "20300101":
        return "#永続"
    return f"{str(d)[4:6]}/{str(d)[6:8]}"

def format_time(t):
    try:
        t = int(t)
        if t == 0 or t == 1100:
            return ""
        hour = str(t // 100).zfill(2)
        min = str(t % 100).zfill(2)
        return f"{hour}:{min}"
    except (ValueError, TypeError):
        return ""

def format_ver(num):
    try:
        num = int(num)
        major = num // 10000
        minor = (num % 10000) // 100
        patch = num % 100
        return f"{major}.{minor}.{patch}"
    except (ValueError, TypeError):
        return ""

def get_day_of_week(date_str):
    """YYYYMMDD 形式の日付から曜日（月～日）を返す"""
    try:
        date = datetime.strptime(str(date_str), "%Y%m%d")
        days = ["月", "火", "水", "木", "金", "土", "日"]
        return days[date.weekday()]
    except ValueError:
        return ""

# =================================
# TSV 読み込み
# =================================
async def fetch_tsv(url):
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                print(f"Fetching {url}: Status {resp.status}")
                if resp.status != 200:
                    print(f"Failed to fetch {url}: Status {resp.status}")
                    return []
                text = await resp.text()
                print(f"TSV content: {text[:100]}...")
                lines = text.splitlines()
                rows = []
                for line in lines:
                    row = line.split("\t")
                    if "".join(row).strip() == "":
                        continue
                    while len(row) > 0 and row[-1] == "":
                        row.pop()
                    if len(row) == 0 or (row[-1] not in ("0", "1")):
                        row = row + ["0"]
                    rows.append(row)
                print(f"Parsed {len(rows)} rows from {url}")
                return rows
    except Exception as e:
        print(f"Error fetching {url}: {e}")
        return []

# =========================
# stage.tsv を辞書化
# =========================
async def load_stage_map():
    url = "https://shibanban2.github.io/bc-event/token/stage.tsv"
    rows = await fetch_tsv(url)
    stage_map = {}
    for row in rows:
        if len(row) >= 2:
            try:
                sid = int(row[0])
                name = row[1]
                stage_map[sid] = name
            except ValueError:
                continue
    print(f"Loaded stage_map: {stage_map}")
    return stage_map

# =========================
# GAS準拠：ID逆走査抽出
# =========================
def extract_event_ids(row_tokens):
    nums = []
    for v in row_tokens:
        try:
            nums.append(int(v))
        except (ValueError, TypeError):
            continue
    ids = []
    for i in range(len(nums) - 2, -1, -1):
        val = nums[i]
        is_valid = (50 <= val <= 60) or (100 <= val <= 199) or (val >= 1000)
        if is_valid:
            ids.insert(0, val)
        else:
            break
    return ids

# =========================
# GAS準拠：D列（スケジュール）検出
# =========================
def _find_last_schedule_segment(nums):
    start = -1
    for i in range(len(nums) - 1):
        if nums[i] == 999999 and nums[i + 1] == 0:
            start = i
    if start == -1:
        return None
    return nums[start:]

def parse_schedule(segment_nums):
    if not segment_nums or len(segment_nums) < 3:
        return ""
    if segment_nums[0] != 999999 or segment_nums[1] != 0:
        return ""
    DAYS = [("日", 1), ("月", 2), ("火", 4), ("水", 8), ("木", 16), ("金", 32), ("土", 64)]
    def fmt_time(t):
        try:
            n = int(t)
        except (ValueError, TypeError):
            n = 0
        s = str(n).zfill(4)
        return f"{s[:2]}:{s[2:]}"
    def fmt_mmdd(d):
        s = str(int(d)).zfill(4)
        return f"{s[:2]}/{s[2:4]}"
    def decode_days(bit):
        try:
            b = int(bit)
        except (ValueError, TypeError):
            b = 0
        arr = []
        for name, val in DAYS:
            if (b & val) == val:
                arr.append(name)
        return "・".join(arr)
    row = segment_nums
    out_lines = []
    if len(row) >= 5 and row[2] == 1 and row[3] == 0 and row[4] > 0:
        n = row[4]
        days = row[5:5 + n]
        if len(days) == n:
            out_lines.append(f"{','.join(str(d) for d in days)}日")
        return "\n".join(out_lines)
    if len(row) >= 7 and row[2] == 1 and row[3] == 0 and row[4] == 0 and row[5] == 0 and row[6] >= 1:
        n = row[6]
        times = []
        for i in range(n):
            s = row[7 + i * 2]
            e = row[8 + i * 2]
            times.append(f"{fmt_time(s)}～{fmt_time(e)}")
        if times:
            out_lines.append(" ".join([" & ".join(times)]))
        return "\n".join(out_lines)
    if len(row) >= 4 and row[2] >= 1 and row[3] == 1:
        period_count = row[2]
        p = 4
        for _ in range(period_count):
            if p < len(row) and row[p] == 1:
                p += 1
            if p + 3 >= len(row):
                break
            sDate, sTime = row[p], row[p + 1]
            eDate, eTime = row[p + 2], row[p + 3]
            p += 4
            if p + 2 < len(row) and row[p] == 0 and row[p + 1] == 0 and (row[p + 2] in (0, 3)):
                time_count = row[p + 2]
                p += 3
                times = []
                for _i in range(time_count):
                    if p + 1 >= len(row):
                        break
                    s, e = row[p], row[p + 1]
                    p += 2
                    times.append(f"{fmt_time(s)}～{fmt_time(e)}")
                period_str = f"{fmt_mmdd(sDate)}({fmt_time(sTime)})～{fmt_mmdd(eDate)}({fmt_time(eTime)})"
                if times:
                    out_lines.append(f"{period_str} { ' & '.join(times) }")
                else:
                    out_lines.append(period_str)
            else:
                while p < len(row) and row[p] != 999999:
                    p += 1
        return "\n".join(out_lines)
    if len(row) >= 5 and row[2] >= 1 and row[3] == 0 and row[4] == 0:
        block_count = row[2]
        p = 5
        for _ in range(block_count):
            if p >= len(row):
                break
            day_id = row[p]; p += 1
            if p >= len(row):
                break
            time_count = row[p]; p += 1
            times = []
            for _j in range(time_count):
                if p + 1 >= len(row):
                    break
                s, e = row[p], row[p + 1]
                p += 2
                times.append(f"{fmt_time(s)}～{fmt_time(e)}")
            if p + 1 < len(row) and row[p] == 0 and row[p + 1] == 0:
                p += 2
            label = decode_days(day_id)
            label_out = f"{label}曜日" if "・" not in label else label
            if time_count > 0:
                out_lines.append(f"{label_out} {' & '.join(times)}")
            else:
                out_lines.append(f"毎週{label_out}")
        return "\n".join(out_lines)
    if len(row) >= 5 and row[2] >= 1 and row[3] == 0 and row[4] > 0:
        block_count = row[2]
        p = 4
        for _ in range(block_count):
            if p >= len(row):
                break
            date_count = row[p]; p += 1
            dates = row[p:p + date_count]; p += date_count
            if p < len(row) and row[p] == 0:
                p += 1
            if p >= len(row):
                break
            time_block_count = row[p]; p += 1
            times = []
            for _t in range(time_block_count):
                if p + 1 >= len(row):
                    break
                s, e = row[p], row[p + 1]
                p += 2
                times.append(f"{fmt_time(s)}～{fmt_time(e)}")
            if p < len(row) and row[p] == 0:
                p += 1
            out_lines.append(f"{','.join(str(d) for d in dates)}日 {' & '.join(times)}")
        return "\n".join(out_lines)
    return ""

def build_monthly_note(row_tokens):
    nums = []
    for v in row_tokens:
        try:
            nums.append(int(v))
        except (ValueError, TypeError):
            continue
    seg = _find_last_schedule_segment(nums)
    if not seg:
        return ""
    return parse_schedule(seg)

# =========================
# ガチャデータ処理
# =========================
async def load_gatya_maps():
    try:
        gatya_url = "https://shibanban2.github.io/bc-event/token/gatya.tsv"
        gatya_rows = await fetch_tsv(gatya_url)
        name_url = "https://shibanban2.github.io/bc-event/token/gatyaName.tsv"
        name_rows = await fetch_tsv(name_url)
        name_map = {int(r[0]): r[1] for r in name_rows if r and r[0].isdigit()}
        item_url = "https://shibanban2.github.io/bc-event/token/gatyaitem.tsv"
        item_rows = await fetch_tsv(item_url)
        item_map = {int(r[2]): r[3] for r in item_rows if r and len(r) > 3 and r[2].isdigit()}
        print(f"Loaded gatya_rows: {len(gatya_rows)}, name_map: {len(name_map)}, item_map: {len(item_map)}")
        return gatya_rows, name_map, item_map
    except Exception as e:
        print(f"Error in load_gatya_maps: {e}")
        raise

def parse_gatya_row(row, name_map, item_map, today_str="20250823"):
    output_lines = []
    try:
        start_date = str(row[0])
        start_time = row[1]
        end_date = str(row[2])
        end_time = row[3]
        min_ver = row[4] if len(row) > 4 else 0
        max_ver = row[5] if len(row) > 5 else 999999
        type_code = int(row[8]) if len(row) > 8 and row[8].isdigit() else 0
        j = int(row[9]) if len(row) > 9 and row[9].isdigit() else 0
        print(f"Processing row: {row[:10]}")
    except (IndexError, ValueError, TypeError) as e:
        print(f"Invalid row format: {row}, error: {e}")
        return output_lines

    # 今日以降のスケジュールのみ
    if start_date < today_str:
        return output_lines

    base_cols = {
        1: {"id": 10, "extra": 13, "normal": 14, "rare": 16, "super": 18, "ultra": 20, "confirm": 21, "legend": 22, "title": 24},
        2: {"id": 25, "extra": 28, "normal": 29, "rare": 31, "super": 33, "ultra": 35, "confirm": 36, "legend": 37, "title": 39},
        3: {"id": 40, "extra": 43, "normal": 44, "rare": 46, "super": 48, "ultra": 50, "confirm": 51, "legend": 52, "title": 54},
        4: {"id": 55, "extra": 58, "normal": 59, "rare": 61, "super": 63, "ultra": 65, "confirm": 66, "legend": 67, "title": 69},
        5: {"id": 70, "extra": 73, "normal": 74, "rare": 76, "super": 78, "ultra": 80, "confirm": 81, "legend": 82, "title": 84},
        6: {"id": 85, "extra": 88, "normal": 89, "rare": 91, "super": 93, "ultra": 95, "confirm": 96, "legend": 97, "title": 99},
        7: {"id": 100, "extra": 103, "normal": 104, "rare": 106, "super": 108, "ultra": 110, "confirm": 111, "legend": 112, "title": 114},
    }

    # 特例: typeCode=4 かつ j=2
    if type_code == 4 and j == 2:
        try:
            id = int(row[27]) if len(row) > 27 and row[27].isdigit() else -1
            extra = lookup_extra(row[28], item_map) if len(row) > 28 else ""
            title = "".join([row[i] for i in range(40, 43) if len(row) > i and row[i]]) if len(row) > 42 else ""
        except (IndexError, ValueError, TypeError) as e:
            print(f"Error in special case (type=4, j=2): {e}")
            return output_lines
        if id <= 0:
            return output_lines
        gname = name_map.get(id, f"error[{id}]")
        ver_text = ""
        if min_ver and min_ver != 0:
            ver_text += f"[要Ver.{format_ver(min_ver)}]"
        if max_ver and max_ver != 999999:
            ver_text += f"[Ver.{format_ver(max_ver)}まで]"
        date_range = f"{format_date(start_date)}({get_day_of_week(start_date)}){format_time(start_time)}〜{format_date(end_date)}({get_day_of_week(end_date)}){format_time(end_time)}"
        col_k = f"{date_range} {id} {gname}{ver_text}"
        if extra:
            col_k += f" {extra}"
        output_lines.append(col_k)
        return output_lines

    # 通常処理
    col = base_cols.get(j)
    if not col:
        print(f"Invalid j value: {j}")
        return output_lines

    try:
        id = int(row[col["id"]]) if len(row) > col["id"] and row[col["id"]].isdigit() else -1
        extra = lookup_extra(row[col["extra"]], item_map) if len(row) > col["extra"] else ""
        confirm = "【確定】" if len(row) > col["confirm"] and row[col["confirm"]] == "1" and type_code != 4 else ""
        title = row[col["title"]] if len(row) > col["title"] and row[col["title"]] else ""
    except (IndexError, ValueError, TypeError) as e:
        print(f"Error processing row at col {col}: {e}")
        return output_lines

    if id <= 0:
        return output_lines

    gname = name_map.get(id, f"error[{id}]")
    ver_text = ""
    if min_ver and min_ver != 0:
        ver_text += f"[要Ver.{format_ver(min_ver)}]"
    if max_ver and max_ver != 999999:
        ver_text += f"[Ver.{format_ver(max_ver)}まで]"
    date_range = f"{format_date(start_date)}({get_day_of_week(start_date)}){format_time(start_time)}〜{format_date(end_date)}({get_day_of_week(end_date)}){format_time(end_time)}"
    col_k = f"{date_range} {id} {gname}{confirm}{ver_text}"
    if extra:
        col_k += f" {extra}"
    output_lines.append(col_k)
    return output_lines

def lookup_extra(code, item_map):
    try:
        return item_map.get(int(code), "")
    except (ValueError, TypeError):
        return ""

# =========================
# Discord Bot
# =========================
@client.event
async def on_ready():
    print(f"ログインしました: {client.user.name}")

@client.event
async def on_message(message):
    if message.author == client.user:
        return
    if message.content.lower() == "ping.":
        await message.channel.send("Pong.")
    if message.content.lower().startswith(f"{PREFIX}sale "):
        try:
            query = message.content.split(" ", 1)[1].strip()
            sale_id = None
            sale_name = None
            try:
                sale_id = int(query)
            except ValueError:
                sale_name = query
            sale_url = "https://shibanban2.github.io/bc-event/token/sale.tsv"
            rows = await fetch_tsv(sale_url)
            stage_map = await load_stage_map()
            outputs = []
            found_ids = set()
            header = None
            if sale_id is not None:
                stage_name = stage_map.get(sale_id,"")
                header = f"[{sale_id} {stage_name}]"
            elif sale_name is not None:
                header = f"[??? {sale_name}]"
            for row in rows:
                ids = extract_event_ids(row)
                for eid in ids:
                    name = stage_map.get(eid, "")
                    if sale_id is not None and eid != sale_id:
                        continue
                    if sale_name is not None and sale_name not in name:
                        continue
                    header = f"[{eid} {name}]" if name else f"[{eid}]"
                    if eid not in found_ids:
                        outputs.append(header)
                        found_ids.add(eid)
                    note = build_monthly_note(row)
                    period_line = _fmt_date_range_line(row)
                    ver_line = _version_line(row)
                    if note:
                        outputs.append(f"{period_line}\n{ver_line}\n```{note}```")
                    else:
                        outputs.append(f"{period_line}\n{ver_line}")
            if outputs:
                await message.channel.send("\n".join(outputs))
            else:
                if header is None:
                    header = "[]"
                await message.channel.send(f"{header}\nスケジュールが見つかりませんでした")
        except Exception as e:
            print(f"Error in {PREFIX}sale command: {e}")
            await message.channel.send("エラーが発生しました。")
    if message.content.lower().startswith(f"{PREFIX}gt"):
        try:
            gatya_rows, name_map, item_map = await load_gatya_maps()
            outputs = []
            today_str = datetime.now().strftime("%Y%m%d")  # 今日の日付（例：20250823）
            for row in gatya_rows[1:]:  # ヘッダー行をスキップ
                lines = parse_gatya_row(row, name_map, item_map, today_str)
                outputs.extend(lines)
            if outputs:
                await message.channel.send("\n".join(outputs))
            else:
                await message.channel.send("今日以降のガチャ情報は見つかりませんでした")
        except Exception as e:
            print(f"Error in {PREFIX}gt command: {e}")
            await message.channel.send("エラーが発生しました。")

# 実行
keep_alive()
TOKEN = os.getenv("DISCORD_TOKEN")
if TOKEN:
    client.run(TOKEN)
else:
    print("Tokenが見つかりませんでした")
