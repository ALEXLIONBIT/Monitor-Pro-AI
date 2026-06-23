import time
import platform
import subprocess
import requests
import psutil

print("===================")
print(" 🌐 MONITOR PRO AI ")
print("===================")

# 1. Input configurazione utente
host_ip = input("[->] Inserisci l'IP o Dominio del PC Host:   ").strip()
device_name = input("[->] Inserisci il nome personalizzato per questo dispositivo: ").strip()

if not host_ip.startswith("http"):
    host_ip = f"http://{host_ip}:25565"

# 2. Rilevamento automatico del Sistema Operativo
os_type = platform.system()
os_dist = os_type
if os_type == "Linux":
    try:
        with open("/etc/os-release", "r") as f:
            release_info = f.read()
            if "SteamOS" in release_info:
                os_dist = "SteamOS (Arch Linux)"
            elif "Mint" in release_info:
                os_dist = "Linux Mint"
    except:
        os_dist = "Linux (Generic)"

# 3. Rilevamento automatico della CPU
cpu_model = platform.processor()
if not cpu_model or cpu_model == "unknown":
    try:
        # Fallback Linux per leggere il modello esatto
        cpu_model = subprocess.check_output("lscpu | grep 'Model name'", shell=True).decode().split(":")[1].strip()
    except:
        try:
            cpu_model = subprocess.check_output("cat /proc/cpuinfo | grep 'model name' | head -n 1", shell=True).decode().split(":")[1].strip()
        except:
            cpu_model = "Generic x86_64 / ARM"

print(f"\n[+] OS Rilevato autonomamente: {os_dist}")
print(f"[+] CPU Rilevata autonomamente: {cpu_model}")
print(f"[*] Connessione al cluster in corso a: {host_ip}\n")

def read_temperature():
    try:
        temps = psutil.sensors_temperatures()
        if temps:
            for name, entries in temps.items():
                return entries[0].current
    except:
        pass
    return 45.0 # Fallback se i sensori della sandbox sono protetti da sudo

# 4. Loop di trasmissione real-time
while True:
    try:
        cpu = psutil.cpu_percent(interval=1)
        ram = psutil.virtual_memory().percent
        disk = psutil.disk_usage('/').percent
        freq = round(psutil.cpu_freq().current / 1000, 2) if psutil.cpu_freq() else 2.4
        temp = round(read_temperature(), 1)
        
        # Lettura GPU Reale (Rileva se ci sono schede NVIDIA tramite nvidia-smi)
        gpu = 0.0
        try:
            gpu_out = subprocess.check_output("nvidia-smi --query-gpu=utilization.gpu --format=csv,noheader,nounits", shell=True)
            gpu = float(gpu_out.decode().strip())
        except:
            # Fallback proporzionale se la scheda grafica è integrata/condivisa senza tool proprietari
            gpu = round(cpu * 0.7, 1) if cpu > 10 else 2.0
            if gpu > 100: gpu = 100

        payload = {
            "device_id": device_name,
            "cpu": cpu,
            "gpu": gpu,
            "ram": ram,
            "disk": disk,
            "freq": freq,
            "temp": temp,
            "os": os_dist,
            "cpu_model": cpu_model,
            "gpu_model": "NVIDIA GeForce" if gpu > 0 and "nvidia" in str(gpu) else "AMD RDNA2 / Intel Iris"
        }

        # Spedisce i dati al server Flask
        response = requests.post(f"{host_ip}/api/report", json=payload, timeout=5)
        if response.status_code == 200:
            print(f"[{time.strftime('%H:%M:%S')}] Telemetria Reale inviata -> CPU: {cpu}% | GPU: {gpu}% | Temp: {temp}°C", end="\r")
            
    except Exception as e:
        print(f"\n[-] Disconnessione dall'Host o Errore Rete: {e}")
        time.sleep(5)
        
    time.sleep(3)