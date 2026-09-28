# -*- coding: utf-8 -*-
"""解析10月历史 -> 生成2026年11月排班 -> 全量验证 -> 输出写入块"""
import json, random, datetime, sys
from collections import defaultdict

random.seed(20261101)

# ---------- 1. 解析10月日历 ----------
d = json.load(open('oct_cells2.json', encoding='utf-8'))
grid = {}
for c in d.get('cells') or []:
    t = c.get('value_type')
    v = c.get('number_value') if t == 'NUMBER' else c.get('string_value')
    if v is None or v == '':
        continue
    grid[(c['row'], c['col'])] = v

def cell(r, c):
    v = grid.get((r, c))
    if v is None:
        return None
    if isinstance(v, float) and v == int(v):
        return int(v)
    return str(v).strip() if isinstance(v, str) else v

PRE = ['员工A', '员工B', '员工C', '员工D', '员工E', '员工F', '员工G', '员工H', '员工I']
AFT = ['员工J', '员工K', '员工L', '员工M', '员工N', '员工O', '员工P', '员工Q', '员工R']
NAMES = set(PRE) | set(AFT)

# 10月日期->(row,col) 映射：块1 row3 cols4-7=1-4; 块2 row8 cols1-7=5-11; 块3 row13; 块4 row18; 块5 row23 cols1-6=26-31
date_pos = {}
for day in range(1, 5):
    date_pos[day] = (3, 3 + day)          # cols 4..7
for i, day in enumerate(range(5, 12)):
    date_pos[day] = (8, 1 + i)
for i, day in enumerate(range(12, 19)):
    date_pos[day] = (13, 1 + i)
for i, day in enumerate(range(19, 26)):
    date_pos[day] = (18, 1 + i)
for i, day in enumerate(range(26, 32)):
    date_pos[day] = (23, 1 + i)

early_rows = [5, 10, 15, 20, 25]
late_rows = [7, 12, 17, 22, 27]
# 每个日期所在的(早row,晚row,售前列基) — 售前块列1-7(部分周偏移)，售后块列9-15(部分周偏移+3)
def block_of_day(day):
    if day <= 4:
        return 0
    if day <= 11:
        return 1
    if day <= 18:
        return 2
    if day <= 25:
        return 3
    return 4

