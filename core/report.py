"""签到报告模块 — 查看/导出签到结果"""

import json
import csv
from pathlib import Path
from datetime import datetime
import numpy as np

import os
PROJECT_ROOT = Path(__file__).resolve().parent.parent
MEETINGS_ROOT = PROJECT_ROOT / 'data' / 'courses'


def _meeting_path(name):
    return MEETINGS_ROOT / name


def _load_attendance(meeting_name):
    path = _meeting_path(meeting_name) / 'attendance.json'
    if not path.exists():
        return []
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def _load_names(meeting_name):
    names_path = _meeting_path(meeting_name) / 'names.npy'
    if not names_path.exists():
        return None
    return np.load(names_path)


def get_statistics(meeting_name):
    """返回签到统计数据"""
    names = _load_names(meeting_name)
    records = _load_attendance(meeting_name)
    checked_names = set(r['name'] for r in records)

    # 优先用 participants 目录的实际数量（比 facebank 准确）
    try:
        import course as meeting_mod
        participants = meeting_mod.get_participants(meeting_name)
        total = len(participants)
        all_names_list = [p['name'] for p in participants]
    except Exception:
        total = len(names) - 1 if names is not None else 0
        all_names_list = list(names[1:]) if names is not None and len(names) > 1 else []

    checked = len(checked_names)

    # 预期参会人员
    try:
        import course as meeting_mod
        expected = meeting_mod.get_expected_participants(meeting_name)
        expected_count = len(expected) if expected else 0
        deadline = meeting_mod.get_checkin_deadline(meeting_name)
    except Exception:
        expected = None
        expected_count = total
        deadline = None

    # 迟到统计
    late_count = sum(1 for r in records if r.get('late', False))

    # 按时间排序
    records_sorted = sorted(records, key=lambda r: r['time'])

    # 安全计算
    denom = max(expected_count, 1)  # 防止除零
    not_checked = max(0, expected_count - checked)  # 防止负数
    rate_val = checked / denom * 100 if denom > 0 else 0
    return {
        "meeting": meeting_name,
        "total_participants": total,
        "expected_count": expected_count,
        "expected_names": expected if expected else all_names_list,
        "checked_in": checked,
        "late_count": late_count,
        "ontime_count": checked - late_count,
        "not_checked_in": not_checked,
        "checkin_deadline": deadline,
        "checkin_rate": f"{rate_val:.1f}%",
        "records": records_sorted,
        "checked_names": sorted(checked_names),
        "all_names": all_names_list
    }


def show_report(meeting_name):
    """终端打印签到报告"""
    stats = get_statistics(meeting_name)
    all_names = stats['all_names']
    records_sorted = stats['records']
    checked_names = stats['checked_names']

    print(f"\n{'='*45}")
    print(f"  会议: {meeting_name}")
    print(f"{'='*45}")
    print(f"  总人数:     {stats['total_participants']}")
    print(f"  已签到:     {stats['checked_in']}")
    print(f"  未签到:     {stats['not_checked_in']}")
    print(f"  签到率:     {stats['checkin_rate']}")
    print(f"{'='*45}")

    if records_sorted:
        print(f"\n  签到明细:")
        print(f"  {'姓名':<12} {'签到时间':<22} {'置信度':<10}")
        print(f"  {'-'*44}")
        for r in records_sorted:
            t = r['time'][:19]  # 截断秒后精度
            print(f"  {r['name']:<12} {t:<22} {r['confidence']:<10.3f}")
    else:
        print("\n  暂无签到记录")

    print(f"\n  签到状态:")
    for n in all_names:
        mark = "✓ 已签到" if n in checked_names else "○ 未签到"
        print(f"    {mark}  {n}")
    print(f"{'='*45}\n")


