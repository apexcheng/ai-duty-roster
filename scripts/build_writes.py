# -*- coding: utf-8 -*-
"""构建写入参数: 清空区 + 批量写值"""
import json

writes = json.load(open('nov_writes.json', encoding='utf-8'))  # [row, col, value]

# 1) 追加块6的行标签 (早/中/晚 at col0/col8)
writes += [
    [30, 0, '早'], [30, 8, '早'],
    [31, 0, '中'], [31, 8, '中'],
    [32, 0, '晚'], [32, 8, '晚'],
]

# 2) 底部汇总区 (行已 +5)
PRE = ['员工A', '员工B', '员工C', '员工D', '员工E', '员工F', '员工G', '员工H', '员工I']
AFT = ['员工J', '员工K', '员工L', '员工M', '员工N', '员工O', '员工P', '员工Q', '员工R']
early_rows = [6, 11, 16, 21, 26, 31]   # Excel 1-based 早班行
late_rows = [8, 13, 18, 23, 28, 33]    # Excel 1-based 晚班行

# 指定休息表: row38(0-based) 售后 员工P 2、7、9 3天
writes += [[38, 1, '售后'], [38, 2, '员工P'], [38, 3, '2、7、9'], [38, 4, 3], [38, 5, '计入正常休息额度']]
writes += [[39, 1, ''], [39, 2, ''], [39, 3, ''], [39, 4, ''], [39, 5, '']]
# 请假休息表: row43 售后 员工O
writes += [[43, 1, '售后'], [43, 2, '员工O'], [43, 3, '2~7、9~12'], [43, 4, 10], [43, 5, '请假不占正常休息额度']]
# 请假说明文字 (合并区 42,7)
writes += [[42, 7, '说明：请假日期不排班，不占正常休息额度；本月员工O请假 10 天。']]

# 排班汇总 rows 48-56
def cntif(rows, c1, c2, name):
    return '=' + '+'.join(f'COUNTIF({c1}{r}:{c2}{r},"*{name}*")' for r in rows)

for i, n in enumerate(PRE):
    r0 = 48 + i          # 0-based
    R = r0 + 1           # Excel 1-based
    writes += [
        [r0, 2, cntif(early_rows, 'B', 'H', n)],
        [r0, 3, cntif(late_rows, 'B', 'H', n)],
        [r0, 4, f'=30-G{R}-F{R}'],
        [r0, 5, 0],
        [r0, 6, f'=C{R}+D{R}'],
    ]
for i, n in enumerate(AFT):
    r0 = 48 + i
    R = r0 + 1
    leave_v = 10 if n == '员工O' else 0
    writes += [
        [r0, 10, cntif(early_rows, 'J', 'P', n)],
        [r0, 11, cntif(late_rows, 'J', 'P', n)],
        [r0, 12, f'=30-O{R}-N{R}'],
        [r0, 13, leave_v],
        [r0, 14, f'=K{R}+L{R}'],
    ]

def typed(v):
    if isinstance(v, str) and v.startswith('='):
        return {'value_type': 'FORMULA', 'formula': v}
    if isinstance(v, (int, float)):
        return {'value_type': 'NUMBER', 'number_value': v}
    return {'value_type': 'STRING', 'string_value': v}

values = [dict(row=r, col=c, **typed(v)) for r, c, v in writes if v is not None]
json.dump({'sheet_id': 'Rce0LN', 'values': values}, open('set_values_args.json', 'w', encoding='utf-8'), ensure_ascii=False)
print('writes:', len(values))

# 清空区
clears = [
    # 线下 block1-5 日期/简称/人员 (cols 18-24) 全清后重写日期
    (3, 18, 27, 24),
    # 售前 block1 10月残留 (cols 4-6)
    (3, 4, 7, 6),
    # 售后 block1 10月残留 (cols 12-14)
    (3, 12, 7, 14),
]
json.dump(clears, open('clears.json', 'w', encoding='utf-8'))
print('clears:', clears)