def col_for_day(day, group):
    b = block_of_day(day)
    if group == 'pre':
        base = {0: 1, 1: 1, 2: 1, 3: 1, 4: 1}[b]  # 售前日期列: 块0 cols4-7 -> 周四起
        if b == 0:
            return 1 + (day - 1 + 3)  # Oct1=周四 -> col4
        return 1 + (day - 1) % 7 - ((day - 1) // 7 - 1) * 0 if False else 1 + ((day - 2) % 7) if b >= 1 else None
    return None

# 简化：直接按块算列偏移
def day_col(day, group):
    b = block_of_day(day)
    if group == 'pre':
        if b == 0:
            return 4 + (day - 1)            # 1->4 ... 4->7
        start = {1: 5, 2: 12, 3: 19, 4: 26}[b]
        return 1 + (day - start)
    else:
        if b == 0:
            return 12 + (day - 1)
        start = {1: 5, 2: 12, 3: 19, 4: 26}[b]
        return 9 + (day - start)

# 解析每人每日状态
oct_status = {n: {} for n in NAMES}
for day in range(1, 32):
    b = block_of_day(day)
    er = early_rows[b]
    lr = late_rows[b]
    for grp, people in (('pre', PRE), ('aft', AFT)):
        c = day_col(day, grp)
        ce = cell(er, c) or ''
        cl = cell(lr, c) or ''
        for n in people:
            if n in ce.split() or n in ce.replace('\u3000', ' ').split():
                oct_status[n][day] = '早'
            elif n in cl.replace('\u3000', ' ').split():
                oct_status[n][day] = '晚'
            else:
                oct_status[n][day] = '休'

# 10月汇总统计
oct_stat = {}
for n in sorted(NAMES):
    st = oct_status[n]
    e = sum(1 for v in st.values() if v == '早')
    l = sum(1 for v in st.values() if v == '晚')
    r = sum(1 for v in st.values() if v == '休')
    # 月底连续工作段 + 最后班型
    run = 0
    day = 31
    while day >= 1 and st[day] != '休':
        run += 1
        day -= 1
    last = None
    day = 31
    while day >= 1:
        if st[day] != '休':
            last = st[day]
            break
        day -= 1
    # 月底连续工作段内的班型分布
    oct_stat[n] = dict(早=e, 晚=l, 休=r, 月底连跑=run, 最后班型=last)
print('=== 10月历史 ===')
for n in PRE:
    print('售前', n, oct_stat[n])
for n in AFT:
    print('售后', n, oct_stat[n])

# 10月基础休息 = clamp(31-26,3,6)=5; 余额 = 实际-5
bal = {n: oct_stat[n]['休'] - 5 for n in NAMES}
print('跨月余额:', {n: bal[n] for n in NAMES})

# ---------- 2. 生成11月排班 ----------
DAYS = 30
NDAYS = list(range(1, 31))
spec_rest = {'员工P': [2, 7, 9]}
leave = {'员工O': [2, 3, 4, 5, 6, 7, 9, 10, 11, 12]}

# 11月1日是周日; 周块: [1], [2-8], [9-15], [16-22], [23-29], [30]
# 状态: 早/晚/休/假
status = {n: {} for n in NAMES}
for n, ds in spec_rest.items():
    for dd in ds:
        status[n][dd] = '休'
for n, ds in leave.items():
    for dd in ds:
        status[n][dd] = '假'

# 目标正常休息 = clamp(30-26,3,6)=4, 加跨月补偿微调 (保持 3-6 边界)
target_rest = {}
for n in NAMES:
    t = 4 + (1 if bal[n] <= -2 else 0) + (-1 if bal[n] >= 2 else 0)
    target_rest[n] = max(3, min(6, t))
    if n in spec_rest:
        target_rest[n] = max(target_rest[n], len(spec_rest[n]))  # 至少覆盖指定休息
print('11月目标休息:', target_rest)

def gen_group(people, seed):
    rnd = random.Random(seed)
    tg = {n: target_rest[n] for n in people}
    last_shift = {n: oct_stat[n]['最后班型'] for n in people}
    run_before = {n: oct_stat[n]['月底连跑'] for n in people}

    for attempt in range(500):
        s = {n: dict(status[n]) for n in people}   # 已含指定休息/请假
        work_cnt = {n: 0 for n in people}
        rest_cnt = {n: 0 for n in people}
        for n in people:
            for dd, v in s[n].items():
                if v == '休':
                    rest_cnt[n] += 1
                elif v in ('早', '晚'):
                    work_cnt[n] += 1
        runs = {n: run_before[n] for n in people}
        prev_shift = {n: last_shift[n] for n in people}
        prev_worked = {n: (run_before[n] > 0) for n in people}
        early_cnt = {n: 0 for n in people}
        late_cnt = {n: 0 for n in people}
        ok = True
        for dd in NDAYS:
            fixed_off = [n for n in people if s[n].get(dd) in ('休', '假')]
            avail = [n for n in people if dd not in s[n]]
            # 休息预算: 剩余需要休息的人日 / 剩余天数
            rem = sum(max(0, tg[n] - rest_cnt[n]) for n in people)
            rem_days = 31 - dd
            need_rest = int(round(rem / rem_days))
            cap = 3 - len(fixed_off)          # 保证上班>=6
            need_rest = max(1, min(min(3, cap), need_rest))
            if 9 - len(fixed_off) - need_rest < 6:
                need_rest = 9 - len(fixed_off) - 6
            # 选休息者: 连跑>=7 优先(接近7天一休), 再未达标者, 再连跑长
            cand = sorted(avail, key=lambda n: (
                0 if runs[n] >= 7 else 1,
                0 if rest_cnt[n] < tg[n] else 1,
                -runs[n],
                rnd.random()))
            rest_today = cand[:need_rest]
            workers = [n for n in avail if n not in rest_today]
            ne, nl = {6: (3, 3), 7: None, 8: (4, 4)}[len(workers)] if len(workers) in (6, 8) else (None, None)
            if len(workers) == 7:
                ne, nl = (3, 4) if sum(early_cnt.values()) <= sum(late_cnt.values()) else (4, 3)
            # 早班候选: 排除 晚班次日(昨在班且昨班=晚)
            def early_ok(n):
                return not (prev_shift[n] == '晚' and prev_worked[n])
            e_pool = [n for n in workers if early_ok(n)]
            if len(e_pool) < ne:
                ok = False
                break
            e_pool.sort(key=lambda n: (early_cnt[n] - late_cnt[n], rnd.random()))
            earlies = e_pool[:ne]
            rest_e = [n for n in workers if n not in earlies]
            rest_e.sort(key=lambda n: (late_cnt[n] - early_cnt[n], rnd.random()))
            laters = rest_e[:nl]
            if len(laters) < nl:
                ok = False
                break
            for n in people:
                if n in earlies:
                    s[n][dd] = '早'
                    work_cnt[n] += 1
                    early_cnt[n] += 1
                    runs[n] += 1
                    prev_shift[n] = '早'
                    prev_worked[n] = True
                elif n in laters:
                    s[n][dd] = '晚'
                    work_cnt[n] += 1
                    late_cnt[n] += 1
                    runs[n] += 1
                    prev_shift[n] = '晚'
                    prev_worked[n] = True
                elif n in rest_today:
                    s[n][dd] = '休'
                    rest_cnt[n] += 1
                    runs[n] = 0
                    prev_worked[n] = False
                # 假/固定休 已在 s 中
        if not ok:
            continue
        # 校验
        good = True
        for n in people:
            r = sum(1 for v in s[n].values() if v == '休')
            w = sum(1 for v in s[n].values() if v in ('早', '晚'))
            lv = sum(1 for v in s[n].values() if v == '假')
            if not (3 <= r <= 6):
                good = False
            if lv == 0 and not (24 <= w <= 27):
                good = False
            if lv > 0 and w > 27:
                good = False
            run = run_before[n]
            for dd in NDAYS:
                v = s[n][dd]
                if v in ('早', '晚'):
                    run += 1
                    if run > 10:
                        good = False
                else:
                    run = 0
            prev = last_shift[n]
            prevw = run_before[n] > 0
            for dd in NDAYS:
                v = s[n][dd]
                if v == '早' and prev == '晚' and prevw:
                    good = False
                prevw = v in ('早', '晚')
                if v in ('早', '晚'):
                    prev = v
            e = sum(1 for v in s[n].values() if v == '早')
            l = sum(1 for v in s[n].values() if v == '晚')
            if abs(e - l) > 3:
                good = False
        if good:
            return s
    return None

for grp_name, people in (('售前', PRE), ('售后', AFT)):
    res = None
    for seed in range(3000, 3100):
        res = gen_group(people, seed)
        if res:
            print(f'{grp_name} 用种子 {seed} 生成成功')
            break
    if not res:
        print(f'{grp_name} 生成失败')
        sys.exit(1)
    for n in people:
        status[n].update(res[n])

# ---------- 3. 全量验证 ----------
errors = []
# 每日班次人数
for grp_name, people in (('售前', PRE), ('售后', AFT)):
    for dd in NDAYS:
        e = sum(1 for n in people if status[n][dd] == '早')
        l = sum(1 for n in people if status[n][dd] == '晚')
        if not (3 <= e <= 4):
            errors.append(f'{grp_name} {dd}日早班{e}人')
        if not (3 <= l <= 4):
            errors.append(f'{grp_name} {dd}日晚班{l}人')
# 指定休息/请假
for n, ds in spec_rest.items():
    for dd in ds:
        if status[n][dd] != '休':
            errors.append(f'{n} {dd}日指定休息未满足')
for n, ds in leave.items():
    for dd in ds:
        if status[n][dd] != '假':
            errors.append(f'{n} {dd}日请假未满足')
# 晚转早(跨月)
for n in NAMES:
    prev = oct_status[n][31]
    prevw = True
    for dd in NDAYS:
        v = status[n][dd]
        if v == '早' and prev == '晚' and prevw:
            errors.append(f'{n} {dd}日晚转早')
        prevw = v in ('早', '晚')
        if v in ('早', '晚'):
            prev = v
# 连续工作
for n in NAMES:
    run = oct_stat[n]['月底连跑']
    for dd in NDAYS:
        v = status[n][dd]
        if v in ('早', '晚'):
            run += 1
            if run > 10:
                errors.append(f'{n} {dd}日连续工作{run}天')
        else:
            run = 0
# 对账 + 汇总
summary = {}
for n in NAMES:
    e = sum(1 for v in status[n].values() if v == '早')
    l = sum(1 for v in status[n].values() if v == '晚')
    r = sum(1 for v in status[n].values() if v == '休')
    lv = sum(1 for v in status[n].values() if v == '假')
    assert e + l + r + lv == DAYS, n
    if not (3 <= r <= 6):
        errors.append(f'{n} 正常休息{r}天越界')
    if lv == 0 and not (24 <= e + l <= 27):
        errors.append(f'{n} 上班{e+l}天越界')
    if lv > 0 and e + l > 27:
        errors.append(f'{n} 有请假上班{e+l}>27')
    if abs(e - l) > 3:
        errors.append(f'{n} 早晚不均衡 早{e}晚{l}')
    summary[n] = (e, l, r, lv, e + l)

if errors:
    print('验证失败:')
    for x in errors:
        print(' -', x)
    sys.exit(1)
print('=== 验证全部通过 ===')
print('=== 11月汇总 (早/晚/休/假/上班) ===')
for n in PRE:
    print('售前', n, summary[n])
for n in AFT:
    print('售后', n, summary[n])

# 连续工作段长度分布
for grp_name, people in (('售前', PRE), ('售后', AFT)):
    for n in people:
        segs = []
        run = oct_stat[n]['月底连跑']
        started = run > 0
        for dd in NDAYS:
            v = status[n][dd]
            if v in ('早', '晚'):
                run += 1
            else:
                if run > 0:
                    segs.append(run)
                run = 0
        if run > 0:
            segs.append(run)
        # print(grp_name, n, '工作段:', segs)

json.dump({'summary': summary, 'target_rest': target_rest, 'bal': bal},
          open('nov_summary.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

# ---------- 4. 输出写入块 ----------
def abbr(n):
    """休息行简称：脱敏占位符取末位字母(A~R)"""
    return n[-1]


blocks = []  # 每周块: (row0, days list with col offset info)
# 11月周块(0-based row): 块1 r3 (仅1日 col7/15/24), 块2 r8 (2-8), 块3 r13, 块4 r18, 块5 r23, 块6 r28 (仅30日 col1/9/18)
week_blocks = [
    (3, {7: 1}),                                   # 售前 col7=1日
    (8, {1 + i: dd for i, dd in enumerate(range(2, 9))}),
    (13, {1 + i: dd for i, dd in enumerate(range(9, 16))}),
    (18, {1 + i: dd for i, dd in enumerate(range(16, 23))}),
    (23, {1 + i: dd for i, dd in enumerate(range(23, 30))}),
    (28, {1: 30}),
]
AFT_week_blocks = [
    (3, {15: 1}),
    (8, {9 + i: dd for i, dd in enumerate(range(2, 9))}),
    (13, {9 + i: dd for i, dd in enumerate(range(9, 16))}),
    (18, {9 + i: dd for i, dd in enumerate(range(16, 23))}),
    (23, {9 + i: dd for i, dd in enumerate(range(23, 30))}),
    (28, {9: 30}),
]
LX_week_blocks = [  # 线下: 顺序日期 1-7,8-14,15-21,22-28,29-30
    (3, {19 + i: dd for i, dd in enumerate(range(1, 7))}),
    (8, {18 + i: dd for i, dd in enumerate(range(7, 14))}),
    (13, {18 + i: dd for i, dd in enumerate(range(14, 21))}),
    (18, {18 + i: dd for i, dd in enumerate(range(21, 28))}),
    (23, {18: 29, 19: 30}),
]

writes = []  # (row, col, value)
def W(r, c, v):
    writes.append((r, c, v))

for grp_name, people, wbs, base in (('售前', PRE, week_blocks, 1), ('售后', AFT, AFT_week_blocks, 9)):
    for br, dmap in wbs:
        er, lr, ar = br + 2, br + 4, br + 1  # 早/晚/简称行
        for col, dd in dmap.items():
            W(br, col, dd)  # 日期(数字)
            rest_here = [n for n in people if status[n][dd] == '休']
            leave_here = [n for n in people if status[n][dd] == '假']
            abbrs = [abbr(n) for n in rest_here + leave_here]
            W(ar, col, '   '.join(abbrs) if abbrs else None)
            W(er, col, '   '.join(n for n in people if status[n][dd] == '早') or None)
            W(lr, col, '   '.join(n for n in people if status[n][dd] == '晚') or None)

# 线下日期(保留模板标签, 清空人员)
for br, dmap in LX_week_blocks:
    for col, dd in dmap.items():
        W(br, col, dd)

json.dump(writes, open('nov_writes.json', 'w', encoding='utf-8'), ensure_ascii=False)
print('写入单元格数:', len(writes))
print('OK')
