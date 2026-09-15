"""
Laboratory Exercise 3:
Compute the Taylor series for e^x = sum_{n=0}^∞ x^n / n!  up to 10,000 terms.
Draw histogram of partial sums and a convergence (digits) plot in Matplotlib
using the specified color palette.
"""

import numpy as np
import matplotlib.pyplot as plt
from math import factorial, exp, log10, floor
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

# We evaluate the series for e^1 (i.e., e itself) – the classic case.
# Up to N = 10_000 terms (indices 0 … 9999)
X = 1.0
MAX_TERMS = 10000
TRUE_VALUE = math.e

# Compute partial sums efficiently (running product to avoid huge factorials)
partial_sums = np.zeros(MAX_TERMS)
term = 1.0  # n=0 term
s = term
partial_sums[0] = s

for n in range(1, MAX_TERMS):
    term *= X / n          # next term = previous * x / n
    s += term
    partial_sums[n] = s

# Absolute errors
errors = np.abs(partial_sums - TRUE_VALUE)

# Approximate number of correct decimal digits
# (avoid log of zero; clamp very small errors)
with np.errstate(divide='ignore'):
    digits = -np.log10(np.maximum(errors, 1e-16))
digits = np.clip(digits, 0, 16)

# ---- Figure with two panels ----
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6), dpi=150)
fig.suptitle(r"Exercise 3: $e^x = \sum_{n=0}^{\infty}\frac{x^n}{n!}$  ($x=1$), summation up to $N=10{,}000$ terms",
             fontsize=14, fontweight='bold', color=ROYAL_PURPLE)

# Left panel: histogram of a selection of partial sums
# Sample every few hundred terms for a readable bar chart
sample_idx = np.unique(np.concatenate([
    np.arange(0, 30),                    # early terms
    np.linspace(30, 200, 15, dtype=int),
    np.linspace(200, 1000, 10, dtype=int),
    np.linspace(1000, 5000, 8, dtype=int),
    [9999]
]))
sample_sums = partial_sums[sample_idx]
sample_labels = [str(i) for i in sample_idx]

bars = ax1.bar(range(len(sample_idx)), sample_sums,
               color=LAVENDER, edgecolor=ROYAL_PURPLE, linewidth=0.8, width=0.85)
ax1.axhline(y=TRUE_VALUE, color=FERN_GREEN, linestyle='--', linewidth=2.2,
            label=fr'$e \approx {TRUE_VALUE:.6f}$')
ax1.set_xticks(range(0, len(sample_idx), max(1, len(sample_idx)//10)))
ax1.set_xticklabels([sample_labels[i] for i in range(0, len(sample_idx), max(1, len(sample_idx)//10))],
                    rotation=45, ha='right', fontsize=8)
ax1.set_xlabel("Number of terms (selected)", fontsize=11)
ax1.set_ylabel("Partial sum value", fontsize=11)
ax1.set_title("Histogram of the partial sums", fontsize=12, color=FERN_GREEN)
ax1.set_ylim(0, 3.0)
ax1.legend(loc='lower right', fontsize=10)
ax1.grid(axis='y', linestyle=':', alpha=0.55)
ax1.set_axisbelow(True)

# Right panel: how many correct digits vs number of terms (log x)
# Use a denser sampling for the line plot
N_plot = np.unique(np.concatenate([
    np.arange(0, 40),
    np.logspace(1.6, 4, 80, dtype=int)
]))
N_plot = N_plot[N_plot < MAX_TERMS]
digits_plot = digits[N_plot]
errors_plot = errors[N_plot]

ax2.semilogx(N_plot + 1, digits_plot, color=ROYAL_PURPLE, linewidth=2.2,
             label='Correct digits')
ax2.fill_between(N_plot + 1, 0, digits_plot, color=PISTACHIO, alpha=0.35)

# Mark a few milestones
milestones = [1, 5, 10, 20, 50, 100, 500, 1000, 5000, 10000]
for m in milestones:
    if m - 1 < MAX_TERMS:
        d = digits[m - 1]
        ax2.plot(m, d, 'o', color=FERN_GREEN, markersize=7, zorder=5)
        if m in [10, 100, 1000, 10000]:
            ax2.annotate(f'{d:.1f} dig',
                         xy=(m, d), xytext=(8, 4), textcoords='offset points',
                         fontsize=8, color=FERN_GREEN)

ax2.set_xlabel("Number of terms (log scale)", fontsize=11)
ax2.set_ylabel("Approx. correct decimal digits", fontsize=11)
ax2.set_title("How many correct digits each N buys (log N)", fontsize=12, color=ROYAL_PURPLE)
ax2.set_ylim(0, 17)
ax2.set_xlim(1, 12000)
ax2.legend(loc='lower right', fontsize=10)
ax2.grid(True, which='both', linestyle=':', alpha=0.5)
ax2.set_axisbelow(True)

# Secondary axis for the actual error (optional visual)
ax2b = ax2.twinx()
ax2b.semilogx(N_plot + 1, errors_plot, color=LAVENDER, linewidth=1.2, alpha=0.7, linestyle='--')
ax2b.set_ylabel(r"$|$error$|$ (log)", fontsize=10, color=LAVENDER)
ax2b.set_yscale('log')
ax2b.tick_params(axis='y', labelcolor=LAVENDER)
ax2b.set_ylim(1e-17, 3)

plt.tight_layout(rect=[0, 0, 1, 0.93])
plt.savefig(OUTPUT_DIR / 'exercise3_plot.png', dpi=200, bbox_inches='tight',
            facecolor='white', edgecolor='none')
plt.close()

# Summary output
print(f"Taylor series for e^{X} up to {MAX_TERMS} terms")
print(f"True value e = {TRUE_VALUE:.15f}")
print(f"Partial sum after 10 terms   : {partial_sums[9]:.15f}")
print(f"Partial sum after 20 terms   : {partial_sums[19]:.15f}")
print(f"Partial sum after 100 terms  : {partial_sums[99]:.15f}")
print(f"Partial sum after 1000 terms : {partial_sums[999]:.15f}")
print(f"Partial sum after 10000 terms: {partial_sums[9999]:.15f}")
print(f"Final absolute error         : {errors[-1]:.2e}")
print(f"Final correct digits (approx): {digits[-1]:.1f}")
print("\nPlot saved to exercise3_plot.png")
