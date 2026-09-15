"""
Laboratory Exercise 2:
Compute (a^h - 1)/h for bases a=2, a≈e, a=3 as h shrinks to tolerance ~1e-6.
Draw bar chart / histogram in Matplotlib using the specified color palette.
"""

import numpy as np
import matplotlib.pyplot as plt
import math
from pathlib import Path

OUTPUT_DIR = Path(__file__).resolve().parent / "artifacts"
OUTPUT_DIR.mkdir(exist_ok=True)

# Color palette
FERN_GREEN = '#3E8241'
PISTACHIO = '#8CD18E'
LIGHT_GREEN = '#9AE69C'
LAVENDER = '#BA98F5'
ROYAL_PURPLE = '#6948A3'

# Bases
a_values = {
    'a = 2': 2.0,
    'a = e': math.e,
    'a = 3': 3.0,
}

# h values from 0.1 down to ~1e-7 (covers tolerance ×10^{-6})
hs = [0.1, 0.01, 0.001, 0.0001, 1e-5, 1e-6, 1e-7]

# Limits = ln(a)
limits = {k: math.log(v) for k, v in a_values.items()}

# Compute the difference quotients
results = {k: [] for k in a_values}
for h in hs:
    for name, a in a_values.items():
        # Use expm1 for numerical stability when a^h is close to 1
        # a^h - 1 = exp(h * log(a)) - 1
        val = math.expm1(h * math.log(a)) / h
        results[name].append(val)

# Create figure
fig, ax = plt.subplots(figsize=(12, 7), dpi=150)
fig.suptitle(r"Exercise 2: $\frac{a^h - 1}{h}$ settling to $\ln(a)$",
             fontsize=16, fontweight='bold', color=ROYAL_PURPLE)

x = np.arange(len(hs))
width = 0.25

colors = [PISTACHIO, LAVENDER, FERN_GREEN]
edge_colors = [FERN_GREEN, ROYAL_PURPLE, '#2E5A2F']

bars = []
for i, (name, vals) in enumerate(results.items()):
    offset = (i - 1) * width
    b = ax.bar(x + offset, vals, width, label=f'{name} (ln a = {limits[name]:.5f})',
               color=colors[i], edgecolor=edge_colors[i], linewidth=1.1)
    bars.append(b)

# Dashed horizontal lines for the limits
line_styles = ['--', '-.', ':']
for i, (name, lim) in enumerate(limits.items()):
    ax.axhline(y=lim, color=edge_colors[i], linestyle=line_styles[i],
               linewidth=1.8, alpha=0.85, label=f'limit {name}')

ax.set_xticks(x)
ax.set_xticklabels([f'h = {h:g}' for h in hs], fontsize=10)
ax.set_xlabel(r'Step size $h$ (shrinking)', fontsize=12)
ax.set_ylabel(r'$\frac{a^h - 1}{h}$', fontsize=13)
ax.set_title("Bars: difference quotient per h.  Dashed lines: the limit ln(a).",
             fontsize=12, color=FERN_GREEN)
ax.legend(loc='upper right', fontsize=9, ncol=2)
ax.set_ylim(0.65, 1.25)
ax.grid(axis='y', linestyle=':', alpha=0.55)
ax.set_axisbelow(True)

# Annotate the settled values on the last group
for i, (name, vals) in enumerate(results.items()):
    ax.annotate(f'{vals[-1]:.5f}',
                xy=(x[-1] + (i-1)*width, vals[-1]),
                xytext=(0, 6), textcoords='offset points',
                ha='center', va='bottom', fontsize=8, color=edge_colors[i])

plt.tight_layout(rect=[0, 0, 1, 0.94])
plt.savefig(OUTPUT_DIR / 'exercise2_plot.png', dpi=200, bbox_inches='tight',
            facecolor='white', edgecolor='none')
plt.close()

# Print the table matching the PDF style
print("Table of (a^h - 1)/h")
print("-" * 70)
print(f"{'h':>10}  {'a = 2':>12}  {'a ≈ e':>12}  {'a = 3':>12}")
print("-" * 70)
for i, h in enumerate(hs):
    row = f"{h:>10g}"
    for name in a_values:
        row += f"  {results[name][i]:>12.4f}"
    print(row)
print("-" * 70)
print(f"{'settles at':>10}  {limits['a = 2']:>12.4f}  {limits['a = e']:>12.4f}  {limits['a = 3']:>12.4f}")
print("\nTolerance × 10^{-6}  (h reaches 1e-6 and beyond)")
print("Plot saved to exercise2_plot.png")
