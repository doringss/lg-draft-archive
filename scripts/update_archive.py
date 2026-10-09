import copy
import json
import os
import re
import subprocess
import time
from datetime import datetime
from fractions import Fraction
from pathlib import Path
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup

NOW = datetime.now(ZoneInfo("Asia/Seoul"))
STAMP = NOW.strftime("%Y-%m-%d %H:%M KST")
ROOT = Path("data")
FIELDS = ("stats", "advanced", "noStatsReason", "statsDateNote")


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


groups = {
    int(path.stem): read(path)
    for path in sorted((ROOT / "entries").glob("*.json"))
}
records = read(ROOT / "stats.json")
meta = read(ROOT / "meta.json")

# 한 번만 적용하는 명단 복원 및 화면 변경.
if not meta.get("archiveUpgradeV2"):
    if not any(
        p["name"] == "전경원"
        for players in groups.values()
        for p in players
    ):
        old_html = subprocess.check_output(
            [
                "git", "show",
                "e5fd50fb7995f95f5595f3b51b3ab4da7f61c9d1:index.html",
            ]
        ).decode("utf-8")
        match = re.search(r"\bconst\s+DATA\s*=\s*", old_html)
        if not match:
            raise ValueError("전경원 복원용 데이터가 없습니다.")
        old_data, _ = json.JSONDecoder().raw_decode(old_html[match.end():])
        player = copy.deepcopy(
            next(p for p in old_data["players"] if p["name"] == "전경원")
        )
        records[player["id"]] = {
            key: player.pop(key) for key in FIELDS if key in player
        }
        player["sourceNote"] = (
            "2025 LG 육성 입단. 타 구단 경력이 있으나 "
            "자료 관리자의 요청으로 포함한 예외입니다."
        )
        groups.setdefault(2025, []).append(player)

    source = (
        "https://www.kyungmin.ac.kr/homepage/page.do"
        "?m=V&menu=137&no=2026-01797&page=1"
    )
    for name, school in (
        ("황윤재", "경민대"),
        ("임영기", "한양대"),
        ("박정훈", "인하대"),
    ):
        if any(p["name"] == name for p in groups.setdefault(2027, [])):
            continue
        groups[2027].append({
            "id": f"2027-dev-{name}",
            "name": name,
            "year": 2027,
            "development": True,
            "roundNum": 12,
            "roundLabel": "신고·육성",
            "school": school,
            "cellLabel": school,
            "currentLG": True,
            "teamLabel": "LG 트윈스",
            "lgFirst": False,
            "firstVerified": False,
            "serving": False,
            "photo": None,
            "position": "",
            "birthday": "",
            "hand": "",
            "body": "",
            "military": "",
            "draft": "2027년 LG 육성선수 입단",
            "entryNote": "2027년 육성 입단 명단",
            "rookieNote": (
                "2026년 9월 28일 육성선수 계약. "
                "이 자료에서는 2027년 입단 명단으로 분류합니다."
            ),
            "career": "LG 트윈스 육성선수 계약",
            "draftSource": source,
            "sourceNote": (
                "계약 및 출신 대학: 경민대 2026.09.29 발표. "
                "추가 프로필과 KBO 선수 ID는 확인 후 보완합니다."
            ),
            "events": [{
                "date": "2026.09.28",
                "text": "LG 트윈스 육성선수 계약.",
                "url": source,
            }],
        })

    pending = next(
        p for p in groups[2027]
        if p["name"] == "김서준" and "상동고" in p.get("school", "")
    )
    pending.update({
        "entryPending": True,
        "currentLG": False,
        "cellLabel": "상동고 · 입단 보류",
        "teamLabel": "LG 지명 · 입단 보류",
        "rookieNote": "현재 입단 보류 상태입니다.",
        "sourceNote": (
            "입단 보류: 자료 관리자 제공 정보. "
            "공개 발표 원문은 추가 확인이 필요합니다."
        ),
    })

    template_path = Path("source/template.html")
    html = template_path.read_text(encoding="utf-8")
    html = re.sub(
        r'<details class="footnotes">[\s\S]*?</details>', "", html
    )
    html = re.sub(
        r"\$\{p\.wikiMirror\?`<a[\s\S]*?확인한 미러 ↗</a>`:''\}",
        "",
        html,
    )
    html = html.replace(
        "class=\"player ${p.currentLG",
        "class=\"player ${p.entryPending?'pending':''} ${p.currentLG",
    )
    html = html.replace(
        "${p.year===2027?'<span class=\"tag\">"
        "지명 완료 · 프로 성적 없음</span>':''}",
        "${p.entryPending?'<span class=\"tag\">입단 보류</span>':"
        "p.year===2027?'<span class=\"tag\">"
        "신인 · 프로 성적 없음</span>':''}",
    )
    html = html.replace(
        "2026.09.24–25 조회. OPS",
        "${esc(p.statsDateNote||"
        "'2026.09.24–25 조회 · 이후 갱신 미확인')}. OPS",
    )
    html = html.replace(
        "${p.advanced?",
        "${!Object.keys(p.stats||{}).length&&p.statsDateNote?"
        "`<p class=\"source\">${esc(p.statsDateNote)}</p>`:''}"
        "${p.advanced?",
        1,
    )
    html = html.replace(
        "const years=Array.from({length:17},(_,i)=>2011+i);",
        "const years=[...new Set(DATA.players.map(p=>p.year))]"
        ".sort((a,b)=>a-b);",
    )
    html = html.replace("`17개년 · 지명 ", "`${years.length}개년 · 지명 ")
    html = html.replace(
        "</style>",
        "tr[hidden]{display:none!important}"
        ".player.pending{background:#fff4d5;border:1px solid #d6a52c}"
        "</style>",
        1,
    )
    enhancement = """
// ARCHIVE_UI_V2
const devRow=document.querySelector('tr.development');
if(devRow){
  devRow.id='developmentPlayers';
  devRow.hidden=true;
  const toggleRow=document.createElement('tr');
  toggleRow.innerHTML=`<td colspan="${years.length+1}"
    style="padding:0;height:auto"><button id="developmentToggle"
    type="button" aria-expanded="false"
    aria-controls="developmentPlayers developmentWarning"
    style="width:100%;padding:14px;text-align:left;border:0;
    background:#eeeaf0;font-weight:700">
    신고·육성 입단 · 펼치기 ▾</button></td>`;
  const note=document.createElement('tr');
  note.id='developmentWarning';
  note.hidden=true;
  note.innerHTML=`<td colspan="${years.length+1}"
    style="height:auto;font-size:13px">
    신고·육성 자료에는 누락이나 부정확한 정보가 있을 수 있습니다.
    미확인 사항은 선수 프로필에 표시합니다.</td>`;
  devRow.before(toggleRow,note);
  const button=toggleRow.querySelector('button');
  button.onclick=()=>{
    const open=button.getAttribute('aria-expanded')!=='true';
    button.setAttribute('aria-expanded',String(open));
    devRow.hidden=!open;
    note.hidden=!open;
    button.textContent='신고·육성 입단 · '+(open?'접기 ▴':'펼치기 ▾');
  };
}
const edition=document.querySelector('.edition');
if(edition){
  edition.textContent='명단 수정 '+(DATA.rosterUpdated||'미확인')
    +' · 기록 조회일은 선수별 표시';
}
"""
    html = html.replace("</script>", enhancement + "\n</script>", 1)
    template_path.write_text(html, encoding="utf-8")
    meta["archiveUpgradeV2"] = True
    meta["rosterUpdated"] = NOW.strftime("%Y-%m-%d")

