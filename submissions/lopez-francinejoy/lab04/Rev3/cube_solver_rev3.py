# File: rev3_deliverables/cube_solver_rev3.py
"""Cube Solver Rev. 3 — Interactive solver (Tk + matplotlib 3D canvas).

Tabbed solver interface: Loads (live 3D viewer), Validation, Combinations and Model
(interactive: click nodes/members on the canvas to inspect them).

Run:  python cube_solver_rev3.py
"""

import os
os.environ.setdefault("MPLBACKEND", "TkAgg")

import tkinter as tk
from tkinter import ttk

import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import (FigureCanvasTkAgg,
                                               NavigationToolbar2Tk)

from cube_structure_rev4 import L, MEMBERS, NODES, member_type
from rev3_analysis import run_rev3_workflow
from rev3_viewer import (draw_load_case, render_combination, OUTPUT_DIR,
                         _draw_structure, _sphere)
from rev3_loads import (nscp_asd_combinations, nscp_lrfd_combinations,
                        nscp_temperature_combinations)


# ---- solver interface palette (pastel / light) ----
C_BG = "#EDE8DF"
C_CARD = "#F7F4EF"
C_CARD2 = "#E5DFD4"
C_EDGE = "#C4B5A0"
C_TXT = "#3D3830"
C_SUB = "#6B5E50"
C_ACC = "#8B9A7A"
C_ACC_D = "#5C6B4A"
C_SEL = "#C4A574"
C_OK = "#7FBF8E"
C_WARN = "#F0B37E"

# Logical (inches) canvas sizes the two 3D figures are LAID OUT at — every
# title, legend and info-panel position inside them is a fraction of these,
# and every font a fixed point size. MUST match the figsize= used in
# rev3_viewer.draw_load_case()/render_combination() (Loads tab) and the
# figsize set on self.mfig below (Model tab).
LOADS_FIG_SIZE = (16.0, 9.5)
MODEL_FIG_SIZE = (8.4, 7.2)


class SolverApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        root.title("Rev. 3 — Structural Load Solver")
        root.geometry("1420x900")
        root.minsize(1000, 650)
        root.configure(bg=C_BG)
        self._is_fullscreen = False
        self._maximize_on_start()
        root.bind("<F11>", self._toggle_fullscreen)
        root.bind("<Escape>", self._exit_fullscreen)

        self.model, self.diaphragm, self.validation, _r, _c = run_rev3_workflow(run_analysis=False)

        self.entries = [("Load Case", c) for c in self.model.load_cases]
        self.entries += [("LRFD", c) for c in nscp_lrfd_combinations()]
        self.entries += [("ASD", c) for c in nscp_asd_combinations()]
        self.entries += [("Temperature", c) for c in nscp_temperature_combinations()]

        self._style()
        self._header()
        self.tabs = ttk.Notebook(root)
        self.tabs.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        self.tab_loads = tk.Frame(self.tabs, bg=C_BG)
        self.tab_valid = tk.Frame(self.tabs, bg=C_BG)
        self.tab_combo = tk.Frame(self.tabs, bg=C_BG)
        self.tab_model = tk.Frame(self.tabs, bg=C_BG)
        for name, tab in (("Loads", self.tab_loads), ("Validation", self.tab_valid),
                          ("Combinations", self.tab_combo), ("Model", self.tab_model)):
            self.tabs.add(tab, text=f"  {name}  ")

        self._build_loads_tab()
        self._build_validation_tab()
        self._build_combinations_tab()
        self._build_model_tab()
        # re-fit 3D views when the main window is maximized / resized
        self.root.bind("<Configure>", self._on_root_configure)
        self._root_cfg_after = None


    # ---------- window sizing: maximize on open, F11 for true fullscreen ----------
    def _maximize_on_start(self):
        """Open maximized (fills the screen, keeps window chrome) instead of
        the fixed 1420x900 box — that box was the "can't make it fullscreen"
        problem: there was nothing sizing the window past its start size."""
        try:
            self.root.state("zoomed")          # Windows, most Linux WMs
        except tk.TclError:
            try:
                self.root.attributes("-zoomed", True)   # some Linux WMs
            except tk.TclError:
                sw = self.root.winfo_screenwidth()
                sh = self.root.winfo_screenheight()
                self.root.geometry(f"{sw}x{sh}+0+0")

    def _toggle_fullscreen(self, _event=None):
        """F11: true borderless fullscreen (no window chrome). Escape exits."""
        self._is_fullscreen = not self._is_fullscreen
        self.root.attributes("-fullscreen", self._is_fullscreen)

    def _exit_fullscreen(self, _event=None):
        if self._is_fullscreen:
            self._is_fullscreen = False
            self.root.attributes("-fullscreen", False)

    # ---------- styling / chrome ----------
    def _style(self):
        style = ttk.Style(self.root)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("TNotebook", background=C_BG, borderwidth=0)
        style.configure("TNotebook.Tab", background=C_CARD, foreground=C_SUB,
                        padding=(18, 8), font=("Segoe UI", 11, "bold"))
        style.map("TNotebook.Tab",
                  background=[("selected", C_ACC_D)],
                  foreground=[("selected", "white")])
        style.configure("Dash.TCombobox", fieldbackground=C_CARD, background=C_CARD2,
                        foreground=C_TXT, arrowcolor=C_ACC_D)
        style.configure("Dash.TCheckbutton", background=C_BG, foreground=C_TXT)
        style.map("Dash.TCheckbutton", background=[("active", C_BG)])
        style.configure("Dash.TButton", background=C_CARD, foreground=C_TXT,
                        padding=(10, 6), borderwidth=0)
        style.map("Dash.TButton", background=[("active", C_ACC)],
                  foreground=[("active", "white")])
        style.configure("Dash.TLabel", background=C_BG, foreground=C_TXT)
        # the combobox popdown list ignores ttk styles — set it directly
        self.root.option_add("*TCombobox*Listbox.background", C_CARD)
        self.root.option_add("*TCombobox*Listbox.foreground", C_TXT)
        self.root.option_add("*TCombobox*Listbox.selectBackground", C_ACC)
        self.root.option_add("*TCombobox*Listbox.selectForeground", "white")
        # clickable load list (Treeview) — pastel to match the solver interface
        style.configure("Dash.Treeview", background=C_CARD, fieldbackground=C_CARD,
                        foreground=C_TXT, rowheight=32, borderwidth=0,
                        font=("Segoe UI", 11))
        style.map("Dash.Treeview",
                  background=[("selected", C_ACC_D)],
                  foreground=[("selected", "white")])

    def _header(self):
        hdr = tk.Frame(self.root, bg=C_BG)
        hdr.pack(fill="x", padx=10, pady=(10, 4))
        tk.Label(hdr, text="REV. 3", bg=C_ACC, fg="white", font=("Segoe UI", 10, "bold"),
                 padx=10, pady=4).pack(side="left")
        tk.Label(hdr, text=" Structural Load Solver", bg=C_BG, fg=C_TXT,
                 font=("Segoe UI", 15, "bold")).pack(side="left", padx=10)
        tk.Label(hdr, text=f"{len(NODES)} nodes · {len(MEMBERS)} members · "
                 f"{len(self.model.load_cases)} load cases",
                 bg=C_BG, fg=C_SUB, font=("Segoe UI", 11)).pack(side="right")
        ttk.Button(hdr, text="⛶ Fullscreen (F11)", command=self._toggle_fullscreen,
                   style="Dash.TButton").pack(side="right", padx=(0, 12))

    def _card(self, parent, title=None):
        card = tk.Frame(parent, bg=C_CARD, highlightbackground=C_EDGE,
                        highlightthickness=1)
        if title:
            tk.Label(card, text=title, bg=C_CARD, fg=C_ACC_D,
                     font=("Segoe UI", 12, "bold")).pack(anchor="w", padx=12, pady=(8, 2))
        return card

    # ---------- Loads tab ----------
    def _build_loads_tab(self):
        body = tk.Frame(self.tab_loads, bg=C_BG)
        body.pack(fill="both", expand=True)

        # ---- left: category tabs + button list (no scrollbar) ----
        side = self._card(body, "LOAD SELECTION")
        side.pack(side="left", fill="y", padx=(8, 6), pady=8)
        side.configure(width=280)
        side.pack_propagate(False)

        self._load_groups = (
            ("Cases", "Load Case"),
            ("LRFD", "LRFD"),
            ("ASD", "ASD"),
            ("Temp", "Temperature"),
        )
        cat_bar = tk.Frame(side, bg=C_CARD)
        cat_bar.pack(fill="x", padx=6, pady=(4, 4))
        self._cat_btns = {}
        self._active_kind = "Load Case"
        self._selected_idx = 0
        for label, kind in self._load_groups:
            b = tk.Button(
                cat_bar, text=label, relief="flat", bd=0, cursor="hand2",
                font=("Segoe UI", 10, "bold"), padx=6, pady=5,
                command=lambda k=kind: self._switch_load_category(k),
            )
            b.pack(side="left", fill="x", expand=True, padx=1)
            self._cat_btns[kind] = b
        self._style_cat_buttons()

        # plain button stack — no scrollbar
        self._load_inner = tk.Frame(side, bg=C_CARD)
        self._load_inner.pack(fill="both", expand=True, padx=6, pady=(0, 6))
        self._load_btns = {}
        self._populate_load_buttons()

        # ---- right: controls + live 3D canvas ----
        right = tk.Frame(body, bg=C_BG)
        right.pack(side="left", fill="both", expand=True)
        bar = tk.Frame(right, bg=C_BG)
        bar.pack(fill="x", padx=6, pady=(8, 2))
        self.grid_on = tk.BooleanVar(value=True)
        ttk.Checkbutton(bar, text="Grid", variable=self.grid_on,
                        command=self.redraw, style="Dash.TCheckbutton").pack(side="left", padx=6)
        ttk.Button(bar, text="Save PNG", command=self.save_png,
                   style="Dash.TButton").pack(side="left", padx=6)
        self._pick_hint = tk.Label(bar, text="→ pick a load case or combination",
                                   bg=C_BG, fg=C_SUB, font=("Segoe UI", 11, "italic"))
        self._pick_hint.pack(side="right", padx=6)

        # Host frame = true available area (avoids TkAgg Configure feedback loop)
        self._loads_host = tk.Frame(right, bg=C_BG, highlightthickness=0)
        self._loads_host.pack(fill="both", expand=True, padx=4, pady=4)

        self.fig = draw_load_case(self.model, self.entries[0][1])
        self.canvas = FigureCanvasTkAgg(self.fig, master=self._loads_host)
        self.canvas.get_tk_widget().configure(bg="#EDE8DF", highlightthickness=0)
        self.canvas.get_tk_widget().pack(fill="both", expand=True)
        self.toolbar = NavigationToolbar2Tk(self.canvas, right)
        self.toolbar.config(bg=C_BG)
        self.toolbar.update()
        self._loads_host.bind("<Configure>", self._on_loads_host_resize)
        self._resize_after = None
        self.root.after(200, self._apply_loads_resize)
        self.redraw()

    def _style_cat_buttons(self):
        for kind, b in self._cat_btns.items():
            if kind == self._active_kind:
                b.configure(bg=C_ACC_D, fg="white", activebackground=C_ACC_D,
                            activeforeground="white")
            else:
                b.configure(bg=C_CARD2, fg=C_TXT, activebackground=C_ACC,
                            activeforeground="white")

    def _populate_load_buttons(self):
        for w in self._load_inner.winfo_children():
            w.destroy()
        self._load_btns.clear()
        first = None
        for i, (kind, entry) in enumerate(self.entries):
            if kind != self._active_kind:
                continue
            if first is None:
                first = i
            b = tk.Button(
                self._load_inner, text=entry.name, anchor="w",
                relief="flat", bd=0, cursor="hand2",
                font=("Segoe UI", 11), padx=10, pady=6,
                bg=C_CARD, fg=C_TXT, activebackground=C_ACC,
                activeforeground="white",
                command=lambda idx=i: self._select_load(idx),
            )
            b.pack(fill="x", pady=1, padx=2)
            self._load_btns[i] = b
        if self._selected_idx not in self._load_btns and first is not None:
            self._selected_idx = first
        self._highlight_load_buttons()

    def _highlight_load_buttons(self):
        for i, b in self._load_btns.items():
            if i == self._selected_idx:
                b.configure(bg=C_ACC_D, fg="white",
                            activebackground=C_ACC_D, activeforeground="white",
                            font=("Segoe UI", 11, "bold"))
            else:
                b.configure(bg=C_CARD, fg=C_TXT,
                            activebackground=C_ACC, activeforeground="white",
                            font=("Segoe UI", 11))

    def _switch_load_category(self, kind):
        self._active_kind = kind
        self._style_cat_buttons()
        self._populate_load_buttons()
        self.redraw()

    def _select_load(self, idx):
        self._selected_idx = idx
        self._highlight_load_buttons()
        self.redraw()

    def _current(self):
        idx = self._selected_idx if 0 <= self._selected_idx < len(self.entries) else 0
        kind, entry = self.entries[idx]
        if kind == "Load Case":
            return entry, None
        return None, entry

    def redraw(self):
        case, combo = self._current()
        old = self.fig
        if case is not None:
            self.fig = draw_load_case(self.model, case, show_grid=self.grid_on.get())
        else:
            self.fig = render_combination(self.model, combo, show_grid=self.grid_on.get())
        old.clf()
        plt.close(old)
        self.canvas.figure = self.fig
        self.fig.patch.set_facecolor("#EDE8DF")
        # new figures are born at 16x9.5 — sync to the host frame size now
        self._apply_loads_resize()

    def _fit_figure(self, fig, canvas, native_size=None):
        self._apply_loads_resize()

    def _on_loads_host_resize(self, event):
        if event.widget is not getattr(self, "_loads_host", None):
            return
        if event.width < 80 or event.height < 80:
            return
        if getattr(self, "_resize_after", None) is not None:
            try:
                self.root.after_cancel(self._resize_after)
            except Exception:
                pass
        self._resize_after = self.root.after(60, self._apply_loads_resize)

    def _apply_loads_resize(self):
        self._resize_after = None
        host = getattr(self, "_loads_host", None)
        if host is None or not hasattr(self, "fig") or not hasattr(self, "canvas"):
            return
        try:
            host.update_idletasks()
        except Exception:
            pass
        w = int(host.winfo_width())
        h = int(host.winfo_height())
        if w < 80 or h < 80:
            return
        fig = self.fig
        dpi = float(fig.get_dpi() or 100.0)
        fig.set_size_inches(w / dpi, h / dpi, forward=False)
        fig.patch.set_facecolor("#EDE8DF")
        try:
            self.canvas.resize(w, h)
        except Exception:
            pass
        try:
            for ax in fig.axes:
                ax.set_facecolor("#EDE8DF")
                if hasattr(ax, "patch"):
                    ax.patch.set_facecolor("#EDE8DF")
                    ax.patch.set_alpha(1.0)
                if hasattr(ax, "xaxis") and hasattr(ax.xaxis, "pane"):
                    for pane in (ax.xaxis.pane, ax.yaxis.pane, ax.zaxis.pane):
                        pane.set_facecolor("#EDE8DF")
                        pane.set_alpha(1.0)
                        pane.set_edgecolor("#EDE8DF")
        except Exception:
            pass
        self.canvas.draw_idle()

    def _sync_figure_to_widget(self, fig, canvas):
        # kept for compatibility with redraw / root refit
        if canvas is getattr(self, "canvas", None):
            self._apply_loads_resize()
        elif canvas is getattr(self, "mcanvas", None):
            self._apply_model_resize()

    def save_png(self):
        case, combo = self._current()
        if case is not None:
            safe = case.name.replace(" ", "_").replace("/", "-")
            path = OUTPUT_DIR / f"rev3_loads_case{case.id}_{safe}.png"
            draw_load_case(self.model, case, path, show_grid=self.grid_on.get())
        else:
            path = OUTPUT_DIR / f"rev3_combination_{combo.name.replace(' ', '_').replace('+', 'p')}.png"
            render_combination(self.model, combo, path, show_grid=self.grid_on.get())
        print(f"Saved: {path}")

    # ---------- Validation tab ----------
    def _build_validation_tab(self):
        card = self._card(self.tab_valid, "LOAD-CASE VALIDATION")
        card.pack(fill="both", expand=True, padx=14, pady=14)
        wrap = tk.Frame(card, bg=C_CARD)
        wrap.pack(fill="both", expand=True, padx=8, pady=(4, 10))
        yscroll = ttk.Scrollbar(wrap, orient="vertical")
        xscroll = ttk.Scrollbar(wrap, orient="horizontal")
        txt = tk.Text(
            wrap, bg=C_CARD, fg=C_TXT, relief="flat", borderwidth=0,
            font=("Consolas", 12), padx=18, pady=14,
            spacing1=4, spacing3=5, wrap="none",
            yscrollcommand=yscroll.set, xscrollcommand=xscroll.set,
        )
        yscroll.config(command=txt.yview)
        xscroll.config(command=txt.xview)
        yscroll.pack(side="right", fill="y")
        xscroll.pack(side="bottom", fill="x")
        txt.pack(side="left", fill="both", expand=True)
        txt.tag_config("title", foreground=C_ACC_D, font=("Segoe UI", 15, "bold"),
                       spacing1=8, spacing3=10)
        txt.tag_config("h", foreground=C_ACC_D, font=("Consolas", 12, "bold"),
                       spacing1=6, spacing3=4)
        txt.tag_config("row", foreground=C_TXT, font=("Consolas", 12),
                       spacing1=3, spacing3=3)
        txt.tag_config("diaph", foreground=C_SUB, font=("Consolas", 12),
                       spacing1=3, spacing3=3)
        txt.tag_config("rule", foreground=C_EDGE, font=("Consolas", 11))
        rule = "\u2500"
        txt.insert("end", "Load-Case Validation Summary\n", "title")
        txt.insert("end", rule * 72 + "\n", "rule")
        txt.insert("end", f"{'CASE':>4}  {'NAME':<28}{'CATEGORY':<20}{'TOTAL (kN)':>14}\n", "h")
        txt.insert("end", rule * 72 + "\n", "rule")
        for line in self.validation:
            txt.insert("end", line + "\n", "row")
        d = self.diaphragm
        txt.insert("end", "\n", "row")
        txt.insert("end", "Diaphragm\n", "h")
        txt.insert("end", rule * 48 + "\n", "rule")
        txt.insert("end", d.describe() + "\n", "diaph")
        txt.configure(state="disabled")

    # ---------- Combinations tab ----------
    def _build_combinations_tab(self):
        card = self._card(self.tab_combo, "NSCP LOAD COMBINATIONS")
        card.pack(fill="both", expand=True, padx=14, pady=14)
        wrap = tk.Frame(card, bg=C_CARD)
        wrap.pack(fill="both", expand=True, padx=8, pady=(4, 10))
        yscroll = ttk.Scrollbar(wrap, orient="vertical")
        xscroll = ttk.Scrollbar(wrap, orient="horizontal")
        txt = tk.Text(
            wrap, bg=C_CARD, fg=C_TXT, relief="flat", borderwidth=0,
            font=("Consolas", 12), padx=18, pady=14,
            spacing1=3, spacing3=4, wrap="none",
            yscrollcommand=yscroll.set, xscrollcommand=xscroll.set,
        )
        yscroll.config(command=txt.yview)
        xscroll.config(command=txt.xview)
        yscroll.pack(side="right", fill="y")
        xscroll.pack(side="bottom", fill="x")
        txt.pack(side="left", fill="both", expand=True)
        txt.tag_config("title", foreground=C_ACC_D, font=("Segoe UI", 15, "bold"),
                       spacing1=8, spacing3=8)
        txt.tag_config("section", foreground=C_ACC_D, font=("Segoe UI", 13, "bold"),
                       spacing1=14, spacing3=6)
        txt.tag_config("id", foreground=C_ACC_D, font=("Consolas", 12, "bold"))
        txt.tag_config("name", foreground=C_TXT, font=("Consolas", 12, "bold"))
        txt.tag_config("src", foreground=C_SUB, font=("Consolas", 11))
        txt.tag_config("rule", foreground=C_EDGE, font=("Consolas", 11))
        rule = "\u2500"
        txt.insert("end", "NSCP 2015 Load Combinations\n", "title")
        txt.insert("end", rule * 64 + "\n", "rule")
        for title, combos in (("LRFD  /  Factored", nscp_lrfd_combinations()),
                              ("ASD  /  Allowable", nscp_asd_combinations()),
                              ("Temperature", nscp_temperature_combinations())):
            txt.insert("end", f"\n{title}\n", "section")
            txt.insert("end", rule * 52 + "\n", "rule")
            for c in combos:
                txt.insert("end", f"  {c.id:>3}.  ", "id")
                txt.insert("end", f"{c.name:<28}  ", "name")
                txt.insert("end", f"{c.source}\n", "src")
        txt.configure(state="disabled")

    # ---------- Model tab (interactive) ----------
    def _build_model_tab(self):
        main = tk.Frame(self.tab_model, bg=C_BG)
        main.pack(fill="both", expand=True)

        # detail panel (left)
        panel = self._card(main, "MODEL EXPLORER")
        panel.pack(side="left", fill="y", padx=(10, 6), pady=10)
        self.detail = tk.Text(panel, width=34, bg=C_CARD, fg=C_TXT, relief="flat",
                              font=("Consolas", 12), padx=12, pady=10, height=24)
        self.detail.pack(fill="both", expand=True, padx=8, pady=(2, 10))
        self.detail.tag_config("h", foreground=C_ACC_D, font=("Consolas", 13, "bold"))
        self.detail.insert("end", "Click a node or member\non the 3D view.\n")
        self.detail.configure(state="disabled")

        # Parent FRAME owns the available space. We bind <Configure> on THIS
        # frame (not the matplotlib canvas) so there is no feedback loop with
        # TkAgg's own size handling — that loop was why the model stayed cropped.
        self._model_host = tk.Frame(main, bg=C_BG, highlightthickness=0)
        self._model_host.pack(side="right", fill="both", expand=True, padx=(0, 8), pady=8)

        self.mfig = plt.figure(figsize=(6, 5), facecolor=C_BG, dpi=100)
        self.max = self.mfig.add_axes([0.0, 0.0, 1.0, 1.0], projection="3d")
        self.mcanvas = FigureCanvasTkAgg(self.mfig, master=self._model_host)
        self.mcanvas.get_tk_widget().configure(bg=C_BG, highlightthickness=0)
        self.mcanvas.get_tk_widget().pack(fill="both", expand=True)
        self.mcanvas.mpl_connect("button_press_event", self._on_model_pick)
        self._selected = None

        # resize driven by the host frame's real allocated size
        self._model_host.bind("<Configure>", self._on_model_host_resize)
        self._model_resize_after = None
        self._draw_model()
        self.root.after(200, self._apply_model_resize)

    def _on_model_host_resize(self, event):
        if event.widget is not self._model_host:
            return
        if event.width < 80 or event.height < 80:
            return
        if self._model_resize_after is not None:
            try:
                self.root.after_cancel(self._model_resize_after)
            except Exception:
                pass
        self._model_resize_after = self.root.after(60, self._apply_model_resize)

    def _apply_model_resize(self):
        self._model_resize_after = None
        host = getattr(self, "_model_host", None)
        if host is None:
            return
        try:
            host.update_idletasks()
        except Exception:
            pass
        w = int(host.winfo_width())
        h = int(host.winfo_height())
        if w < 80 or h < 80:
            return
        dpi = float(self.mfig.get_dpi() or 100.0)
        self.mfig.set_size_inches(max(w, 80) / dpi, max(h, 80) / dpi, forward=False)
        try:
            # TkAgg: rebuild the PhotoImage at the new pixel size
            self.mcanvas.resize(w, h)
        except Exception:
            pass
        self._draw_model()

    def _force_model_fit(self):
        self._apply_model_resize()

    def _draw_model(self):
        ax = self.max
        try:
            elev, azim = ax.elev, ax.azim
        except Exception:
            elev, azim = 20, -55
        ax.clear()
        ax.set_position([0.0, 0.0, 1.0, 1.0])
        ax.set_facecolor(C_BG)
        try:
            ax.patch.set_facecolor(C_BG)
            ax.patch.set_alpha(1.0)
        except Exception:
            pass
        for pane in (ax.xaxis.pane, ax.yaxis.pane, ax.zaxis.pane):
            pane.set_facecolor(C_BG)
            pane.set_alpha(1.0)
            pane.set_edgecolor(C_BG)
        _draw_structure(ax, self.model, show_ids=True, show_grid=True)
        sel = self._selected
        if isinstance(sel, int):
            x, y, z = NODES[sel]
            _sphere(self.max, (x, z, y), 0.36, "#FFC55C", n=18)
        elif sel is not None:
            ni, nj = next((ni, nj) for m, ni, nj in MEMBERS if m == sel)
            p, q = NODES[ni], NODES[nj]
            ax.plot([p[0], q[0]], [p[2], q[2]], [p[1], q[1]], color="#FFC55C",
                    lw=7.0, zorder=6, solid_capstyle="round", alpha=0.9)
        M = 1.5
        ax.set_xlim(-M, L + M)
        ax.set_ylim(-M, L + M)
        ax.set_zlim(-0.8, L + M)
        try:
            ax.set_box_aspect((1, 1, 1))
        except Exception:
            pass
        ax.view_init(elev=elev, azim=azim)
        try:
            ax.set_proj_type("persp", focal_length=0.45)
        except Exception:
            try:
                ax.dist = 8
            except Exception:
                pass
        ax.set_xlabel("X (m)", color=C_TXT, fontsize=11)
        ax.set_ylabel("Z (m)", color=C_TXT, fontsize=11)
        ax.set_zlabel("Y (m)", color=C_TXT, fontsize=11)
        ax.tick_params(labelsize=10, colors="#6A5A8E")
        ax.set_title("Model — click a node or member", color=C_SUB, fontsize=12, pad=2)
        self.mfig.patch.set_facecolor(C_BG)
        try:
            self.mcanvas.draw_idle()
        except Exception:
            pass

    def _on_model_pick(self, event):
        # Pick in SCREEN space: project every node/member to display coords and
        # take the element nearest the click. (Comparing raw model coords to
        # event.x/y mixes data units with pixels — it always selected the wrong
        # element, which is why clicking "did nothing".)
        if event.inaxes is not self.max or event.x is None:
            return
        from mpl_toolkits.mplot3d import proj3d
        M = self.max.get_proj()

        def to_screen(p):
            x2d, y2d, _ = proj3d.proj_transform(p[0], p[2], p[1], M)
            xp, yp = self.max.transData.transform((x2d, y2d))
            return xp, yp

        best, bestd = None, 1e9
        for nid, (x, y, z) in NODES.items():
            xp, yp = to_screen((x, y, z))
            d = (xp - event.x) ** 2 + (yp - event.y) ** 2
            if d < bestd:
                best, bestd = nid, d
        for name, ni, nj in MEMBERS:
            p, q = NODES[ni], NODES[nj]
            for t in (0.25, 0.5, 0.75):        # sample along the member, not just its midpoint
                px = p[0] + (q[0] - p[0]) * t
                py = p[1] + (q[1] - p[1]) * t
                pz = p[2] + (q[2] - p[2]) * t
                xp, yp = to_screen((px, py, pz))
                d = (xp - event.x) ** 2 + (yp - event.y) ** 2
                if d < bestd:
                    best, bestd = name, d
        if best is not None:
            self._selected = best
            self._show_detail(best)
            self._draw_model()

    def _show_detail(self, sel):
        self.detail.configure(state="normal")
        self.detail.delete("1.0", "end")
        # --- hover-style detail: real properties from the Rev 2 libraries ---
        if isinstance(sel, int):
            x, y, z = NODES[sel]
            base = y == 0.0
            in_diaph = sel in self.diaphragm.constrained_nodes or sel == self.diaphragm.master_node
            self.detail.insert("end", f"NODE N{sel}\n", "h")
            for k, v in (("X", x), ("Y", y), ("Z", z)):
                self.detail.insert("end", f"  {k}: {v:.2f} m\n")
            self.detail.insert("end", f"  support: {'pinned' if base else 'free'}\n")
            self.detail.insert("end", f"  diaphragm: {'yes' if in_diaph else 'no'}\n")
        else:
            from rev3_analysis import member_properties
            ni, nj = next((ni, nj) for m, ni, nj in MEMBERS if m == sel)
            kind = member_type(sel, ni, nj)
            p = member_properties(sel)
            self.detail.insert("end", f"MEMBER {sel}\n", "h")
            self.detail.insert("end", f"  nodes: N{ni} -> N{nj}\n")
            self.detail.insert("end", f"  type:  {kind}\n")
            self.detail.insert("end", f"  section A: {p['A'] * 1e4:.1f} cm2\n")
            self.detail.insert("end", f"  material:  {p['material']}\n")
            self.detail.insert("end", f"  E:  {p['E'] / 1e6:.0f} MPa\n")
            self.detail.insert("end", f"  alpha: {p['alpha'] * 1e6:.1f} 1e-6/C\n")
            self.detail.insert("end", f"  (loads per case: see Loads tab)\n")
        self.detail.configure(state="disabled")


    def _on_root_configure(self, event):
        if event.widget is not self.root:
            return
        if getattr(self, "_root_cfg_after", None):
            try:
                self.root.after_cancel(self._root_cfg_after)
            except Exception:
                pass
        self._root_cfg_after = self.root.after(80, self._refit_all_canvases)

    def _refit_all_canvases(self):
        try:
            self._apply_loads_resize()
        except Exception:
            pass
        try:
            self._apply_model_resize()
        except Exception:
            pass



def main():
    root = tk.Tk()
    SolverApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()

