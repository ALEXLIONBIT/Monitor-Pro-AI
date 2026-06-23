# MONITOR PRO AI - Remote Telemetry Agent

Un'infrastruttura di monitoraggio hardware centralizzata basata su architettura Client/Server. Il sistema raccoglie in tempo reale metriche di CPU, GPU, RAM, Disco e Temperature da vari dispositivi nella rete (PC Windows, Linux, SteamOS) e li invia a un server centrale Flask. Include un database SQLite per lo storico e un'integrazione AI (Ollama) per l'analisi intelligente dei log.

## Architettura del Sistema

Il progetto è diviso in due componenti principali:
1. **Server Host (`main.py`):** Riceve i dati, ospita la dashboard Web UI, gestisce il database SQLite e processa l'analisi AI.
2. **Client Agent (`add-machine.py`):** Lo script leggero da eseguire sui dispositivi secondari (es. Steam Deck, laptop) per rilevare l'hardware e trasmettere la telemetria.

---

## 🖥️ PARTE 1: Installazione del Server Host (PC Principale)

Questa configurazione va eseguita **solo sul computer principale** che fungerà da server di raccolta dati.

### Requisiti
- Python 3.x
- Ollama installato localmente (per le funzioni di chat AI)

### 1. Configurazione dell'ambiente
Apri il terminale nella cartella del server e installa le dipendenze:
```bash
pip install flask psutil requests