players = [p for group in groups.values() for p in group]
ids = [p["id"] for p in players]
if len(ids) != len(set(ids)):
    raise ValueError("선수 ID가 중복되었습니다.")

# 현재 저장된 소속을 기준으로 하며, 명시적 설정이 있으면 우선합니다.
clubs = (
    "LG", "삼성", "롯데", "KIA", "두산", "키움", "한화",
    "KT", "kt", "SSG", "NC", "울산 웨일즈",
)


def target(player):
    if "statsAutoUpdate" in player:
        return player["statsAutoUpdate"] is True
    label = player.get("teamLabel", "")
    if player.get("entryPending"):
        return False
    if any(word in label for word in ("은퇴", "미확인", "입단 전", "방출")):
        return False
    return player.get("currentLG", False) or any(c in label for c in clubs)


def innings(value):
    value = str(value).replace("⅓", " 1/3").replace("⅔", " 2/3")
    if not re.fullmatch(r"\d+(?:\s+[12]/3)?|[12]/3", value.strip()):
        raise ValueError("이닝 형식 미확인")
    return sum(Fraction(part) for part in value.split())


def cells(row):
    values = []
    for cell in row.find_all(["th", "td"], recursive=False):
        values.append(cell.get_text(" ", strip=True))
        values.extend([""] * (int(cell.get("colspan", 1)) - 1))
    return values


