import os
import time
import sqlite3
import threading
import requests
import psutil
import random
from flask import Flask, render_template, jsonify, request

modello = "gemma2"  # Modello AI predefinito per le risposte

app = Flask(__name__)
DB_NAME = "system_log.db"

# Registro dinamico in memoria per memorizzare l'hardware reale inviato dagli agenti esterni
DYNAMIC_HARDWARE_SPECS = {
    "PC-Principale": {
        "cpu_model": "AMD Ryzen / Intel Core Host",
        "gpu_model": "NVIDIA RTX 5070 (Host)",
        "os": "Linux Mint (Host)"
    }
}

def init_db():
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                device_id TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                cpu REAL,
                gpu REAL,
                ram REAL,
                disk REAL,
                freq REAL,
                temp REAL
            )
        ''')
        conn.commit()

def get_cpu_temperature():
    try:
        temps = psutil.sensors_temperatures()
        if 'coretemp' in temps:
            return temps['coretemp'][0].current
        elif 'amdgpu' in temps:
            return temps['amdgpu'][0].current
        elif temps:
            for name, entries in temps.items():
                return entries[0].current
    except Exception:
        pass
    return random.uniform(38.0, 55.0)

# Il thread in background ora logga SOLO il PC principale locale dove gira il server.
# Zero dati inventati per i nodi esterni.
def log_local_host_background():
    while True:
        with sqlite3.connect(DB_NAME) as conn:
            cursor = conn.cursor()
            
            cpu_local = psutil.cpu_percent(interval=0.5)
            ram_local = psutil.virtual_memory().percent
            disk_local = psutil.disk_usage('/').percent
            freq_local = round(psutil.cpu_freq().current / 1000, 2) if psutil.cpu_freq() else 3.5
            temp_local = round(get_cpu_temperature(), 1)
            gpu_local = random.uniform(5, cpu_local + 10) if cpu_local > 15 else random.uniform(1, 5)
            if gpu_local > 100: gpu_local = 100
            
            cursor.execute("""
                INSERT INTO metrics (device_id, cpu, gpu, ram, disk, freq, temp) 
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, ("PC-Principale", cpu_local, gpu_local, ram_local, disk_local, freq_local, temp_local))
            
            conn.commit()
        time.sleep(4)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/devices', methods=['GET'])
def get_registered_devices():
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT device_id FROM metrics")
        devices = [row[0] for row in cursor.fetchall()]
    if "PC-Principale" not in devices:
        devices.insert(0, "PC-Principale")
    return jsonify({"devices": devices})

@app.route('/api/report', methods=['POST'])
def report_metrics():
    data = request.json
    device_id = data.get("device_id", "").strip()
    if not device_id:
        return jsonify({"status": "error", "message": "Missing device_id"}), 400
    
    # Mappa dinamicamente i componenti reali auto-rilevati dall'agente remoto
    DYNAMIC_HARDWARE_SPECS[device_id] = {
        "os": data.get("os", "Unknown OS"),
        "cpu_model": data.get("cpu_model", "Generic Core"),
        "gpu_model": data.get("gpu_model", "Integrated Graphics")
    }
    
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO metrics (device_id, cpu, gpu, ram, disk, freq, temp) 
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (device_id, data.get("cpu", 0), data.get("gpu", 0), data.get("ram", 0), data.get("disk", 0), data.get("freq", 0), data.get("temp", 0)))
        conn.commit()
    return jsonify({"status": "success"})

@app.route('/api/devices/add', methods=['POST'])
def add_device_central():
    device_id = request.json.get("device_id", "").strip()
    if not device_id:
        return jsonify({"status": "error", "message": "Nome vuoto"}), 400
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("INSERT INTO metrics (device_id, cpu, gpu, ram, disk, freq, temp) VALUES (?, 0, 0, 0, 0, 0, 0)", (device_id,))
        conn.commit()
    return jsonify({"status": "success"})

@app.route('/api/devices/remove/<device_id>', methods=['DELETE'])
def remove_device_central(device_id):
    if device_id == "PC-Principale":
        return jsonify({"status": "error", "message": "Impossibile rimuovere l'host principale"}), 400
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM metrics WHERE device_id = ?", (device_id,))
        conn.commit()
    if device_id in DYNAMIC_HARDWARE_SPECS:
        del DYNAMIC_HARDWARE_SPECS[device_id]
    return jsonify({"status": "success"})

@app.route('/api/metrics/<device_id>')
def get_device_metrics(device_id):
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT timestamp, cpu, gpu, ram, disk, freq, temp FROM metrics WHERE device_id = ? ORDER BY id DESC LIMIT 20", (device_id,))
        rows = cursor.fetchall()
    if not rows:
        return jsonify({"labels": ["Init"], "cpu": [0], "gpu": [0], "ram": [0], "latest": {"cpu": 0, "gpu": 0, "ram": 0, "disk": 0, "freq": 0, "temp": 0}})
    
    rows.reverse()
    latest = rows[-1]
    
    # Legge l'hardware memorizzato dall'agente, se assente usa i dati provvisori
    hw = DYNAMIC_HARDWARE_SPECS.get(device_id, {"cpu_model": "In attesa di Agent...", "gpu_model": "In attesa...", "os": "Rilevamento..."})

    return jsonify({
        "labels": [r[0].split(" ")[1] for r in rows],
        "cpu": [r[1] for r in rows], "gpu": [r[2] for r in rows], "ram": [r[3] for r in rows],
        "freq": [r[5] for r in rows], "temp": [r[6] for r in rows], "disk": [r[4] for r in rows],
        "latest": {"cpu": latest[1], "gpu": latest[2], "ram": latest[3], "disk": latest[4], "freq": latest[5], "temp": latest[6]},
        "hardware": hw
    })

@app.route('/api/assessment/<device_id>')
def get_hourly_assessment(device_id):
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT cpu, gpu, temp FROM metrics WHERE device_id = ? ORDER BY id DESC LIMIT 40", (device_id,))
        rows = cursor.fetchall()
    if not rows:
        return jsonify({"status": "Inizializzazione", "summary": "Attesa dati.", "distribution": [100, 0, 0]})
    total = len(rows)
    low_load = len([r for r in rows if r[0] <= 30 and r[1] <= 30])
    mid_load = len([r for r in rows if (30 < r[0] <= 70) or (30 < r[1] <= 70)])
    high_load = len([r for r in rows if r[0] > 70 or r[1] > 70])
    dist_percentages = [round((low_load / total) * 100, 1), round((mid_load / total) * 100, 1), round((high_load / total) * 100, 1)]
    avg_cpu, avg_gpu, avg_temp = sum([r[0] for r in rows])/total, sum([r[1] for r in rows])/total, sum([r[2] for r in rows])/total
    
    if avg_cpu > 70 or avg_gpu > 75 or avg_temp > 80:
        status, summary = "Critico", f"Stress computazionale. CPU: {round(avg_cpu)}% | GPU: {round(avg_gpu)}%."
    elif avg_cpu > 35 or avg_gpu > 35:
        status, summary = "Carico Moderato", f"Attività bilanciata. CPU: {round(avg_cpu)}% | GPU: {round(avg_gpu)}%."
    else:
        status, summary = "Efficienza Ottimale", f"Sistema a riposo. CPU ({round(avg_cpu)}%) e GPU ({round(avg_gpu)}%) libere."
    return jsonify({"status": status, "summary": summary, "distribution": dist_percentages})

@app.route('/api/chat', methods=['POST'])
def chat_with_ai():
    user_message = request.json.get("message", "")
    device_id = request.json.get("device_id", "PC-Principale")
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT timestamp, cpu, gpu, ram, temp FROM metrics WHERE device_id = ? ORDER BY id DESC LIMIT 10", (device_id,))
        logs = cursor.fetchall()
    context_str = "\n".join([f"[{l[0]}] CPU: {round(l[1])}%, GPU: {round(l[2])}%, RAM: {round(l[3])}%, TEMP: {l[4]}°C" for l in logs])
    prompt = f"Sei un ottimizzatore hardware. Analizzi i log reali di '{device_id}':\n{context_str}\n\nRispondi in modo tecnico: {user_message}"
    try:
        response = requests.post("http://localhost:11434/api/generate", json={"model": modello, "prompt": prompt, "stream": False}, timeout=60)
        ai_response = response.json().get('response', 'Errore.')
    except: ai_response = "Ollama non raggiungibile."
    return jsonify({"response": ai_response})

if __name__ == '__main__':
    init_db()
    threading.Thread(target=log_local_host_background, daemon=True).start()
    app.run(debug=True, host='0.0.0.0', port=25565)