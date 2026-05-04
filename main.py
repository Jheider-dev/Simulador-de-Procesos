import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import logica

class SimuladorOS:
    def __init__(self, root):
        self.root = root
        self.root.title("Simulador de Planificación de CPU")
        self.root.geometry("850x650")
        
        self.ruta_archivo = ""
        self.procesos = []
        self.historial_gantt = []
        
        self.crear_interfaz()

    def crear_interfaz(self):
        frame_controles = tk.Frame(self.root, pady=10)
        frame_controles.pack(fill="x")

        btn_cargar = tk.Button(frame_controles, text="Cargar CSV/TXT", command=self.cargar_archivo)
        btn_cargar.pack(side="left", padx=10)

        self.lbl_archivo = tk.Label(frame_controles, text="Ningún archivo seleccionado", fg="gray")
        self.lbl_archivo.pack(side="left", padx=10)

        tk.Label(frame_controles, text="Algoritmo:").pack(side="left", padx=(10, 2))
        self.combo_algoritmo = ttk.Combobox(frame_controles, values=["FCFS", "SPN", "SRT", "Round Robin"], state="readonly", width=12)
        self.combo_algoritmo.current(0)
        self.combo_algoritmo.pack(side="left", padx=5)
        self.combo_algoritmo.bind("<<ComboboxSelected>>", self.toggle_quantum)

        tk.Label(frame_controles, text="Quantum (Q):").pack(side="left", padx=(10, 2))
        self.entry_quantum = tk.Entry(frame_controles, width=5, state="disabled")
        self.entry_quantum.pack(side="left")

        btn_ejecutar = tk.Button(frame_controles, text="Ejecutar Simulación", bg="lightblue", command=self.ejecutar_simulacion)
        btn_ejecutar.pack(side="left", padx=20)

        frame_tabla = tk.Frame(self.root, pady=10)
        frame_tabla.pack(fill="both", expand=True)

        columnas = ("PID", "Llegada", "Ráfaga", "1er Inicio", "Fin Total", "T. Retorno", "T. Espera")
        self.tree = ttk.Treeview(frame_tabla, columns=columnas, show="headings", height=8)
        
        for col in columnas:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=100, anchor="center")
        
        self.tree.pack(fill="both", expand=True, padx=10)
        
        self.lbl_promedios = tk.Label(self.root, text="", font=("Arial", 11, "bold"), fg="#333333")
        self.lbl_promedios.pack(pady=5)

        tk.Label(self.root, text="Diagrama de Gantt:", font=("Arial", 11, "bold")).pack(anchor="w", padx=10)
        self.canvas = tk.Canvas(self.root, bg="white", height=150)
        self.canvas.pack(fill="x", padx=10, pady=(0, 20))

    def toggle_quantum(self, event=None):
        if self.combo_algoritmo.get() == "Round Robin":
            self.entry_quantum.config(state="normal")
        else:
            self.entry_quantum.delete(0, tk.END)
            self.entry_quantum.config(state="disabled")

    def cargar_archivo(self):
        self.ruta_archivo = filedialog.askopenfilename(filetypes=[("Archivos Soportados", "*.csv *.txt"), ("Todos los archivos", "*.*")])
        if self.ruta_archivo:
            self.lbl_archivo.config(text=self.ruta_archivo.split("/")[-1], fg="black")

    def ejecutar_simulacion(self):
        if not self.ruta_archivo:
            messagebox.showwarning("Advertencia", "Por favor, carga un archivo CSV o TXT primero.")
            return

        algoritmo = self.combo_algoritmo.get()
        quantum = 0

        if algoritmo == "Round Robin":
            try:
                quantum = int(self.entry_quantum.get())
                if quantum <= 0: raise ValueError
            except:
                messagebox.showerror("Error", "Para Round Robin, necesitas ingresar un Quantum entero válido mayor a 0.")
                return

        try:
            self.procesos = logica.leer_procesos_csv(self.ruta_archivo)
            
            if algoritmo == "FCFS":
                self.procesos, self.historial_gantt = logica.calcular_fcfs(self.procesos)
            elif algoritmo == "SPN":
                self.procesos, self.historial_gantt = logica.calcular_spn(self.procesos)
            elif algoritmo == "SRT":
                self.procesos, self.historial_gantt = logica.calcular_srt(self.procesos)
            elif algoritmo == "Round Robin":
                self.procesos, self.historial_gantt = logica.calcular_rr(self.procesos, quantum)

            self.actualizar_tabla()
            self.dibujar_gantt_animado()

        except Exception as e:
            messagebox.showerror("Error Interno", str(e))

    def actualizar_tabla(self):
        for row in self.tree.get_children():
            self.tree.delete(row)
            
        suma_retorno = 0
        suma_espera = 0

        for p in self.procesos:
            self.tree.insert("", "end", values=(p.pid, p.llegada, p.rafaga, p.inicio, p.fin, p.retorno, p.espera))
            suma_retorno += p.retorno
            suma_espera += p.espera
            
        n = len(self.procesos)
        if n > 0:
            prom_retorno = suma_retorno / n
            prom_espera = suma_espera / n
            self.lbl_promedios.config(text=f"Promedios Generales >>> Tiempo de Retorno: {prom_retorno:.2f}  |  Tiempo de Espera: {prom_espera:.2f}")

    def dibujar_gantt_animado(self):
        self.canvas.delete("all")
        if not hasattr(self, 'historial_gantt') or not self.historial_gantt:
            return

        escala = 30 
        y_offset = 50
        alto_bloque = 40
        colores = ["#A9CCE3", "#F9E79F", "#A9DFBF", "#F5CBA7", "#AEB6BF", "#D7BDE2", "#F1948A"]

        pids_unicos = []
        for bloque in self.historial_gantt:
            if bloque[0] not in pids_unicos:
                pids_unicos.append(bloque[0])
        mapa_colores = {pid: colores[i % len(colores)] for i, pid in enumerate(pids_unicos)}

        def dibujar_paso(idx):
            if idx < len(self.historial_gantt):
                pid, inicio, fin = self.historial_gantt[idx]
                x1 = inicio * escala + 20
                x2 = fin * escala + 20
                color = mapa_colores[pid]

                self.canvas.create_rectangle(x1, y_offset, x2, y_offset + alto_bloque, fill=color, outline="black")
                centro_x = (x1 + x2) / 2
                self.canvas.create_text(centro_x, y_offset + alto_bloque / 2, text=pid, font=("Arial", 12, "bold"))
                
                self.canvas.create_text(x1, y_offset + alto_bloque + 10, text=str(inicio))
                if idx == len(self.historial_gantt) - 1:
                    self.canvas.create_text(x2, y_offset + alto_bloque + 10, text=str(fin))

                self.root.after(600, dibujar_paso, idx + 1)

        dibujar_paso(0)

if __name__ == "__main__":
    root = tk.Tk()
    app = SimuladorOS(root)
    root.mainloop()