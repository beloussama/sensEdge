import streamlit as st
import pandas as pd
import paho.mqtt.client as mqtt
import threading
import queue
import time
import os
import base64
from pymongo import MongoClient
from datetime import datetime

# --- Streamlit Config ---
st.set_page_config(page_title="Edge Dashboard", layout="wide")

# --- MQTT Configuration from environment ---
MQTT_BROKER = os.getenv("MQTT_BROKER", "mosquitto_broker")
MQTT_PORT = int(os.getenv("MQTT_PORT", 1883))
MQTT_TOPIC_SUB = os.getenv("MQTT_TOPIC_SUB", "sensors/motor")

data_queue = queue.Queue()
alert_history = []

# --- MongoDB Config ---
MONGO_URI = "url to mongoDB"
DB_NAME = "motor_data"
COLLECTION_NAME = "sensor_data"

@st.cache_resource
def get_mongo_collection():
    client = MongoClient(MONGO_URI)
    db = client[DB_NAME]
    return db[COLLECTION_NAME]

collection = get_mongo_collection()

# --- MQTT Callback Functions ---
def on_connect(client, userdata, flags, rc):
    if rc == 0:
        client.subscribe(MQTT_TOPIC_SUB)
        print("[MQTT] Connected and subscribed.")
    else:
        print(f"[MQTT] Connection failed with code {rc}.")

def on_message(client, userdata, msg):
    try:
        payload = msg.payload.decode()
        data = pd.read_json(payload, typ='series')
        data_queue.put(data)

        if data.get("etat_moteur", "normal") != "normal":
            alert = {
                "timestamp": data["timestamp"],
                "etat_moteur": data["etat_moteur"],
                "anomalie": data.get("anomalie", "Anomalie détectée")
            }
            alert_history.append(alert)
            if len(alert_history) > 5:
                alert_history.pop(0)
    except Exception as e:
        print("[MQTT] Error decoding message:", e)

# --- MQTT Background Thread ---
def mqtt_thread():
    client = mqtt.Client()
    client.on_connect = on_connect
    client.on_message = on_message
    client.connect(MQTT_BROKER, MQTT_PORT)
    client.loop_forever()

threading.Thread(target=mqtt_thread, daemon=True).start()

# --- Fetch All Data for Stats & CSV ---
def fetch_all_data():
    cursor = collection.find({}, {"_id": 0})
    data = list(cursor)
    df = pd.DataFrame(data)
    if not df.empty:
        df["timestamp"] = pd.to_datetime(df["timestamp"])
    return df

df_all = fetch_all_data()

# --- Encode local image to base64 ---
def load_base64_image(image_path):
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode()

image_base64 = load_base64_image("assets/JESA.png")