def export_csv(meeting_name):
    """导出签到记录为 CSV"""
    stats = get_statistics(meeting_name)
    output_path = _meeting_path(meeting_name) / 'checkin_log.csv'

    with open(output_path, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.writer(f)
        writer.writerow(['会议名称', meeting_name])
        writer.writerow(['导出时间', datetime.now().isoformat()[:19]])
        writer.writerow(['总人数', stats['total_participants']])
        writer.writerow(['已签到', stats['checked_in']])
        writer.writerow(['未签到', stats['not_checked_in']])
        writer.writerow(['签到率', stats['checkin_rate']])
        writer.writerow([])
        writer.writerow(['姓名', '签到时间', '置信度(距离)'])
        for r in stats['records']:
            writer.writerow([r['name'], r['time'][:19], f"{r['confidence']:.3f}"])
        writer.writerow([])
        writer.writerow(['签到状态'])
        for n in stats['all_names']:
            status = '已签到' if n in stats['checked_names'] else '未签到'
            writer.writerow([n, status])

    print(f"CSV 已导出: {output_path}")
    return str(output_path)


def export_html(meeting_name):
    """导出签到报告为 HTML"""
    stats = get_statistics(meeting_name)
    output_path = _meeting_path(meeting_name) / 'checkin_report.html'

    # 构建签到明细行
    detail_rows = ""
    for r in stats['records']:
        t = r['time'][:19]
        detail_rows += f"""
        <tr>
            <td>{r['name']}</td>
            <td>{t}</td>
            <td>{r['confidence']:.3f}</td>
        </tr>"""

    # 构建签到状态行
    status_rows = ""
    for n in stats['all_names']:
        checked = n in stats['checked_names']
        icon = "✓" if checked else "○"
        color = "#27ae60" if checked else "#e74c3c"
        status_rows += f"""
        <tr>
            <td style="color:{color}; font-size:1.3em;">{icon}</td>
            <td>{n}</td>
            <td style="color:{color};">{'已签到' if checked else '未签到'}</td>
        </tr>"""

    # 没有签到记录时的占位
    if not detail_rows:
        detail_rows = '<tr><td colspan="3" style="text-align:center;color:#999;">暂无签到记录</td></tr>'

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<title>会议签到报告 - {meeting_name}</title>
<style>
body {{ font-family: "Microsoft YaHei", sans-serif; max-width: 800px; margin: 30px auto; padding: 0 20px; background: #f5f6fa; }}
h1 {{ color: #2c3e50; text-align: center; }}
.summary {{ display: flex; gap: 15px; justify-content: center; flex-wrap: wrap; margin: 20px 0; }}
.card {{ background: #fff; border-radius: 10px; padding: 20px 30px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); text-align: center; }}
.card .num {{ font-size: 2em; font-weight: bold; color: #2c3e50; }}
.card .label {{ font-size: 0.85em; color: #7f8c8d; }}
table {{ width: 100%; border-collapse: collapse; background: #fff; border-radius: 10px; overflow: hidden; box-shadow: 0 2px 8px rgba(0,0,0,0.1); margin: 20px 0; }}
th {{ background: #2c3e50; color: #fff; padding: 12px; text-align: left; }}
td {{ padding: 10px 12px; border-bottom: 1px solid #ecf0f1; }}
tr:last-child td {{ border-bottom: none; }}
.footer {{ text-align: center; color: #95a5a6; font-size: 0.85em; margin: 20px 0; }}
</style>
</head>
<body>
<h1>📋 会议签到报告</h1>
<p style="text-align:center;color:#7f8c8d;">{meeting_name} | 导出时间: {datetime.now().isoformat()[:19]}</p>

<div class="summary">
    <div class="card"><div class="num">{stats['total_participants']}</div><div class="label">总人数</div></div>
    <div class="card"><div class="num" style="color:#27ae60;">{stats['checked_in']}</div><div class="label">已签到</div></div>
    <div class="card"><div class="num" style="color:#e74c3c;">{stats['not_checked_in']}</div><div class="label">未签到</div></div>
    <div class="card"><div class="num" style="color:#2980b9;">{stats['checkin_rate']}</div><div class="label">签到率</div></div>
</div>

<h2>签到明细</h2>
<table>
<tr><th>姓名</th><th>签到时间</th><th>置信度</th></tr>
{detail_rows}
</table>

<h2>签到状态</h2>
<table>
<tr><th>状态</th><th>姓名</th><th>结果</th></tr>
{status_rows}
</table>

<div class="footer">
    Generated by InsightFace Check-in System | {datetime.now().isoformat()[:19]}
</div>
</body>
</html>"""

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)

    print(f"HTML 报告已导出: {output_path}")
    return str(output_path)
