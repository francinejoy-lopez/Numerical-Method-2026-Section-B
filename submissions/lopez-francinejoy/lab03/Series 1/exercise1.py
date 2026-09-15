"""
Laboratory Exercise 1:
Compute (1 + 1/n)^n for compounding periods from yearly to nanosecond.
Draw histogram / bar charts in Matplotlib using the specified color palette.
"""

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch
from decimal import Decimal, getcontext
import math
from pathlib import Path

getcontext().prec = 50
OUTPUT_DIR = Path(__file__).resolve().parent / "artifacts"
OUTPUT_DIR.mkdir(exist_ok=True)

# Color palette
FERN_GREEN = '#3E8241'
PISTACHIO = '#8CD18E'
LIGHT_GREEN = '#9AE69C'
LAVENDER = '#BA98F5'
ROYAL_PURPLE = '#6948A3'

# Compounding frequencies (n = number of periods per year)
# Approximating a non-leap year
periods = [
    ("yearly", 1),
    ("semi-annually", 2),
    ("quarterly", 4),
    ("monthly", 12),
    ("weekly", 52),
    ("daily", 365),
    ("hourly", 365 * 24),
    ("per minute", 365 * 24 * 60),
    ("per second", 365 * 24 * 60 * 60),
    ("millisecond", 365 * 24 * 60 * 60 * 1000),
    ("microsecond", 365 * 24 * 60 * 60 * 1000 * 1000),
    ("nanosecond", 365 * 24 * 60 * 60 * 1000 * 1000 * 1000),
]

labels = [p[0] for p in periods]
ns = [p[1] for p in periods]

# High-precision computation
values = []
for n in ns:
    nd = Decimal(n)
    val = (Decimal(1) + Decimal(1) / nd) ** nd
    values.append(float(val))

e_approx = math.e
errors = [abs(v - e_approx) for v in values]

# Theoretical error ~ e/(2n)
theo_errors = [e_approx / (2 * n) for n in ns]

# Create figure with two subplots
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6), dpi=150)
fig.suptitle(r"Exercise 1: Convergence of $\left(1 + \frac{1}{n}\right)^n$ to $e$",
             fontsize=16, fontweight='bold', color=ROYAL_PURPLE)

# Left: Values
x = np.arange(len(labels))
bars1 = ax1.bar(x, values, color=PISTACHIO, edgecolor=FERN_GREEN, linewidth=1.2, width=0.7)
ax1.axhline(y=e_approx, color=ROYAL_PURPLE, linestyle='--', linewidth=2, label=r'$e \approx 2.71828$')
ax1.set_xticks(x)
ax1.set_xticklabels(labels, rotation=45, ha='right', fontsize=9)
ax1.set_ylabel(r"Value of $\left(1 + \frac{1}{n}\right)^n$", fontsize=11)
ax1.set_title("Value per compounding period", fontsize=13, color=FERN_GREEN)
ax1.set_ylim(1.9, 2.85)
ax1.legend(loc='lower right', fontsize=10)
ax1.grid(axis='y', linestyle=':', alpha=0.6)
ax1.set_axisbelow(True)

# Annotate a few values
for i, (bar, v) in enumerate(zip(bars1, values)):
    if i in [0, 1, 2, 5, 11]:
        ax1.annotate(f'{v:.4f}', xy=(bar.get_x() + bar.get_width()/2, v),
                     xytext=(0, 4), textcoords='offset points',
                     ha='center', va='bottom', fontsize=7, color=ROYAL_PURPLE)

# Right: Errors (log scale)
bars2 = ax2.bar(x, errors, color=LAVENDER, edgecolor=ROYAL_PURPLE, linewidth=1.2, width=0.7, label='Actual |error|')
ax2.plot(x, theo_errors, 'o-', color=FERN_GREEN, linewidth=2, markersize=6, label=r'Theory $\approx e/(2n)$')
ax2.set_xticks(x)
ax2.set_xticklabels(labels, rotation=45, ha='right', fontsize=9)
ax2.set_ylabel(r"$|\left(1 + \frac{1}{n}\right)^n - e|$  (log scale)", fontsize=11)
ax2.set_title("Error shrinks like $e/(2n)$", fontsize=13, color=ROYAL_PURPLE)
ax2.set_yscale('log')
ax2.legend(loc='upper right', fontsize=9)
ax2.grid(axis='y', linestyle=':', alpha=0.6)
ax2.set_axisbelow(True)

plt.tight_layout(rect=[0, 0, 1, 0.95])
plt.savefig(OUTPUT_DIR / 'exercise1_plot.png', dpi=200, bbox_inches='tight',
            facecolor='white', edgecolor='none')
plt.close()

# Also print the table for verification
print("Compounding Frequency Table")
print("-" * 60)
print(f"{'How often':<18} {'n':>18} {'(1+1/n)^n':>14}")
print("-" * 60)
for lab, n, v in zip(labels, ns, values):
    print(f"{lab:<18} {n:>18,} {v:>14.6f}")
print("-" * 60)
print(f"{'limit e':<18} {'∞':>18} {e_approx:>14.6f}")
print("\nPlot saved to exercise1_plot.png")
