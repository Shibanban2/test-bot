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

# =========================
# 共通：数字フォーマット系
# =========================
def _fmt_time_str(t_str: str) -> str:
    """ '0' -> '00:00', '800' -> '08:00', '1100' -> '11:00' """
    try:
        n = int(t_str)
    except (ValueError, TypeError):
        n = 0
    s = str(n).zfill(4)
    return f"{s[:2]}:{s[2:]}"

def _fmt_date_str(d_str: str) -> str:
    """ '20160101' -> '2016/01/01'（桁不足でもゼロ詰めで対処）"""
    s = str(d_str).zfill(8)
    return f"{s[:4]}/{s[4:6]}/{s[6:8]}"

def _fmt_date_range_line(row_tokens):
    """ sale.tsv 1行の [0..3] を使って 'YYYY/MM/DD(HH:MM)〜YYYY/MM/DD(HH:MM)' を作る """
    if len(row_tokens) < 4:
        return "????/??/??(00:00)〜????/??/??(00:00)"
    sd, st, ed, et = row_tokens[0], row_tokens[1], row_tokens[2], row_tokens[3]
    return f"{_fmt_date_str(sd)}({_fmt_time_str(st)})〜{_fmt_date_str(ed)}({_fmt_time_str(et)})"

def _version_line(row_tokens):
    """ sale.tsv 1行の [4..5] を使って 'v:min-max' を返す（常に表示）"""
    minv = row_tokens[4] if len(row_tokens) > 4 else ""
    maxv = row_tokens[5] if len(row_tokens) > 5 else ""
    return f"v:{minv}-{maxv}"

# =================================
# TSV 読み込み：末尾に必要なら 0 を付ける
# =================================
async def fetch_tsv(url):
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            text = await resp.text()
            lines = text.splitlines()
            rows = []
            for line in lines:
                # タブ分割
                row = line.split("\t")
                # 全部空欄の行はスキップ
                if "".join(row).strip() == "":
                    continue
                # 右側の空欄セルを削除（GAS での見え方に合わせる）
                while len(row) > 0 and row[-1] == "":
                    row.pop()
                # 末尾が "0" または "1" でなければ "0" を付与（GAS のイベント終端マーカー相当）
                if len(row) == 0 or (row[-1] not in ("0", "1")):
                    row = row + ["0"]
                rows.append(row)
            return rows

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
    return stage_map

# =========================
# GAS準拠：ID逆走査抽出
# =========================
def extract_event_ids(row_tokens):
    """
    GAS の extractEventIds と同様の ID 抽出（末尾から2番目から逆走査、非IDに当たったら break）
    有効ID: 50~60, 100~199, 1000以上
    """
    nums = []
    for v in row_tokens:
        try:
            nums.append(int(v))
        except (ValueError, TypeError):
            continue

    ids = []
    # 末尾は終端 0（or 1）なので、その1つ手前から逆順で見る
    for i in range(len(nums) - 2, -1, -1):
        val = nums[i]
        is_valid = (50 <= val <= 60) or (100 <= val <= 199) or (val >= 1000)
        if is_valid:
            ids.insert(0, val)  # unshift
        else:
            break
    return ids

# =========================
# GAS準拠：D列（スケジュール）検出
# =========================
def _find_last_schedule_segment(nums):
    """
    行全体（数値配列）から、最後に出現する (999999, 0) の位置を探し、
    そこから右端までの数値配列を返す。無ければ None を返す。
    """
    start = -1
    for i in range(len(nums) - 1):
        if nums[i] == 999999 and nums[i + 1] == 0:
            start = i
    if start == -1:
        return None
    return nums[start:]

def parse_schedule(segment_nums):
    """
    GAS の parseSchedule を ほぼそのまま Python に移植。
    segment_nums: 999999,0 から始まる数値配列
    返り値: D列に出す文面（複数行可）
    """
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

    # --- 1) 毎月○日 ---
    if len(row) >= 5 and row[2] == 1 and row[3] == 0 and row[4] > 0:
        n = row[4]
        days = row[5:5 + n]
        if len(days) == n:
            out_lines.append(f"{','.join(str(d) for d in days)}日")
        return "\n".join(out_lines)

    # --- 2) 時間のみ ---
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

    # --- 3) 複数日付範囲 ---
    if len(row) >= 4 and row[2] >= 1 and row[3] == 1:
        period_count = row[2]
        p = 4
        for _ in range(period_count):
            if p < len(row) and row[p] == 1:
                p += 1  # 先頭1を許容

            if p + 3 >= len(row):
                break
            sDate, sTime = row[p], row[p + 1]
            eDate, eTime = row[p + 2], row[p + 3]
            p += 4

            # 区切り: 0,0,0 or 0,0,3
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
                # 不正ブロックは 999999 までスキップ
                while p < len(row) and row[p] != 999999:
                    p += 1
        return "\n".join(out_lines)

    # --- 4) 曜日指定 ---
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

            # 区切り 0,0 を許容
            if p + 1 < len(row) and row[p] == 0 and row[p + 1] == 0:
                p += 2

            label = decode_days(day_id)
            label_out = f"{label}曜日" if "・" not in label else label

            if time_count > 0:
                out_lines.append(f"{label_out} {' & '.join(times)}")
            else:
                out_lines.append(f"毎週{label_out}")
        return "\n".join(out_lines)

    # --- 5) 日付時間指定型 ---
    if len(row) >= 5 and row[2] >= 1 and row[3] == 0 and row[4] > 0:
        block_count = row[2]
        p = 4
        for _ in range(block_count):
            if p >= len(row):
                break
            date_count = row[p]; p += 1
            dates = row[p:p + date_count]; p += date_count
            if p < len(row) and row[p] == 0:
                p += 1  # 区切り

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
                p += 1  # 区切り

            out_lines.append(f"{','.join(str(d) for d in dates)}日 {' & '.join(times)}")
        return "\n".join(out_lines)

    return ""

