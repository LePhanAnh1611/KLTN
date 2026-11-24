import json, numpy as np, matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
plt.rcParams.update({'font.family': 'Liberation Serif', 'font.size': 12, 'axes.spines.top': False, 'axes.spines.right': False,
                     'axes.edgecolor': '#555', 'axes.labelcolor': '#222', 'xtick.color': '#333', 'ytick.color': '#333',
                     'axes.grid': True, 'grid.color': '#e3e3e3', 'grid.linewidth': 0.8, 'axes.axisbelow': True})
C = ['#2a78d6', '#eb6834', '#1baf7a', '#eda100', '#8a8a8a']
A = json.load(open('/tmp/claude-0/mlx/an/out/analysis.json'))
NAME = {'item_rate': 'Tỉ lệ đúng của từ', 'user_rate': 'Tỉ lệ đúng của người học', 'last_result': 'Kết quả lần trước',
        'irt': 'IRT một tham số', 'bkt': 'BKT', 'logreg': 'Hồi quy logistic (37 đặc trưng)',
        'gbdt': 'Cây tăng cường (37 đặc trưng)', 'gbdt_user': 'Cây tăng cường (+3 đặc trưng người học)',
        'sakt': 'SAKT', 'dkt': 'DKT theo chỉ số', 'dkt_feat': 'DKT dựa trên đặc trưng'}
f = lambda v: f'{v:.3f}'.replace('.', ',')

# 1. AUC + KTC
order = ['user_rate', 'last_result', 'item_rate', 'bkt', 'irt', 'logreg', 'sakt', 'gbdt', 'gbdt_user', 'dkt', 'dkt_feat']
order = sorted([m for m in order if m in A['overall']], key=lambda m: A['overall'][m]['auc_test'])
v = [A['overall'][m]['auc_test'] for m in order]
fig, ax = plt.subplots(figsize=(8.6, 5.0), dpi=200)
y = np.arange(len(order))
col = [C[4] if m in ('user_rate', 'last_result', 'item_rate') else C[2] if m in ('irt', 'logreg', 'gbdt', 'gbdt_user') else C[0] for m in order]
col[-1] = C[1]
ax.barh(y, v, color=col, height=0.6)
for i, m in enumerate(order):
    if m in A['ci']:
        lo, hi = A['ci'][m]; ax.plot([lo, hi], [i, i], color='#222', lw=1.2)
    ax.text(v[i] + 0.004, i, f(v[i]), va='center', color='#222', fontsize=11)
ax.axvline(0.774, color='#555', ls='--', lw=1); ax.text(0.772, -0.45, 'baseline SLAM\n0,774', fontsize=9.5, ha='right', va='bottom', color='#444')
ax.axvline(0.861, color='#555', ls=':', lw=1); ax.text(0.863, -0.45, 'nhóm đầu\nSLAM 0,861', fontsize=9.5, ha='left', va='bottom', color='#444')
ax.set_yticks(y, [NAME[m] for m in order]); ax.set_xlim(0.6, 0.92); ax.set_ylim(-0.6, len(order) - 0.4)
ax.set_xlabel('AUC trên tập test SLAM en_es (vạch đen: KTC 95%)')
ax.grid(axis='y', visible=False)
from matplotlib.patches import Patch
ax.legend(handles=[Patch(color=C[4], label='Mô hình cơ sở đơn giản'), Patch(color=C[2], label='Mô hình không dùng chuỗi'),
                   Patch(color=C[0], label='Mô hình Knowledge Tracing'), Patch(color=C[1], label='Mô hình của đề tài')],
          frameon=True, facecolor='white', edgecolor='#ddd', loc='lower right', bbox_to_anchor=(1.0, 0.13), fontsize=10)
fig.tight_layout(); fig.savefig('/tmp/claude-0/diag/chart_auc.png'); plt.close()

# 2. reliability
fig, axs = plt.subplots(1, 2, figsize=(9.6, 4.2), dpi=200, gridspec_kw={'width_ratios': [1.25, 1]})
ax = axs[0]; ax.plot([0, 1], [0, 1], color='#999', ls='--', lw=1, label='Hiệu chỉnh hoàn hảo')
for k, m in enumerate(['dkt_feat', 'dkt', 'sakt', 'gbdt_user']):
    if m not in A['reliability']: continue
    r = np.array(A['reliability'][m]); keep = r[:, 2] >= 200
    ax.plot(r[keep, 0], r[keep, 1], marker='o', ms=4, lw=1.6, color=[C[1], C[0], C[3], C[2]][k],
            label=f"{NAME[m]} (ECE {f(A['overall'][m]['ece'])})")
ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.set_xlabel('Xác suất dự đoán trung bình trong khoảng'); ax.set_ylabel('Tỉ lệ trả lời đúng thực tế')
ax.legend(frameon=True, facecolor='white', edgecolor='#ddd', fontsize=9, loc='lower right')
ax = axs[1]; r = np.array(A['reliability']['dkt_feat'])
ax.bar(r[:, 0], r[:, 2] / r[:, 2].sum() * 100, width=0.07, color=C[1])
ax.set_xlim(0, 1); ax.set_xlabel('Xác suất dự đoán (DKT dựa trên đặc trưng)'); ax.set_ylabel('% số lượt trên tập test')
fig.tight_layout(); fig.savefig('/tmp/claude-0/diag/chart_reliability_slam.png'); plt.close()

# 3. AUC theo số lần đã gặp từ
g = A['groups']['seen']; labs = [r['group'] for r in g]
fig, ax = plt.subplots(figsize=(8.6, 3.8), dpi=200); x = np.arange(len(g)); w = 0.26
for k, m in enumerate(['dkt_feat', 'dkt', 'gbdt_user']):
    vals = [r.get(m, np.nan) for r in g]
    ax.bar(x + (k - 1) * w, vals, w * 0.92, color=[C[1], C[0], C[2]][k], label=NAME[m])
    for i, vv in enumerate(vals): ax.text(x[i] + (k - 1) * w, vv + 0.004, f(vv), ha='center', fontsize=8.5)
ax.set_xticks(x, [f"{l}\n({r['n']:,} lượt)".replace(',', '.') for l, r in zip(labs, g)])
ax.set_ylim(0.6, 0.9); ax.set_ylabel('AUC trên tập test'); ax.set_xlabel('Số lần người học đã gặp từ trước lượt được chấm')
ax.grid(axis='x', visible=False); ax.legend(frameon=False, fontsize=10, ncol=3, loc='upper left')
fig.tight_layout(); fig.savefig('/tmp/claude-0/diag/chart_auc_seen.png'); plt.close()
print('ok')
