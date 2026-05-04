import csv

class Proceso:
    def __init__(self, pid, llegada, rafaga):
        self.pid = pid
        self.llegada = int(llegada)
        self.rafaga = int(rafaga)
        self.tiempo_restante = int(rafaga) 
        self.inicio = -1 
        self.fin = 0
        self.retorno = 0
        self.espera = 0
        self.en_cola = False 

def leer_procesos_csv(ruta_archivo):
    procesos = []
    try:
        with open(ruta_archivo, mode='r', encoding='utf-8') as file:
            reader = csv.reader(file)
            next(reader) 
            for row in reader:
                if len(row) == 3:
                    procesos.append(Proceso(row[0], row[1], row[2]))
        return procesos
    except Exception as e:
        raise Exception(f"Error al leer el archivo: {e}")

def calcular_fcfs(procesos):
    procesos.sort(key=lambda p: p.llegada)
    historial_gantt = []
    tiempo_actual = 0
    
    for p in procesos:
        if tiempo_actual < p.llegada:
            tiempo_actual = p.llegada
            
        p.inicio = tiempo_actual
        p.fin = tiempo_actual + p.rafaga
        p.retorno = p.fin - p.llegada
        p.espera = p.retorno - p.rafaga 
        
        historial_gantt.append((p.pid, p.inicio, p.fin))
        tiempo_actual = p.fin
        
    return procesos, historial_gantt

def calcular_spn(procesos):
    procesos.sort(key=lambda p: p.llegada)
    historial_gantt = []
    tiempo_actual = 0
    procesos_pendientes = procesos.copy()
    
    while procesos_pendientes:
        disponibles = [p for p in procesos_pendientes if p.llegada <= tiempo_actual]
        
        if disponibles:
            proceso_elegido = min(disponibles, key=lambda p: p.rafaga)
            procesos_pendientes.remove(proceso_elegido)
            
            proceso_elegido.inicio = tiempo_actual
            proceso_elegido.fin = tiempo_actual + proceso_elegido.rafaga
            proceso_elegido.retorno = proceso_elegido.fin - proceso_elegido.llegada
            proceso_elegido.espera = proceso_elegido.retorno - proceso_elegido.rafaga
            
            historial_gantt.append((proceso_elegido.pid, proceso_elegido.inicio, proceso_elegido.fin))
            tiempo_actual = proceso_elegido.fin
        else:
            tiempo_actual = min(p.llegada for p in procesos_pendientes)
            
    return procesos, historial_gantt

def calcular_srt(procesos):
    procesos.sort(key=lambda p: p.llegada)
    historial_gantt = []
    tiempo_actual = 0
    completados = 0
    n = len(procesos)
    
    for p in procesos:
        p.tiempo_restante = p.rafaga
        p.inicio = -1
        
    proceso_actual = None
    inicio_bloque = -1
    
    while completados < n:
        disponibles = [p for p in procesos if p.llegada <= tiempo_actual and p.tiempo_restante > 0]
        
        if disponibles:
            siguiente_proceso = min(disponibles, key=lambda p: (p.tiempo_restante, p.llegada))
            
            if proceso_actual != siguiente_proceso:
                if proceso_actual is not None and proceso_actual.tiempo_restante > 0:
                    historial_gantt.append((proceso_actual.pid, inicio_bloque, tiempo_actual))
                
                proceso_actual = siguiente_proceso
                inicio_bloque = tiempo_actual
                if proceso_actual.inicio == -1:
                    proceso_actual.inicio = tiempo_actual
                    
            proceso_actual.tiempo_restante -= 1
            tiempo_actual += 1
            
            if proceso_actual.tiempo_restante == 0:
                historial_gantt.append((proceso_actual.pid, inicio_bloque, tiempo_actual))
                proceso_actual.fin = tiempo_actual
                proceso_actual.retorno = proceso_actual.fin - proceso_actual.llegada
                proceso_actual.espera = proceso_actual.retorno - proceso_actual.rafaga
                completados += 1
                proceso_actual = None
        else:
            tiempo_actual += 1
            
    return procesos, historial_gantt

def calcular_rr(procesos, quantum):
    procesos.sort(key=lambda p: p.llegada)
    historial_gantt = []
    tiempo_actual = 0
    completados = 0
    n = len(procesos)
    cola = []
    
    for p in procesos:
        p.tiempo_restante = p.rafaga
        p.inicio = -1
        p.en_cola = False

    def encolar_llegadas(hasta_tiempo, ignorar_proceso=None):
        for p in procesos:
            if p != ignorar_proceso and p.llegada <= hasta_tiempo and p.tiempo_restante > 0 and not p.en_cola:
                cola.append(p)
                p.en_cola = True

    encolar_llegadas(tiempo_actual)
    
    while completados < n:
        if not cola:
            tiempo_actual += 1
            encolar_llegadas(tiempo_actual)
            continue
            
        proceso_actual = cola.pop(0)
        proceso_actual.en_cola = False
        
        if proceso_actual.inicio == -1:
            proceso_actual.inicio = tiempo_actual
            
        tiempo_ejecucion = min(proceso_actual.tiempo_restante, quantum)
        inicio_bloque = tiempo_actual
        
        tiempo_actual += tiempo_ejecucion
        proceso_actual.tiempo_restante -= tiempo_ejecucion
        
        historial_gantt.append((proceso_actual.pid, inicio_bloque, tiempo_actual))
        
        encolar_llegadas(tiempo_actual, ignorar_proceso=proceso_actual)
        
        if proceso_actual.tiempo_restante > 0:
            cola.append(proceso_actual)
            proceso_actual.en_cola = True
        else:
            proceso_actual.fin = tiempo_actual
            proceso_actual.retorno = proceso_actual.fin - proceso_actual.llegada
            proceso_actual.espera = proceso_actual.retorno - proceso_actual.rafaga
            completados += 1
            
    return procesos, historial_gantt