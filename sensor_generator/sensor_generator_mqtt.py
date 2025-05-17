import random
import time
import json
import socket
import os
from datetime import datetime
from pymongo import MongoClient
import paho.mqtt.publish as publish

# --- MQTT Config ---
MQTT_BROKER = os.getenv("MQTT_BROKER", "mosquitto_broker")
MQTT_PORT = int(os.getenv("MQTT_PORT", 1883))
MQTT_TOPIC = os.getenv("MQTT_TOPIC", "sensors/motor")

# --- MongoDB Config ---
MONGO_URI = os.getenv("MONGO_URI", "mongodb+srv://oussama:Oussama123@cluster0.jsz12tv.mongodb.net/")
client = MongoClient(MONGO_URI)
db = client["motor_data"]
collection = db["sensor_data"]

# --- Etats moteur ---
etat_courant = "normal"
compteur_cycles = 0
anomalie_active = None

# --- Anomalies possibles ---
anomalies_possibles = [
    "palier_defaillant",
    "frein_bloque",
    "surchauffe_stator",
    "grippage_mecanique"
]

# --- Dernières valeurs pour progression douce ---
valeurs_capteurs = {
    "vibration": 0.2,
    "temperature": 55.0,
    "courant": 8.0,
    "vitesse": 1480.0
}

# --- Evolution de l'état du moteur ---
def evolution_etat():
    global etat_courant, compteur_cycles, anomalie_active
    compteur_cycles += 1

    if etat_courant == "normal":
        # Passage à anomalie possible après 5 cycles avec 40% de chance
        if compteur_cycles > 40 and random.random() < 0.4:
            etat_courant = "anormal"
            anomalie_active = random.choices(anomalies_possibles, weights=[3, 2, 2, 3])[0]
            compteur_cycles = 0  # reset compteur dès changement d'état
    else:
        # Retour à normal après 8 à 15 cycles
        if compteur_cycles > random.randint(60, 125):
            etat_courant = "normal"
            anomalie_active = None
            compteur_cycles = 0

# --- Simulation des données avec variation douce ---
def variation_douce(valeur, variation, min_val, max_val):
    nouvelle_valeur = valeur + random.uniform(-variation, variation)
    return round(max(min(nouvelle_valeur, max_val), min_val), 2)

# --- Génération des données moteur avec comportements réalistes ---
def generer_donnees():
    global valeurs_capteurs, etat_courant, anomalie_active, compteur_cycles

    v = valeurs_capteurs

    if etat_courant == "normal":
        v["vibration"] = variation_douce(v["vibration"], 0.05, 0.1, 0.6)
        v["temperature"] = variation_douce(v["temperature"], 0.5, 45, 65)
        v["courant"] = variation_douce(v["courant"], 0.3, 6, 10)
        v["vitesse"] = variation_douce(v["vitesse"], 2, 1470, 1500)

    else:
        # Anomalie : premier cycle, injection d'un saut marqué
        if anomalie_active == "palier_defaillant":
            if compteur_cycles == 1:
                v["vibration"] = round(random.uniform(2.5, 3.5), 2)  # saut net
                v["courant"] = round(random.uniform(10, 14), 2)
                v["temperature"] = round(random.uniform(70, 85), 2)
            else:
                v["vibration"] = variation_douce(v["vibration"], 0.1, 1.5, 4.0)
                v["courant"] = variation_douce(v["courant"], 0.3, 6, 15)
                v["temperature"] = variation_douce(v["temperature"], 0.5, 45, 90)

        elif anomalie_active == "frein_bloque":
            if compteur_cycles == 1:
                v["vitesse"] = round(random.uniform(1100, 1300), 2)
                v["courant"] = round(random.uniform(12, 18), 2)
                v["temperature"] = round(random.uniform(80, 100), 2)
                v["vibration"] = round(random.uniform(1.0, 1.8), 2)
            else:
                v["vitesse"] = variation_douce(v["vitesse"], 5, 1000, 1400)
                v["courant"] = variation_douce(v["courant"], 0.5, 6, 20)
                v["temperature"] = variation_douce(v["temperature"], 1.0, 60, 100)
                v["vibration"] = variation_douce(v["vibration"], 0.1, 0.5, 2.0)

        elif anomalie_active == "surchauffe_stator":
            if compteur_cycles == 1:
                v["temperature"] = round(random.uniform(95, 110), 2)
                v["courant"] = round(random.uniform(12, 18), 2)
                v["vitesse"] = round(random.uniform(1350, 1450), 2)
                v["vibration"] = round(random.uniform(0.6, 1.0), 2)
            else:
                v["temperature"] = variation_douce(v["temperature"], 1.0, 80, 120)
                v["courant"] = variation_douce(v["courant"], 0.4, 8, 20)
                v["vitesse"] = variation_douce(v["vitesse"], 2, 1350, 1480)
                v["vibration"] = variation_douce(v["vibration"], 0.05, 0.2, 1.5)

        elif anomalie_active == "grippage_mecanique":
            if compteur_cycles == 1:
                v["vibration"] = round(random.uniform(2.5, 3.8), 2)
                v["vitesse"] = round(random.uniform(1200, 1350), 2)
                v["temperature"] = round(random.uniform(80, 100), 2)
                v["courant"] = round(random.uniform(10, 15), 2)
            else:
                v["vibration"] = variation_douce(v["vibration"], 0.15, 1.0, 4.0)
                v["vitesse"] = variation_douce(v["vitesse"], 3, 1200, 1450)
                v["temperature"] = variation_douce(v["temperature"], 0.8, 60, 110)
                v["courant"] = variation_douce(v["courant"], 0.5, 6, 18)

    return {
        "timestamp": datetime.utcnow().isoformat(),
        "etat_moteur": etat_courant,
        "anomalie": anomalie_active if etat_courant != "normal" else None,
        "vibration": v["vibration"],
        "temperature": v["temperature"],
        "courant": v["courant"],
        "vitesse": v["vitesse"]
    }

# --- Attente du broker MQTT ---
def wait_for_broker(host, port, timeout=30):
    for _ in range(timeout):
        try:
            with socket.create_connection((host, port), timeout=2):
                print(f"[MQTT] Broker {host}:{port} is ready.")
                return True
        except OSError:
            print(f"[MQTT] Waiting for broker at {host}:{port}...")
            time.sleep(1)
    return False

# --- Boucle principale ---
if wait_for_broker(MQTT_BROKER, MQTT_PORT):
    try:
        print("🚀 Simulation moteur réaliste lancée...")

        while True:
            evolution_etat()
            data = generer_donnees()

            print(f"[{data['timestamp']}] {data['etat_moteur'].upper()} | Anomalie: {data['anomalie']} | Données: {data}")

            # Enregistrement MongoDB
            collection.insert_one(data)
            data.pop("_id", None)

            # Envoi MQTT
            try:
                publish.single(MQTT_TOPIC, payload=json.dumps(data), hostname=MQTT_BROKER, port=MQTT_PORT)
            except Exception as e:
                print(f"[MQTT] Erreur de publication: {e}")

            time.sleep(2)

    except KeyboardInterrupt:
        print("⏹️ Simulation arrêtée.")
else:
    print(f"[MQTT] ❌ Le broker {MQTT_BROKER}:{MQTT_PORT} n'est pas accessible.")
