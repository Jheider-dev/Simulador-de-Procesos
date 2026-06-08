import customtkinter as ctk
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import matplotlib
matplotlib.use("TkAgg")
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import random
import threading
import time
import os

import logica

#  THEME CONSTANTS

CLR = {
    "bg":        "#0d1117",
    "panel":     "#161b22",
    "card":      "#1c2230",
    "border":    "#30363d",
    "accent":    "#58a6ff",
    "accent2":   "#3fb950",
    "accent3":   "#f78166",
    "accent4":   "#d2a8ff",
    "accent5":   "#ffa657",
    "text":      "#e6edf3",
    "text_dim":  "#8b949e",
    "gantt_os":  "#21262d",
    "hover":     "#1f2937",
    "warning":   "#d29922",
}

PROCESS_COLORS = [
    "#58a6ff", "#3fb950", "#f78166", "#d2a8ff",
    "#ffa657", "#79c0ff", "#56d364", "#ff7b72",
    "#bc8cff", "#ffb77d", "#a5d6ff", "#7ee787",
]

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

#  HELPER WIDGETS

class MetricCard(ctk.CTkFrame):
    def __init__(self, master, title: str, unit: str = "%", accent: str = CLR["accent"], **kw):
        super().__init__(master, fg_color=CLR["card"], corner_radius=12,
                         border_width=1, border_color=CLR["border"], **kw)
        self.accent = accent
        self.unit = unit
        self._value = 0.0

        ctk.CTkLabel(self, text=title, font=("Consolas", 11), text_color=CLR["text_dim"]).pack(
            anchor="w", padx=14, pady=(12, 0))

        self.val_lbl = ctk.CTkLabel(self, text="0%", font=("Consolas", 26, "bold"),
                                    text_color=accent)
        self.val_lbl.pack(anchor="w", padx=14)

        self.bar = ctk.CTkProgressBar(self, height=6, fg_color=CLR["border"],
                                       progress_color=accent, corner_radius=3)
        self.bar.set(0)
        self.bar.pack(fill="x", padx=14, pady=(4, 12))

    def set_value(self, v: float):
        self._value = max(0.0, min(100.0, v))
        self.val_lbl.configure(text=f"{self._value:.1f}{self.unit}")
        self.bar.set(self._value / 100)


class SectionLabel(ctk.CTkLabel):
    def __init__(self, master, text: str, **kw):
        super().__init__(master, text=text.upper(),
                         font=("Consolas", 10, "bold"),
                         text_color=CLR["text_dim"], **kw)


class ActionButton(ctk.CTkButton):
    def __init__(self, master, **kw):
        kw.setdefault("font", ("Consolas", 12, "bold"))
        kw.setdefault("corner_radius", 8)
        kw.setdefault("fg_color", CLR["accent"])
        kw.setdefault("hover_color", "#1f6feb")
        kw.setdefault("text_color", "#ffffff")
        kw.setdefault("height", 34)
        super().__init__(master, **kw)


#  MODULE: CPU SCHEDULING