def parse_page(content, player):
    soup = BeautifulSoup(content, "html.parser")
    text = soup.get_text(" ", strip=True)
    name = re.search(r"선수명\s*:\s*(\S+)", text)
    if not name or name.group(1) not in {
        player["name"], player.get("oldName", player["name"])
    }:
        raise ValueError("KBO 선수명 불일치 또는 페이지 확인 실패")

    birth = re.search(
        r"생년월일\s*:\s*(\d{4})년\s*(\d{1,2})월\s*(\d{1,2})일", text
    )
    expected = re.findall(r"\d+", player.get("birthday", ""))
    if birth and len(expected) >= 3:
        if tuple(map(int, birth.groups())) != tuple(map(int, expected[:3])):
            raise ValueError("생년월일 불일치")

    pitching = "PitcherDetail" in player["kbo"]
    indicator = "ERA" if pitching else "AVG"

    for table in soup.find_all("table"):
        rows = [cells(row) for row in table.find_all("tr")]
        header = next(
            (row for row in rows
             if "연도" in row and "팀명" in row and indicator in row),
            None,
        )
        if not header:
            continue
        total = next(
            (row for row in rows if row and row[0] == "통산"), None
        )
        if not total:
            continue
        if len(total) == len(header) - 1:
            total.insert(1, "")
        if len(total) != len(header):
            raise ValueError("통산 표 열 개수 불일치")
        data = dict(zip(header, total))
        mapping = (
            {"경기": "G", "이닝": "IP", "승": "W", "패": "L",
             "세이브": "SV", "홀드": "HLD", "탈삼진": "SO", "ERA": "ERA"}
            if pitching else
            {"경기": "G", "타석": "PA", "안타": "H", "홈런": "HR",
             "타점": "RBI", "도루": "SB",
             "AVG": "AVG", "OBP": "OBP", "SLG": "SLG"}
        )
        metrics = {key: data[column] for key, column in mapping.items()}
        for key, value in metrics.items():
            if key in ("AVG", "OBP", "SLG", "ERA"):
                if value != "-" and not re.fullmatch(r"\d*\.\d+", value):
                    raise ValueError("비율 기록 형식 오류")
            elif key != "이닝" and not re.fullmatch(r"\d+", value):
                raise ValueError("누적 기록 형식 오류")

        if pitching:
            ip = innings(data["IP"])
            metrics["WHIP"] = (
                f"{(int(data['H']) + int(data['BB'])) / float(ip):.2f}"
                if ip else "-"
            )
        elif data["OBP"] != "-" and data["SLG"] != "-":
            metrics["OPS"] = f"{float(data['OBP']) + float(data['SLG']):.3f}"
        else:
            metrics["OPS"] = "-"

        lg_first = any(
            len(row) == len(header)
            and row[1] == "LG"
            and re.fullmatch(r"\d{4}", row[0])
            and row[header.index("G")].isdigit()
            and int(row[header.index("G")]) > 0
            for row in rows
        )
        return metrics, lg_first

    if any(s in text for s in (
        "데이터가 존재하지 않습니다", "기록이 없습니다",
        "기록이 존재하지 않습니다"
    )):
        return {}, False
    raise ValueError("KBO 정규시즌 통산 표를 확인하지 못했습니다.")