def build_monthly_note(row_tokens):
    """ 行トークンから数値配列を作り、最後の 999999,0 セグメントを parse_schedule に渡して D列相当を返す """
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
# Discord Bot
# =========================
@client.event
async def on_ready():
    print("ログインしました")

# ... 省略（fetch_tsv, load_stage_map, extract_event_ids, parse_schedule, _fmt_time_str, _fmt_date_str などはそのまま）

# -----------------------------
# gt コマンド追加
# -----------------------------
async def load_gatya_maps():
    # gatya.tsv
    gatya_url = "https://shibanban2.github.io/bc-event/token/gatya.tsv"
    gatya_rows = await fetch_tsv(gatya_url)

    # gatyaName.tsv
    name_url = "https://shibanban2.github.io/bc-event/token/gatyaName.tsv"
    name_rows = await fetch_tsv(name_url)
    name_map = {int(r[0]): r[1] for r in name_rows if r and r[0].isdigit()}

    # gatyaitem.tsv
    item_url = "https://shibanban2.github.io/bc-event/token/gatyaitem.tsv"
    item_rows = await fetch_tsv(item_url)
    item_map = {int(r[2]): r[3] for r in item_rows if r and r[2].isdigit()}

    return gatya_rows, name_map, item_map

def format_gatya_time(sd, st, ed, et):
    return f"{_fmt_date_str(sd)}({_fmt_time_str(st)})〜{_fmt_date_str(ed)}({_fmt_time_str(et)})"

def parse_gatya_row(row, name_map, item_map):
    """1行のgatyaデータを複数j列対応で出力文字列リストに変換"""
    output_lines = []
    try:
        start_date, start_time = row[0], row[1]
        end_date, end_time = row[2], row[3]
    except IndexError:
        return output_lines

    date_range = format_gatya_time(start_date, start_time, end_date, end_time)

    # j列は1〜7（例：10列ずつ分かれている場合はGAS baseColsに合わせる）
    base_cols = [10, 25, 40, 55, 70, 85, 100]  # j=1..7のID列
    for col_id in base_cols:
        if col_id >= len(row):
            continue
        try:
            gid = int(row[col_id])
        except (ValueError, TypeError):
            continue
        if gid <= 0:
            continue
        gname = name_map.get(gid, f"error[{gid}]")
        extra = item_map.get(gid, "")
        line = f"{date_range}\n {gid} {gname}{(' '+extra) if extra else ''}"
        output_lines.append(line)
    return output_lines
    
@client.event
async def on_message(message):
    if message.author == client.user:
        return

    if message.content.lower() == "ping.":
        await message.channel.send("Pong.")

    PREFIX = "s."  # PREFIX はここで定義（関数内で毎回定義するのは非効率ですが、元のコードを尊重）
    
    # !sale コマンド
    if message.content.startswith(f"{PREFIX}sale "):
        query = message.content.split(" ", 1)[1].strip()

        # IDかステージ名かを判定
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

        for row in rows:
            ids = extract_event_ids(row)

            for eid in ids:
                name = stage_map.get(eid, "")

                # --- ID指定のとき ---
                if sale_id is not None and eid != sale_id:
                    continue

                # --- 名前指定のとき（部分一致） ---
                if sale_name is not None and sale_name not in name:
                    continue

                # タイトルは必ず出す
                header = f"[{eid} {name}]" if name else f"[{eid}]"
                if eid not in found_ids:
                    outputs.append(header)
                    found_ids.add(eid)
                
                note = build_monthly_note(row)
                period_line = _fmt_date_range_line(row)
                ver_line = _version_line(row)
                # その後、note があれば追加
                if note:
                    outputs.append(f"{period_line}\n{ver_line}\n```{note}```")
                else:
        if outputs:
            await message.channel.send("\n".join(outputs))
        else:
            if sale_id is not None:
                header = f"[{sale_id} ]"
            elif sale_name is not None:
                header = f"[??? {sale_name}]"
            else:
                header = "[不明]"
            await message.channel.send(header + "\n該当するスケジュールは見つかりませんでした")


    # !gt コマンド
    if message.content.startswith(f"{PREFIX}gt"):
        gatya_rows, name_map, item_map = await load_gatya_maps()
        outputs = []
        for row in gatya_rows[1:]:
            lines = parse_gatya_row(row, name_map, item_map)
            outputs.extend(lines)
        
        if outputs:
            await message.channel.send("\n".join(outputs))
        else:
            await message.channel.send("ガチャ情報は見つかりませんでした")

# 実行
keep_alive()
TOKEN = os.getenv("DISCORD_TOKEN")
if TOKEN:
    client.run(TOKEN)
else:
    print("Tokenが見つかりませんでした")