class CPUModule(ctk.CTkFrame):
    def __init__(self, master, on_processes_loaded=None, on_cpu_executed=None, mem_module=None, **kw):
        super().__init__(master, fg_color="transparent", **kw)
        self.processes: list[logica.Process] = []
        self.on_processes_loaded = on_processes_loaded
        self.on_cpu_executed = on_cpu_executed  # Callback cuando CPU termina
        self.mem_module = mem_module  # Referencia a MemoryModule para sincronización
        self._pid_colors: dict[str, str] = {}
        
        # Variables de simulación animada
        self._gantt_result: logica.SchedulingResult = None
        self._is_animating = False
        self._animation_speed = 500  # ms entre pasos
        self._current_time = 0
        self._animation_id = None
        
        self._build_ui()

    def _build_ui(self):
        # ── TOP CONTROLS ──
        ctrl = ctk.CTkFrame(self, fg_color=CLR["panel"], corner_radius=10,
                            border_width=1, border_color=CLR["border"])
        ctrl.pack(fill="x", pady=(0, 12))

        ctk.CTkLabel(ctrl, text="Planificación de CPU",
                     font=("Consolas", 16, "bold"), text_color=CLR["text"]).grid(
            row=0, column=0, columnspan=6, sticky="w", padx=16, pady=(12, 4))

        ActionButton(ctrl, text="Cargar CSV/TXT", command=self._load_file,
                     fg_color=CLR["card"], hover_color=CLR["hover"],
                     border_width=1, border_color=CLR["border"]).grid(
            row=1, column=0, padx=(16, 8), pady=12)

        ctk.CTkLabel(ctrl, text="Algoritmo:", font=("Consolas", 12),
                     text_color=CLR["text_dim"]).grid(row=1, column=1, padx=(0, 4))
        self.algo_var = ctk.StringVar(value="FCFS")
        algo_menu = ctk.CTkOptionMenu(ctrl, values=["FCFS", "SPN", "SRT", "Round Robin"],
                                       variable=self.algo_var,
                                       fg_color=CLR["card"], button_color=CLR["accent"],
                                       button_hover_color="#1f6feb",
                                       font=("Consolas", 12), width=160)
        algo_menu.grid(row=1, column=2, padx=4)

        ctk.CTkLabel(ctrl, text="Quantum:", font=("Consolas", 12),
                     text_color=CLR["text_dim"]).grid(row=1, column=3, padx=(12, 4))
        self.quantum_var = ctk.StringVar(value="4")
        ctk.CTkEntry(ctrl, textvariable=self.quantum_var, width=60,
                     font=("Consolas", 12), fg_color=CLR["card"],
                     border_color=CLR["border"]).grid(row=1, column=4, padx=4)

        ActionButton(ctrl, text="▶  Ejecutar", command=self._run).grid(
            row=1, column=5, padx=(12, 8), pady=12)

        # ── ANIMATION CONTROLS ──
        self.play_pause_btn = ActionButton(ctrl, text="⏯  Animar", command=self._toggle_animation,
                                           fg_color=CLR["accent2"], hover_color="#2ea043",
                                           width=100)
        self.play_pause_btn.grid(row=1, column=6, padx=4, pady=12)

        ctk.CTkLabel(ctrl, text="Velocidad:", font=("Consolas", 11),
                     text_color=CLR["text_dim"]).grid(row=1, column=7, padx=(12, 4))
        self.speed_slider = ctk.CTkSlider(ctrl, from_=100, to=1000, number_of_steps=9,
                                          command=self._on_speed_change,
                                          fg_color=CLR["border"], progress_color=CLR["accent"],
                                          width=120)
        self.speed_slider.set(500)
        self.speed_slider.grid(row=1, column=8, padx=4)

        self.time_label = ctk.CTkLabel(ctrl, text="T: 0", font=("Consolas", 11),
                                       text_color=CLR["accent"])
        self.time_label.grid(row=1, column=9, padx=(12, 16))

        ctrl.columnconfigure(9, weight=1)

        # ── PROCESS TABLE INPUT ──
        input_frame = ctk.CTkFrame(self, fg_color=CLR["panel"], corner_radius=10,
                                    border_width=1, border_color=CLR["border"])
        input_frame.pack(fill="x", pady=(0, 12))

        ctk.CTkLabel(input_frame, text="Procesos Cargados",
                     font=("Consolas", 13, "bold"), text_color=CLR["text"]).pack(
            anchor="w", padx=16, pady=(10, 4))

        self.proc_table = self._make_table(
            input_frame, ["PID", "Llegada", "Ráfaga (ms)"], [80, 100, 120])
        self.proc_table.pack(fill="x", padx=16, pady=(0, 12))

        # ── RESULTS TABLE ──
        results_frame = ctk.CTkFrame(self, fg_color=CLR["panel"], corner_radius=10,
                                      border_width=1, border_color=CLR["border"])
        results_frame.pack(fill="x", pady=(0, 12))

        hdr = ctk.CTkFrame(results_frame, fg_color="transparent")
        hdr.pack(fill="x", padx=16, pady=(10, 4))
        ctk.CTkLabel(hdr, text="Resultados", font=("Consolas", 13, "bold"),
                     text_color=CLR["text"]).pack(side="left")
        self.avg_lbl = ctk.CTkLabel(hdr, text="", font=("Consolas", 11),
                                     text_color=CLR["accent2"])
        self.avg_lbl.pack(side="right")

        self.result_table = self._make_table(
            results_frame,
            ["PID", "1er Inicio", "Fin", "Retorno", "Espera"],
            [80, 100, 80, 100, 100]
        )
        self.result_table.pack(fill="x", padx=16, pady=(0, 12))

        # ── GANTT ──
        gantt_frame = ctk.CTkFrame(self, fg_color=CLR["panel"], corner_radius=10,
                                    border_width=1, border_color=CLR["border"])
        gantt_frame.pack(fill="both", expand=True)

        ctk.CTkLabel(gantt_frame, text="Diagrama de Gantt",
                     font=("Consolas", 13, "bold"), text_color=CLR["text"]).pack(
            anchor="w", padx=16, pady=(10, 4))

        self.gantt_canvas_frame = ctk.CTkScrollableFrame(
            gantt_frame, fg_color=CLR["bg"], height=130,
            scrollbar_button_color=CLR["border"],
            scrollbar_button_hover_color=CLR["accent"],
            orientation="horizontal"
        )
        self.gantt_canvas_frame.pack(fill="x", padx=16, pady=(0, 12))

        self.gantt_tk_canvas = tk.Canvas(
            self.gantt_canvas_frame, bg=CLR["bg"], height=120,
            highlightthickness=0
        )
        self.gantt_tk_canvas.pack(fill="x")

    def _make_table(self, parent, columns, widths):
        style = ttk.Style()
        style.theme_use("default")
        style.configure("Dark.Treeview",
                         background=CLR["card"],
                         foreground=CLR["text"],
                         fieldbackground=CLR["card"],
                         bordercolor=CLR["border"],
                         rowheight=28,
                         font=("Consolas", 11))
        style.configure("Dark.Treeview.Heading",
                         background=CLR["panel"],
                         foreground=CLR["text_dim"],
                         font=("Consolas", 10, "bold"),
                         relief="flat")
        style.map("Dark.Treeview", background=[("selected", CLR["accent"])])

        tree = ttk.Treeview(parent, columns=columns, show="headings",
                             style="Dark.Treeview", height=5)
        for col, w in zip(columns, widths):
            tree.heading(col, text=col)
            tree.column(col, width=w, anchor="center")
        return tree

    def _load_file(self):
        path = filedialog.askopenfilename(
            filetypes=[("CSV / TXT", "*.csv *.txt"), ("All", "*.*")])
        if not path:
            return
        try:
            self.processes = logica.load_processes_from_file(path)
            self._refresh_proc_table()
            if self.on_processes_loaded:
                self.on_processes_loaded(self.processes)
            messagebox.showinfo("OK", f"{len(self.processes)} procesos cargados.")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _refresh_proc_table(self):
        self.proc_table.delete(*self.proc_table.get_children())
        for p in self.processes:
            self.proc_table.insert("", "end", values=(p.pid, p.arrival, p.burst))

    def _run(self):
        if not self.processes:
            messagebox.showwarning("Sin datos", "Carga primero un archivo de procesos.")
            return
        algo = self.algo_var.get()
        try:
            if algo == "FCFS":
                result = logica.fcfs(self.processes)
            elif algo == "SPN":
                result = logica.spn(self.processes)
            elif algo == "SRT":
                result = logica.srt(self.processes)
            else:
                q = int(self.quantum_var.get())
                result = logica.round_robin(self.processes, q)
        except Exception as e:
            messagebox.showerror("Error en ejecución", str(e))
            return

        self._assign_colors(result.processes)
        self._populate_results(result)
        self._draw_gantt(result.gantt)
        
        # Guardar resultado para animación
        self._gantt_result = result
        self._current_time = 0
        self._is_animating = False
        self.play_pause_btn.configure(text="⏯  Animar")
        self.time_label.configure(text="T: 0")
        
        # Llamar al callback para ejecutar memoria automáticamente
        if self.on_cpu_executed:
            self.on_cpu_executed(result.processes)

    def _assign_colors(self, procs):
        for i, p in enumerate(procs):
            if p.pid not in self._pid_colors:
                self._pid_colors[p.pid] = PROCESS_COLORS[i % len(PROCESS_COLORS)]

    def _populate_results(self, result: logica.SchedulingResult):
        self.result_table.delete(*self.result_table.get_children())
        for p in result.processes:
            self.result_table.insert("", "end", values=(
                p.pid,
                p.start if p.start is not None else "-",
                p.finish if p.finish is not None else "-",
                p.turnaround if p.turnaround is not None else "-",
                p.waiting if p.waiting is not None else "-",
            ))
        self.avg_lbl.configure(
            text=f"Promedio  |  Retorno: {result.avg_turnaround:.2f}  ·  Espera: {result.avg_waiting:.2f}")

    def _draw_gantt(self, gantt: list[logica.GanttBlock]):
        c = self.gantt_tk_canvas
        c.delete("all")
        if not gantt:
            return

        BH, BY, TICK_W = 60, 20, 28
        total_ticks = max(b.end for b in gantt)
        canvas_width = max(700, total_ticks * TICK_W + 60)
        c.configure(width=canvas_width, height=120)

        # timeline ruler
        for t in range(0, total_ticks + 1, max(1, total_ticks // 20)):
            x = 40 + t * TICK_W
            c.create_line(x, BY + BH, x, BY + BH + 8, fill=CLR["text_dim"])
            c.create_text(x, BY + BH + 16, text=str(t), fill=CLR["text_dim"],
                          font=("Consolas", 8), anchor="n")

        for block in gantt:
            x1 = 40 + block.start * TICK_W
            x2 = 40 + block.end * TICK_W
            color = self._pid_colors.get(block.pid, CLR["accent"])
            c.create_rectangle(x1, BY, x2, BY + BH, fill=color, outline=CLR["bg"], width=2)
            mid = (x1 + x2) / 2
            label = block.pid if (x2 - x1) > 20 else ""
            c.create_text(mid, BY + BH // 2, text=label, fill="#ffffff",
                          font=("Consolas", 10, "bold"))

    def _on_speed_change(self, value):
        """Cambia la velocidad de animación en CPU y Memoria"""
        self._animation_speed = int(float(value))
        # Sincronizar con memoria
        if self.mem_module:
            self.mem_module._animation_speed_mem = int(float(value))

    def _toggle_animation(self):
        """Inicia o pausa la animación del Gantt Y la Memoria en paralelo"""
        if not self._gantt_result:
            messagebox.showwarning("Sin datos", "Ejecuta primero un algoritmo.")
            return
        
        if self._is_animating:
            # Pausar ambas animaciones
            self._is_animating = False
            self.play_pause_btn.configure(text="⏯  Reanudar")
            if self._animation_id:
                self.after_cancel(self._animation_id)
                self._animation_id = None
            # Pausar memoria
            if self.mem_module:
                self.mem_module._is_animating_mem = False
                self.mem_module.mem_play_pause_btn.configure(text="⏯  Reanudar")
                if self.mem_module._animation_id_mem:
                    self.mem_module.after_cancel(self.mem_module._animation_id_mem)
                    self.mem_module._animation_id_mem = None
        else:
            # Play ambas animaciones
            self._is_animating = True
            self.play_pause_btn.configure(text="⏸  Pausar")
            if self.mem_module:
                self.mem_module._is_animating_mem = True
                self.mem_module.mem_play_pause_btn.configure(text="⏸  Pausar")
            self._animate_gantt_step()

    def _animate_gantt_step(self):
        """Anima el Gantt paso a paso"""
        if not self._is_animating:
            return
        
        gantt = self._gantt_result.gantt
        if not gantt:
            return
        
        max_time = max(b.end for b in gantt)
        
        # Dibujar Gantt hasta el tiempo actual
        c = self.gantt_tk_canvas
        c.delete("all")
        
        BH, BY, TICK_W = 60, 20, 28
        canvas_width = max(700, max_time * TICK_W + 60)
        c.configure(width=canvas_width, height=120)
        
        # Timeline ruler
        for t in range(0, max_time + 1, max(1, max_time // 20)):
            x = 40 + t * TICK_W
            c.create_line(x, BY + BH, x, BY + BH + 8, fill=CLR["text_dim"])
            c.create_text(x, BY + BH + 16, text=str(t), fill=CLR["text_dim"],
                          font=("Consolas", 8), anchor="n")
        
        # Línea vertical de tiempo actual
        x_current = 40 + self._current_time * TICK_W
        c.create_line(x_current, BY, x_current, BY + BH + 5, fill=CLR["accent3"], width=3)
        
        # Dibujar bloques hasta el tiempo actual
        for block in gantt:
            if block.start > self._current_time:
                continue  # Aún no han llegado
            
            x1 = 40 + block.start * TICK_W
            x2 = 40 + min(block.end, self._current_time + 1) * TICK_W
            color = self._pid_colors.get(block.pid, CLR["accent"])
            c.create_rectangle(x1, BY, x2, BY + BH, fill=color, outline=CLR["bg"], width=2)
            mid = (x1 + x2) / 2
            label = block.pid if (x2 - x1) > 20 else ""
            c.create_text(mid, BY + BH // 2, text=label, fill="#ffffff",
                          font=("Consolas", 10, "bold"))
        
        # Actualizar tiempo
        self.time_label.configure(text=f"T: {self._current_time}")
        
        # Sincronizar animación de memoria en paralelo
        if self.mem_module and self.mem_module._is_animating_mem:
            self.mem_module._step_memory_animation()
        
        # Siguiente paso
        self._current_time += 1
        if self._current_time > max_time:
            self._current_time = 0
        
        self._animation_id = self.after(self._animation_speed, self._animate_gantt_step)

    def get_processes(self) -> list[logica.Process]:
        return self.processes


#  MODULE: MEMORY MANAGEMENT

class MemoryModule(ctk.CTkFrame):
    def __init__(self, master, **kw):
        super().__init__(master, fg_color="transparent", **kw)
        self._blocks: list[logica.MemoryBlock] = []
        self._fixed_partitions: list[logica.FixedPartitionInfo] = []
        self._total_kb = 512
        self._cpu_processes: list[logica.Process] = []
        self._is_fixed_partition = False
        
        # Variables de simulación animada
        self._is_animating_mem = False
        self._animation_speed_mem = 500  # ms entre pasos
        self._all_process_list: list[tuple[str, int]] = []
        self._assigned_processes: list[tuple[str, int]] = []
        self._animation_id_mem = None
        
        self._build_ui()

    def _build_ui(self):
        # ── CONTROLS ──
        ctrl = ctk.CTkFrame(self, fg_color=CLR["panel"], corner_radius=10,
                            border_width=1, border_color=CLR["border"])
        ctrl.pack(fill="x", pady=(0, 12))

        ctk.CTkLabel(ctrl, text="Gestión de Memoria Principal",
                     font=("Consolas", 16, "bold"), text_color=CLR["text"]).grid(
            row=0, column=0, columnspan=8, sticky="w", padx=16, pady=(12, 4))

        ctk.CTkLabel(ctrl, text="RAM Total (KB):", font=("Consolas", 12),
                     text_color=CLR["text_dim"]).grid(row=1, column=0, padx=(16, 4), pady=12)
        self.ram_var = ctk.StringVar(value="512")
        ctk.CTkEntry(ctrl, textvariable=self.ram_var, width=80,
                     font=("Consolas", 12), fg_color=CLR["card"],
                     border_color=CLR["border"]).grid(row=1, column=1, padx=4)

        ctk.CTkLabel(ctrl, text="Algoritmo:", font=("Consolas", 12),
                     text_color=CLR["text_dim"]).grid(row=1, column=2, padx=(12, 4))
        self.mem_algo = ctk.StringVar(value="First Fit")
        self.algo_menu = ctk.CTkOptionMenu(ctrl, values=["First Fit", "Best Fit", "Worst Fit", "Buddy System"],
                           variable=self.mem_algo,
                           fg_color=CLR["card"], button_color=CLR["accent"],
                           button_hover_color="#1f6feb",
                           font=("Consolas", 12), width=160)
        self.algo_menu.grid(row=1, column=3, padx=4)

        ctk.CTkLabel(ctrl, text="Procesos (manual):", font=("Consolas", 12),
                     text_color=CLR["text_dim"]).grid(row=1, column=4, padx=(12, 4))
        self.manual_var = ctk.StringVar(value="EJM: P0:23, P1:35")
        ctk.CTkEntry(ctrl, textvariable=self.manual_var, width=200,
                     font=("Consolas", 11), fg_color=CLR["card"],
                     border_color=CLR["border"],
                     placeholder_text="P1:50, P2:120 o usar CPU").grid(row=1, column=5, padx=4)

        ActionButton(ctrl, text="Desde CPU", command=self._use_cpu_procs,
                     fg_color=CLR["card"], hover_color=CLR["hover"],
                     border_width=1, border_color=CLR["border"],
                     width=110).grid(row=1, column=6, padx=4)

        ActionButton(ctrl, text="▶  Asignar", command=self._run).grid(
            row=1, column=7, padx=(8, 16), pady=12)

        # ── FIXED PARTITIONS SECTION ──
        ctk.CTkLabel(ctrl, text="Tipo de Gestión:", font=("Consolas", 12),
                     text_color=CLR["text_dim"]).grid(row=2, column=0, padx=(16, 4), pady=12)
        self.mem_type = ctk.StringVar(value="Dinámica")
        self.type_menu = ctk.CTkOptionMenu(ctrl, values=["Dinámica", "Fija - Igual", "Fija - Desigual"],
                          variable=self.mem_type, command=self._on_type_change,
                          fg_color=CLR["card"], button_color=CLR["accent"],
                          button_hover_color="#1f6feb",
                          font=("Consolas", 12), width=140)
        self.type_menu.grid(row=2, column=1, padx=4)

        ctk.CTkLabel(ctrl, text="Config. Particiones:", font=("Consolas", 12),
                     text_color=CLR["text_dim"]).grid(row=2, column=2, padx=(12, 4))
        self.partition_config_var = ctk.StringVar(value="4")
        self.partition_config_entry = ctk.CTkEntry(
            ctrl, textvariable=self.partition_config_var, width=150,
            font=("Consolas", 11), fg_color=CLR["card"],
            border_color=CLR["border"],
            placeholder_text="Num particiones o tamaños: 100,200,150"
        )
        self.partition_config_entry.grid(row=2, column=3, padx=4)

        ctk.CTkLabel(ctrl, text="Algoritmo Fijo:", font=("Consolas", 12),
                     text_color=CLR["text_dim"]).grid(row=2, column=4, padx=(12, 4))
        self.fixed_algo = ctk.StringVar(value="First Fit")
        self.fixed_algo_menu = ctk.CTkOptionMenu(
            ctrl, values=["First Fit", "Best Fit", "Worst Fit"],
            variable=self.fixed_algo,
            fg_color=CLR["card"], button_color=CLR["accent"],
            button_hover_color="#1f6feb",
            font=("Consolas", 12), width=140
        )
        self.fixed_algo_menu.grid(row=2, column=5, padx=4)

        # ── MEMORY ANIMATION CONTROLS ──
        self.mem_play_pause_btn = ActionButton(ctrl, text="⏯  Animar", command=self._toggle_animation_mem,
                                               fg_color=CLR["accent2"], hover_color="#2ea043",
                                               width=100)
        self.mem_play_pause_btn.grid(row=2, column=6, padx=4, pady=12)

        ctk.CTkLabel(ctrl, text="Velocidad:", font=("Consolas", 11),
                     text_color=CLR["text_dim"]).grid(row=2, column=7, padx=(12, 4))
        self.mem_speed_slider = ctk.CTkSlider(ctrl, from_=100, to=1000, number_of_steps=9,
                                              command=self._on_speed_change_mem,
                                              fg_color=CLR["border"], progress_color=CLR["accent"],
                                              width=120)
        self.mem_speed_slider.set(500)
        self.mem_speed_slider.grid(row=2, column=8, padx=4)

        self.mem_progress_label = ctk.CTkLabel(ctrl, text="Procesos: 0/?", font=("Consolas", 11),
                                               text_color=CLR["accent"])
        self.mem_progress_label.grid(row=2, column=9, padx=(12, 16))

        # ── MEMORY MAP ──
        map_frame = ctk.CTkFrame(self, fg_color=CLR["panel"], corner_radius=10,
                                  border_width=1, border_color=CLR["border"])
        map_frame.pack(fill="x", pady=(0, 12))

        hdr = ctk.CTkFrame(map_frame, fg_color="transparent")
        hdr.pack(fill="x", padx=16, pady=(10, 4))
        ctk.CTkLabel(hdr, text="Mapa de Memoria",
                     font=("Consolas", 13, "bold"), text_color=CLR["text"]).pack(side="left")
        self.mem_pct_lbl = ctk.CTkLabel(hdr, text="", font=("Consolas", 11),
                                         text_color=CLR["accent3"])
        self.mem_pct_lbl.pack(side="right")

        self.map_canvas = tk.Canvas(map_frame, bg=CLR["bg"], height=80,
                                     highlightthickness=0)
        self.map_canvas.pack(fill="x", padx=16, pady=(0, 12))
        self.map_canvas.bind("<Configure>", lambda e: self._redraw_map())

        # ── BLOCKS DETAIL TABLE ──
        detail_frame = ctk.CTkFrame(self, fg_color=CLR["panel"], corner_radius=10,
                                     border_width=1, border_color=CLR["border"])
        detail_frame.pack(fill="both", expand=True)

        ctk.CTkLabel(detail_frame, text="Detalle de Bloques",
                     font=("Consolas", 13, "bold"), text_color=CLR["text"]).pack(
            anchor="w", padx=16, pady=(10, 4))

        style = ttk.Style()
        self.detail_table = ttk.Treeview(
            detail_frame,
            columns=["Nombre", "Dirección", "Tamaño", "Estado"],
            show="headings", style="Dark.Treeview", height=12
        )
        for col, w in zip(["Nombre", "Dirección", "Tamaño", "Estado"],
                           [120, 140, 120, 120]):
            self.detail_table.heading(col, text=col)
            self.detail_table.column(col, width=w, anchor="center")
        self.detail_table.pack(fill="both", expand=True, padx=16, pady=(0, 12))

        # ── LOG ──
        log_frame = ctk.CTkFrame(self, fg_color=CLR["panel"], corner_radius=10,
                                  border_width=1, border_color=CLR["border"])
        log_frame.pack(fill="x", pady=(0, 0))
        ctk.CTkLabel(log_frame, text="Log de Asignación",
                     font=("Consolas", 12, "bold"), text_color=CLR["text"]).pack(
            anchor="w", padx=16, pady=(8, 2))
        self.log_text = ctk.CTkTextbox(log_frame, height=80, font=("Consolas", 11),
                                        fg_color=CLR["bg"], text_color=CLR["accent2"],
                                        border_color=CLR["border"])
        self.log_text.pack(fill="x", padx=16, pady=(0, 10))

        # Inicializar estado de controles
        self._on_type_change("Dinámica")

    def _use_cpu_procs(self):
        if not self._cpu_processes:
            messagebox.showinfo("Info", "Carga y ejecuta primero el módulo de CPU.")
            return
        text = ", ".join(f"{p.pid}:{p.burst}" for p in self._cpu_processes)
        self.manual_var.set(text)

    def set_cpu_processes(self, procs: list[logica.Process]):
        self._cpu_processes = procs

    def execute_cpu_processes(self, cpu_processes: list[logica.Process]):
        """Ejecuta automáticamente la asignación de memoria con procesos de CPU"""
        if not cpu_processes:
            return
        
        # Convertir procesos de CPU (que tienen burst) a tuplas (pid, tamaño_en_kb)
        # Usamos el burst como aproximación al tamaño en KB
        proc_list = [(p.pid, p.burst) for p in cpu_processes]
        
        try:
            total_kb = int(self.ram_var.get())
        except ValueError:
            total_kb = 512
        
        self._total_kb = total_kb
        self._all_process_list = list(proc_list)
        self._assigned_processes = []
        
        mem_type = self.mem_type.get()
        
        try:
            if mem_type == "Dinámica":
                self._is_fixed_partition = False
                algo = self.mem_algo.get()
                if algo == "First Fit":
                    blocks, log = logica.first_fit(total_kb, proc_list)
                elif algo == "Best Fit":
                    blocks, log = logica.best_fit(total_kb, proc_list)
                elif algo == "Worst Fit":
                    blocks, log = logica.worst_fit(total_kb, proc_list)
                else:
                    blocks, log = logica.buddy_system(total_kb, proc_list)
                self._blocks = blocks
                self._populate_detail(blocks, total_kb)
                pct = logica.memory_usage_percent(blocks, total_kb)
            else:
                self._is_fixed_partition = True
                config = self.partition_config_var.get()
                algo = self.fixed_algo.get()
                
                try:
                    if mem_type == "Fija - Igual":
                        num_parts = int(config)
                        partitions = logica._build_fixed_partitions_equal(total_kb, num_parts)
                    else:
                        partitions = logica._build_fixed_partitions_unequal(total_kb, config)
                except ValueError as ve:
                    messagebox.showerror("Error en Particiones", str(ve))
                    return
                
                if algo == "First Fit":
                    partitions, log = logica.first_fit_fixed(total_kb, partitions, proc_list)
                elif algo == "Best Fit":
                    partitions, log = logica.best_fit_fixed(total_kb, partitions, proc_list)
                else:
                    partitions, log = logica.worst_fit_fixed(total_kb, partitions, proc_list)
                
                self._fixed_partitions = partitions
                self._populate_detail_fixed(partitions, total_kb)
                pct = logica.memory_usage_percent_fixed(partitions, total_kb)
                total_frag = logica.total_internal_fragmentation(partitions)
                log.append(f"\n--- FRAGMENTACIÓN INTERNA TOTAL: {total_frag}KB ---")
                
        except Exception as e:
            messagebox.showerror("Error", str(e))
            return

        self._redraw_map()
        self._update_log(log)
        self.mem_pct_lbl.configure(text=f"Uso: {pct:.1f}%")
        
        # Preparar para animación
        self._is_animating_mem = False
        self.mem_play_pause_btn.configure(text="⏯  Animar")
        total = len(self._all_process_list)
        self.mem_progress_label.configure(text=f"Procesos: 0/{total}")

    def _on_type_change(self, value):
        """Actualiza controles según tipo de gestión seleccionado"""
        if value == "Dinámica":
            self.partition_config_entry.configure(state="disabled")
            self.fixed_algo_menu.configure(state="disabled")
            self.algo_menu.configure(state="normal")
        else:
            self.partition_config_entry.configure(state="normal")
            self.fixed_algo_menu.configure(state="normal")
            self.algo_menu.configure(state="disabled")
            if value == "Fija - Igual":
                self.partition_config_entry.delete(0, "end")
                self.partition_config_entry.insert(0, "4")
            else:
                self.partition_config_entry.delete(0, "end")
                self.partition_config_entry.insert(0, "128,128,128,128")

    def _run(self):
        try:
            total_kb = int(self.ram_var.get())
        except ValueError:
            messagebox.showerror("Error", "RAM inválida.")
            return

        self._total_kb = total_kb
        proc_text = self.manual_var.get()
        proc_list = logica.parse_manual_processes(proc_text)
        if not proc_list:
            messagebox.showwarning("Sin procesos", "Ingresa procesos manualmente o usa los de CPU.")
            return

        mem_type = self.mem_type.get()
        
        try:
            if mem_type == "Dinámica":
                self._is_fixed_partition = False
                algo = self.mem_algo.get()
                if algo == "First Fit":
                    blocks, log = logica.first_fit(total_kb, proc_list)
                elif algo == "Best Fit":
                    blocks, log = logica.best_fit(total_kb, proc_list)
                elif algo == "Worst Fit":
                    blocks, log = logica.worst_fit(total_kb, proc_list)
                else:
                    blocks, log = logica.buddy_system(total_kb, proc_list)
                self._blocks = blocks
                self._populate_detail(blocks, total_kb)
                pct = logica.memory_usage_percent(blocks, total_kb)
            else:
                self._is_fixed_partition = True
                config = self.partition_config_var.get()
                algo = self.fixed_algo.get()
                
                try:
                    if mem_type == "Fija - Igual":
                        num_parts = int(config)
                        partitions = logica._build_fixed_partitions_equal(total_kb, num_parts)
                    else:
                        partitions = logica._build_fixed_partitions_unequal(total_kb, config)
                except ValueError as ve:
                    messagebox.showerror("Error en Particiones", str(ve))
                    return
                
                if algo == "First Fit":
                    partitions, log = logica.first_fit_fixed(total_kb, partitions, proc_list)
                elif algo == "Best Fit":
                    partitions, log = logica.best_fit_fixed(total_kb, partitions, proc_list)
                else:
                    partitions, log = logica.worst_fit_fixed(total_kb, partitions, proc_list)
                
                self._fixed_partitions = partitions
                self._populate_detail_fixed(partitions, total_kb)
                pct = logica.memory_usage_percent_fixed(partitions, total_kb)
                total_frag = logica.total_internal_fragmentation(partitions)
                log.append(f"\n--- FRAGMENTACIÓN INTERNA TOTAL: {total_frag}KB ---")
                
        except Exception as e:
            messagebox.showerror("Error", str(e))
            return

        self._redraw_map()
        self._update_log(log)
        self.mem_pct_lbl.configure(text=f"Uso: {pct:.1f}%")
        
        # Preparar para animación
        self._all_process_list = list(proc_list)
        self._assigned_processes = []
        self._is_animating_mem = False
        self.mem_play_pause_btn.configure(text="⏯  Animar")
        total = len(self._all_process_list)
        self.mem_progress_label.configure(text=f"Procesos: 0/{total}")
        
        return pct

    def _populate_detail(self, blocks: list[logica.MemoryBlock], total_kb: int):
        self.detail_table.delete(*self.detail_table.get_children())
        for b in blocks:
            estado = "Libre" if b.is_free else "Ocupado"
            self.detail_table.insert("", "end", values=(
                b.name, f"{b.address} KB", f"{b.size} KB", estado))

    def _populate_detail_fixed(self, partitions: list[logica.FixedPartitionInfo], total_kb: int):
        """Muestra detalles de particiones fijas con fragmentación interna"""
        self.detail_table.delete(*self.detail_table.get_children())
        # Actualizar columnas si es necesario
        for col in self.detail_table["columns"]:
            self.detail_table.heading(col, text=col)
        
        for part in partitions:
            if part.partition_id == 0:
                estado = "Sistema"
                fragmentation = "N/A"
            elif part.assigned_pid is None:
                estado = "Libre"
                fragmentation = "N/A"
            else:
                estado = "Ocupado"
                fragmentation = f"{part.internal_fragmentation}KB"
            
            self.detail_table.insert("", "end", values=(
                f"P#{part.partition_id}", 
                f"{part.assigned_pid or 'Libre'}", 
                f"{part.size}KB", 
                fragmentation if fragmentation != "N/A" else estado
            ))

    def _redraw_map(self):
        c = self.map_canvas
        c.delete("all")
        
        if self._is_fixed_partition:
            self._redraw_map_fixed()
        else:
            self._redraw_map_dynamic()

    def _redraw_map_dynamic(self):
        """Dibuja el mapa de memoria para particiones dinámicas"""
        c = self.map_canvas
        if not self._blocks:
            return
        w = c.winfo_width() or 700
        h = 70
        total = self._total_kb or 512
        pid_color_map = {}
        ci = 0
        for b in self._blocks:
            if not b.is_free and b.name not in pid_color_map:
                if b.name == "S.O.":
                    pid_color_map[b.name] = CLR["accent3"]
                else:
                    pid_color_map[b.name] = PROCESS_COLORS[ci % len(PROCESS_COLORS)]
                    ci += 1

        x = 0
        for b in self._blocks:
            bw = int((b.size / total) * w)
            if bw < 2:
                bw = 2
            color = CLR["border"] if b.is_free else pid_color_map.get(b.name, CLR["accent"])
            c.create_rectangle(x, 10, x + bw, h, fill=color, outline=CLR["bg"], width=1)
            label_text = f"{b.name}\n{b.size}KB"
            if bw > 35:
                c.create_text(x + bw // 2, h // 2 + 5, text=label_text,
                              fill="#ffffff" if not b.is_free else CLR["text_dim"],
                              font=("Consolas", 8), justify="center")
            x += bw

    def _redraw_map_fixed(self):
        """Dibuja el mapa de memoria para particiones fijas"""
        c = self.map_canvas
        if not self._fixed_partitions:
            return
        w = c.winfo_width() or 700
        h = 70
        total = self._total_kb or 512
        pid_color_map = {}
        ci = 0
        
        # Crear mapa de colores
        for part in self._fixed_partitions:
            if part.assigned_pid and part.assigned_pid not in pid_color_map:
                if part.assigned_pid == "S.O.":
                    pid_color_map[part.assigned_pid] = CLR["accent3"]
                else:
                    pid_color_map[part.assigned_pid] = PROCESS_COLORS[ci % len(PROCESS_COLORS)]
                    ci += 1

        x = 0
        for part in self._fixed_partitions:
            bw = int((part.size / total) * w)
            if bw < 2:
                bw = 2
            
            if part.assigned_pid is None:
                color = CLR["border"]
                label_text = f"Libre\n{part.size}KB"
            else:
                color = pid_color_map.get(part.assigned_pid, CLR["accent"])
                frag_text = f"[F:{part.internal_fragmentation}]" if part.internal_fragmentation > 0 else ""
                label_text = f"{part.assigned_pid}\n{part.allocated_size}KB {frag_text}"
            
            # Dibuja el rectángulo de la partición con borde visible
            c.create_rectangle(x, 10, x + bw, h, fill=color, outline=CLR["accent"], width=2)
            
            if bw > 40:
                c.create_text(x + bw // 2, h // 2 + 5, text=label_text,
                              fill="#ffffff" if part.assigned_pid else CLR["text_dim"],
                              font=("Consolas", 8), justify="center")
            x += bw

    def _update_log(self, log: list[str]):
        self.log_text.delete("1.0", "end")
        self.log_text.insert("end", "\n".join(log))

    def _on_speed_change_mem(self, value):
        """Cambia la velocidad de animación de memoria"""
        self._animation_speed_mem = int(float(value))

    def _toggle_animation_mem(self):
        """Inicia o pausa la animación de asignación de memoria"""
        if not self._all_process_list:
            messagebox.showwarning("Sin datos", "Ejecuta primero una asignación de memoria.")
            return
        
        if self._is_animating_mem:
            # Pausar
            self._is_animating_mem = False
            self.mem_play_pause_btn.configure(text="⏯  Reanudar")
            if self._animation_id_mem:
                self.after_cancel(self._animation_id_mem)
                self._animation_id_mem = None
        else:
            # Play
            self._is_animating_mem = True
            self.mem_play_pause_btn.configure(text="⏸  Pausar")
            self._animate_memory_step()

    def _step_memory_animation(self):
        """Un paso de animación de memoria (sincronizado desde CPU)"""
        if not self._is_animating_mem:
            return
        
        if len(self._assigned_processes) < len(self._all_process_list):
            # Agregar el siguiente proceso
            self._assigned_processes.append(self._all_process_list[len(self._assigned_processes)])
            
            # Redibujar memoria y tabla
            if self._is_fixed_partition:
                self._redraw_memory_fixed_animated()
            else:
                self._redraw_memory_dynamic_animated()
            
            # Actualizar etiqueta de progreso
            total = len(self._all_process_list)
            assigned = len(self._assigned_processes)
            self.mem_progress_label.configure(text=f"Procesos: {assigned}/{total}")
        else:
            # Simulación completa
            self._is_animating_mem = False
            self.mem_play_pause_btn.configure(text="⏯  Reanudar")

    def _animate_memory_step(self):
        """Anima la asignación de memoria paso a paso (modo independiente)"""
        if not self._is_animating_mem:
            return
        
        # Ejecutar un paso
        self._step_memory_animation()
        
        # Si aún hay procesos, continuar
        if len(self._assigned_processes) < len(self._all_process_list) and self._is_animating_mem:
            self._animation_id_mem = self.after(self._animation_speed_mem, self._animate_memory_step)
        else:
            # Simulación completa
            if len(self._assigned_processes) >= len(self._all_process_list):
                self._is_animating_mem = False
                self.mem_play_pause_btn.configure(text="⏯  Reanudar")

    def _redraw_memory_fixed_animated(self):
        """Redibuja particiones fijas con procesos asignados animadamente"""
        # Recalcular con procesos asignados hasta ahora
        config = self.partition_config_var.get()
        algo = self.fixed_algo.get()
        
        try:
            mem_type = self.mem_type.get()
            if mem_type == "Fija - Igual":
                num_parts = int(config)
                partitions = logica._build_fixed_partitions_equal(self._total_kb, num_parts)
            else:
                partitions = logica._build_fixed_partitions_unequal(self._total_kb, config)
        except ValueError:
            return
        
        # Asignar procesos animados
        if algo == "First Fit":
            partitions, _ = logica.first_fit_fixed(self._total_kb, partitions, self._assigned_processes)
        elif algo == "Best Fit":
            partitions, _ = logica.best_fit_fixed(self._total_kb, partitions, self._assigned_processes)
        else:
            partitions, _ = logica.worst_fit_fixed(self._total_kb, partitions, self._assigned_processes)
        
        self._fixed_partitions = partitions
        self._populate_detail_fixed(partitions, self._total_kb)
        self._redraw_map()

    def _redraw_memory_dynamic_animated(self):
        """Redibuja particiones dinámicas con procesos asignados animadamente"""
        algo = self.mem_algo.get()
        try:
            if algo == "First Fit":
                blocks, _ = logica.first_fit(self._total_kb, self._assigned_processes)
            elif algo == "Best Fit":
                blocks, _ = logica.best_fit(self._total_kb, self._assigned_processes)
            elif algo == "Worst Fit":
                blocks, _ = logica.worst_fit(self._total_kb, self._assigned_processes)
            else:
                blocks, _ = logica.buddy_system(self._total_kb, self._assigned_processes)
        except Exception:
            return
        
        self._blocks = blocks
        self._populate_detail(blocks, self._total_kb)
        self._redraw_map()

    def get_memory_percent(self) -> float:
        if self._is_fixed_partition:
            if not self._fixed_partitions or not self._total_kb:
                return 0.0
            return logica.memory_usage_percent_fixed(self._fixed_partitions, self._total_kb)
        else:
            if not self._blocks or not self._total_kb:
                return 0.0
            return logica.memory_usage_percent(self._blocks, self._total_kb)

#  MAIN APPLICATION WINDOW

class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("SIMULADOR DE PROCESOS Y MEMORIA")
        self.geometry("1280x820")
        self.minsize(900, 600)
        self.configure(fg_color=CLR["bg"])
        self._sim_running = True
        self._build_layout()
        self._start_metrics_loop()

    def _build_layout(self):
        # ── TOP BAR ──
        top = ctk.CTkFrame(self, fg_color=CLR["panel"], corner_radius=0,
                           border_width=0, height=50)
        top.pack(fill="x", side="top")
        top.pack_propagate(False)
        ctk.CTkLabel(top, text="SISTEMAS OPERATIVOS - 2026",
                     font=("Consolas", 15, "bold"), text_color=CLR["accent"]).pack(
            side="left", padx=20)
        ctk.CTkLabel(top, text="Jhon Deyvis Romario Mamani Machaca - 236754",
                     font=("Consolas", 11), text_color=CLR["text_dim"]).pack(
            side="left", padx=8)
        self.clock_lbl = ctk.CTkLabel(top, text="", font=("Consolas", 11),
                                       text_color=CLR["text_dim"])
        self.clock_lbl.pack(side="right", padx=20)

        # ── METRICS BAR ──
        metrics_bar = ctk.CTkFrame(self, fg_color="transparent", height=95)
        metrics_bar.pack(fill="x", padx=16, pady=(10, 0))
        metrics_bar.pack_propagate(False)

        self.cpu_card  = MetricCard(metrics_bar, "CPU",  accent=CLR["accent"])
        self.mem_card  = MetricCard(metrics_bar, "MEMORIA", accent=CLR["accent3"])
        self.disk_card = MetricCard(metrics_bar, "DISCO", accent=CLR["accent5"])
        self.net_card  = MetricCard(metrics_bar, "RED",  accent=CLR["accent4"])
        for card in [self.cpu_card, self.mem_card, self.disk_card, self.net_card]:
            card.pack(side="left", fill="both", expand=True, padx=6)

        # ── BODY: SIDEBAR + CONTENT ──
        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=16, pady=10)

        # Sidebar
        sidebar = ctk.CTkFrame(body, fg_color=CLR["panel"], width=190,
                                corner_radius=10, border_width=1,
                                border_color=CLR["border"])
        sidebar.pack(side="left", fill="y", padx=(0, 10))
        sidebar.pack_propagate(False)

        ctk.CTkLabel(sidebar, text="MÓDULOS", font=("Consolas", 10, "bold"),
                     text_color=CLR["text_dim"]).pack(anchor="w", padx=16, pady=(16, 6))

        self._active_btn = None
        self.cpu_btn = self._sidebar_btn(sidebar, "Planificación CPU", 0)
        self.mem_btn = self._sidebar_btn(sidebar, "Gestión Memoria", 1)

        ctk.CTkFrame(sidebar, fg_color=CLR["border"], height=1).pack(
            fill="x", padx=16, pady=12)
        ctk.CTkLabel(sidebar, text="SISTEMA", font=("Consolas", 10, "bold"),
                     text_color=CLR["text_dim"]).pack(anchor="w", padx=16, pady=(0, 6))
        ctk.CTkLabel(sidebar, text="Python 3.x", font=("Consolas", 11),
                     text_color=CLR["text_dim"]).pack(anchor="w", padx=16)
        ctk.CTkLabel(sidebar, text="CustomTkinter", font=("Consolas", 11),
                     text_color=CLR["text_dim"]).pack(anchor="w", padx=16)

        # Content area
        self.content = ctk.CTkScrollableFrame(body, fg_color="transparent",
                                               scrollbar_button_color=CLR["border"],
                                               scrollbar_button_hover_color=CLR["accent"])
        self.content.pack(side="left", fill="both", expand=True)

        # Modules - crear Memory primero para usarla como callback
        self.mem_module = MemoryModule(self.content)
        
        self.cpu_module = CPUModule(self.content,
                                     on_processes_loaded=self._on_cpu_procs_loaded,
                                     on_cpu_executed=self.mem_module.execute_cpu_processes,
                                     mem_module=self.mem_module)

        self._show_module(0)

    def _sidebar_btn(self, parent, text: str, idx: int) -> ctk.CTkButton:
        btn = ctk.CTkButton(
            parent, text=text, anchor="w",
            font=("Consolas", 12), height=40,
            fg_color="transparent", hover_color=CLR["hover"],
            text_color=CLR["text"],
            corner_radius=8,
            command=lambda i=idx: self._show_module(i)
        )
        btn.pack(fill="x", padx=10, pady=2)
        return btn

    def _show_module(self, idx: int):
        self.cpu_module.pack_forget()
        self.mem_module.pack_forget()

        btn_map = {0: self.cpu_btn, 1: self.mem_btn}
        if self._active_btn:
            self._active_btn.configure(fg_color="transparent", text_color=CLR["text"])
        self._active_btn = btn_map[idx]
        self._active_btn.configure(fg_color=CLR["accent"], text_color="#ffffff")

        if idx == 0:
            self.cpu_module.pack(fill="both", expand=True)
        else:
            self.mem_module.pack(fill="both", expand=True)

    def _on_cpu_procs_loaded(self, procs):
        self.mem_module.set_cpu_processes(procs)

    def _start_metrics_loop(self):
        self._sim_vals = {"cpu": 20.0, "disk": 15.0, "net": 5.0}

        def _loop():
            while self._sim_running:
                self._sim_vals["cpu"]  += random.uniform(-5, 5)
                self._sim_vals["disk"] += random.uniform(-2, 3)
                self._sim_vals["net"]  += random.uniform(-3, 4)
                for k in self._sim_vals:
                    self._sim_vals[k] = max(3.0, min(97.0, self._sim_vals[k]))

                mem_pct = self.mem_module.get_memory_percent()

                try:
                    import datetime
                    now = datetime.datetime.now().strftime("%Y-%m-%d  %H:%M:%S")
                    self.after(0, lambda: self.clock_lbl.configure(text=now))
                    self.after(0, lambda v=self._sim_vals["cpu"]: self.cpu_card.set_value(v))
                    self.after(0, lambda v=mem_pct: self.mem_card.set_value(v))
                    self.after(0, lambda v=self._sim_vals["disk"]: self.disk_card.set_value(v))
                    self.after(0, lambda v=self._sim_vals["net"]: self.net_card.set_value(v))
                except Exception:
                    pass
                time.sleep(1.5)

        t = threading.Thread(target=_loop, daemon=True)
        t.start()

    def on_closing(self):
        self._sim_running = False
        self.destroy()


#  ENTRY POINT

if __name__ == "__main__":
    app = App()
    app.protocol("WM_DELETE_WINDOW", app.on_closing)
    app.mainloop()