session = requests.Session()
session.headers["User-Agent"] = "LGDraftArchive/1.0 (personal stats archive)"
report = []
blocked = False

for player in players:
    if not target(player):
        continue
    item = {"id": player["id"], "name": player["name"]}
    url = player.get("kbo", "")
    item["source"] = url
    if not re.fullmatch(
        r"https://www\.koreabaseball\.com/Record/Player/"
        r"(?:Hitter|Pitcher)Detail/Total\.aspx\?playerId=\d+",
        url,
    ):
        item.update(status="skipped", reason="KBO 통산 주소 미확인")
        report.append(item)
        continue

    old = records.setdefault(player["id"], {})
    previous_note = old.get("statsDateNote", "2026.09.24–25 조회")
    previous_note = previous_note.split(" · 최근 시도 실패")[0]
    try:
        if blocked:
            raise ValueError("접근 제한으로 이번 실행의 추가 조회 중단")
        response = session.get(url, timeout=(10, 20))
        if response.status_code in (401, 403, 429):
            blocked = True
        response.raise_for_status()
        response.encoding = "utf-8"
        new_stats, lg_first = parse_page(response.text, player)

        for key, value in old.get("stats", {}).items():
            if key in ("AVG", "OBP", "SLG", "OPS", "ERA", "WHIP"):
                continue
            if key not in new_stats:
                raise ValueError("기존 누적 기록 항목 누락")
            if key == "이닝":
                if innings(new_stats[key]) < innings(value):
                    raise ValueError("누적 이닝 감소: 검토 필요")
            elif str(value).isdigit():
                if int(new_stats[key]) < int(value):
                    raise ValueError(f"누적 {key} 감소: 검토 필요")

        old["stats"] = new_stats
        old["statsDateNote"] = (
            f"{STAMP} KBO 통산 페이지 조회 · 최종 경기 반영일 미제공"
        )
        if new_stats:
            old.pop("noStatsReason", None)
            item["status"] = "updated"
        else:
            old["noStatsReason"] = "KBO 정규시즌 1군 통산 기록 없음."
            item["status"] = "no_records"
        if lg_first:
            player["lgFirst"] = True
            player["firstVerified"] = True
    except Exception as error:
        item.update(status="failed", reason=str(error)[:180])
        old["statsDateNote"] = (
            previous_note + f" · 최근 시도 실패({STAMP}), 기존 기록 유지"
        )
    finally:
        report.append(item)
        if not blocked:
            time.sleep(2)

for year, group in groups.items():
    save(ROOT / "entries" / f"{year}.json", group)
save(ROOT / "stats.json", records)
save(ROOT / "meta.json", meta)
save(ROOT / "stats-report.json", {
    "retrievedAt": STAMP,
    "scope": "저장된 소속 기준 프로 소속 선수의 KBO 정규시즌 누적 기록",
    "players": report,
})

counts = {
    state: sum(r["status"] == state for r in report)
    for state in ("updated", "no_records", "failed", "skipped")
}
summary = (
    f"# KBO 기록 갱신\n\n조회: {STAMP}\n\n"
    f"- 통산 기록 확인: {counts['updated']}명\n"
    f"- 1군 기록 없음 확인: {counts['no_records']}명\n"
    f"- 실패하여 기존 기록 유지: {counts['failed']}명\n"
    f"- KBO 주소 미확인: {counts['skipped']}명\n\n"
)
for row in report:
    if row["status"] in ("failed", "skipped"):
        summary += f"- {row['name']}: {row['reason']}\n"
if os.environ.get("GITHUB_STEP_SUMMARY"):
    with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as out:
        out.write(summary)
print(summary)
if counts["failed"]:
    print("::warning::일부 기록 갱신 실패. stats-report.json을 확인하세요.")
if not counts["updated"] and not counts["no_records"]:
    print("::warning::이번 실행에서는 KBO 기록 갱신에 성공하지 못했습니다.")