# --- Sidebar ---
with st.sidebar:
    st.markdown(
        f"""
        <div style="display:flex; justify-content:center; margin-left:10px; margin-top:10px; margin-bottom:20px">
            <img src="data:image/png;base64,{image_base64}" style="max-width:100%; height:auto; border-radius:10px;">
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown("## Edge Dashboard")
    menu = st.radio("📌 Navigation", ["Dashboard", "Monthly Stats", "Yearly Stats"])
    st.markdown("---")
    st.markdown("### 📥 Download Data")
    if not df_all.empty:
        csv_data = df_all.to_csv(index=False).encode('utf-8')
        st.download_button("Download CSV", csv_data, file_name="motor_data.csv", mime="text/csv")
    else:
        st.info("Waiting for data...")

# === PAGE: DASHBOARD ===
if menu == "Dashboard":
    st.title("🛠️ Real-Time Motor Monitoring Dashboard")

    chart_cols = st.columns(4)

    with chart_cols[0]:
        st.markdown("### 🌡️ Température")
        temp_chart = st.empty()
    with chart_cols[1]:
        st.markdown("### 📈 Vibration")
        vib_chart = st.empty()
    with chart_cols[2]:
        st.markdown("### ⚡ Courant")
        current_chart = st.empty()
    with chart_cols[3]:
        st.markdown("### ⚙️ Vitesse")
        speed_chart = st.empty()

    kpi1, kpi2 = st.columns(2)
    global_state_card = kpi1.empty()
    alerts_card = kpi2.empty()

    df_live = pd.DataFrame(columns=["timestamp", "temperature", "vibration", "courant", "vitesse", "etat_moteur", "anomalie"])

    while True:
        if not data_queue.empty():
            data = data_queue.get()
            data["timestamp"] = pd.to_datetime(data["timestamp"])
            df_live = pd.concat([df_live, pd.DataFrame([data])], ignore_index=True)

            display_df = df_live.tail(50).copy().set_index("timestamp")
            temp_chart.line_chart(display_df["temperature"])
            vib_chart.line_chart(display_df["vibration"])
            current_chart.line_chart(display_df["courant"])
            speed_chart.line_chart(display_df["vitesse"])

            now = datetime.now()

            etat = data.get("etat_moteur", "normal")
            alert_color = "#28a745" if etat == "normal" else "#dc3545"
            alert_text = "✅ Etat du moteur : NORMAL" if etat == "normal" else f"🚨 ETAT MOTEUR: {etat.upper()} - {data.get('anomalie', 'Anomalie détectée')}"

            global_state_card.markdown(f"""
            <div style='border:2px solid {alert_color};border-radius:10px;padding:10px'>
                <h5>📊 État Actuel du Moteur</h5>
                <ul style='list-style:none;padding-left:0'>
                    <li>🌡️ Température: <strong>{data['temperature']} °C</strong></li>
                    <li>📈 Vibration: <strong>{data['vibration']}</strong></li>
                    <li>⚙️ Vitesse: <strong>{data['vitesse']}</strong></li>
                    <li>🔌 Courant: <strong>{data['courant']} A</strong></li>
                </ul>
                <div style='margin-top:10px;padding:8px;background-color:{alert_color};color:white;border-radius:5px;text-align:center'>
                    <strong>{alert_text}</strong>
                </div>
            </div>
            """, unsafe_allow_html=True)

            if alert_history:
                alert_box = "<div style='border:2px solid red;padding:10px;border-radius:10px'>"
                alert_box += "<h5>🚨 Last 5 Alerts</h5><ul>"
                for a in reversed(alert_history[-5:]):
                    t = pd.to_datetime(a['timestamp']).strftime('%Y-%m-%d %H:%M:%S')
                    alert_box += f"<li><strong>{t}</strong>: {a['etat_moteur'].upper()} - {a['anomalie']}</li>"
                alert_box += "</ul></div>"
                alerts_card.markdown(alert_box, unsafe_allow_html=True)

            start_of_month = datetime(now.year, now.month, 1)
            recent_anomalies = list(collection.find({
                "timestamp": {"$gte": start_of_month},
                "etat_moteur": {"$ne": "normal"}
            }).sort("timestamp", -1).limit(5))

            if recent_anomalies:
                rows = ""
                for a in recent_anomalies:
                    t = pd.to_datetime(a['timestamp']).strftime('%Y-%m-%d %H:%M:%S')
                    rows += f"<li><strong>{t}</strong>: {a['etat_moteur'].upper()} - {a.get('anomalie', 'Anomalie détectée')}</li>"

                st.markdown(f"""
                <div style='border:2px solid orange;border-radius:10px;padding:10px;margin-top:20px'>
                    <h5>🕵️‍♂️ Dernières 5 Anomalies (Mois en cours)</h5>
                    <ul>{rows}</ul>
                </div>
                """, unsafe_allow_html=True)

        time.sleep(1)

# === PAGE: MONTHLY STATS ===
elif menu == "Monthly Stats":
    st.title("📅 Monthly Statistics")
    if not df_all.empty:
        df = df_all.copy()
        df["month"] = df["timestamp"].dt.to_period("M")
        stats = df.groupby("month")[["temperature", "vibration", "courant", "vitesse"]].agg(["mean", "max", "min", "count"])
        st.dataframe(stats)
    else:
        st.info("Waiting for data...")

# === PAGE: YEARLY STATS ===
elif menu == "Yearly Stats":
    st.title("📆 Yearly Overview")
    if not df_all.empty:
        df = df_all.copy()
        df["year"] = df["timestamp"].dt.year
        stats = df.groupby("year")[["temperature", "vibration", "courant", "vitesse"]].agg(["mean", "max", "min", "count"])
        st.dataframe(stats)
    else:
        st.info("Waiting for data...")
