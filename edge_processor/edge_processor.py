import os
import pandas as pd
import json
import paho.mqtt.client as mqtt
from datetime import datetime
import xgboost as xgb

# --- Load Model and Label Mappings ---
MODEL_PATH = "motor_model_xgb.model"
MAPPINGS_PATH = "label_mapping_xgb.json"

if not os.path.exists(MODEL_PATH):
    print(f"❌ Model file not found at {MODEL_PATH}")
else:
    print(f"✅ Model file found at {MODEL_PATH}")

try:
    model = xgb.Booster()
    model.load_model(MODEL_PATH)
    print("✅ Model loaded successfully")
except Exception as e:
    print(f"❌ Failed to load model: {e}")

try:
    with open(MAPPINGS_PATH, 'r') as f:
        mappings = json.load(f)
    label_mapping = mappings["label_mapping"]
    anomalie_mapping = mappings["anomalie_mapping"]
    print("✅ XGBoost model and mappings loaded.")
except Exception as e:
    print(f"❌ Failed to load label mappings: {e}")

# --- MQTT Configuration ---
MQTT_BROKER = os.getenv("MQTT_BROKER", "mosquitto_broker")  
MQTT_PORT = int(os.getenv("MQTT_PORT", 1883))
MQTT_TOPIC_SUB = "sensors/motor"
# MQTT_TOPIC_PUB = "predictions/motor"

client = mqtt.Client()


# --- Prediction Function ---
def predict_motor_status(temp, vib, courant, vitesse, timestamp=None):
    """
    Predicts motor status and anomaly based on sensor data.
    """
    if timestamp is None:
        timestamp = datetime.now()
    else:
        timestamp = pd.to_datetime(timestamp)

    hour = timestamp.hour
    dayofweek = timestamp.dayofweek
    month = timestamp.month
    day_night = 1 if 6 <= hour < 18 else 0

    # Input columns expected by the model
    input_columns = ["vibration", "temperature", "courant", "vitesse", "hour", "dayofweek", "month", "day_night"]
    input_data = pd.DataFrame([[vib, temp, courant, vitesse, hour, dayofweek, month, day_night]], columns=input_columns)
    input_dmatrix = xgb.DMatrix(input_data)

    # Prediction
    pred_code = model.predict(input_dmatrix)[0]
    pred_code = int(round(pred_code))

    print(f"Predicted code: {pred_code}")  # Debugging line

    combined_label = label_mapping.get(str(pred_code), "unknown")
    etat_code, anomalie_code = combined_label.split("_")
    etat_moteur = "anormal" if etat_code == "1" else "normal"
    anomalie = anomalie_mapping.get(str(int(anomalie_code)), "aucune")  # FIXED

    return etat_moteur, anomalie



# --- MQTT Callbacks ---
def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print("✅ Connected to MQTT Broker")
        client.subscribe(MQTT_TOPIC_SUB)
    else:
        print(f"❌ Connection failed with code {rc}")


def on_message(client, userdata, msg):
    """
    Handles the received MQTT message and predicts motor status and anomalies.
    """
    try:
        payload = json.loads(msg.payload.decode())
        print(f"📩 Received sensor data: {payload}")

        temperature = payload.get("temperature")
        vibration = payload.get("vibration")
        courant = payload.get("courant")
        vitesse = payload.get("vitesse")
        timestamp = payload.get("timestamp", None)

        # Call prediction function
        etat_moteur, anomalie = predict_motor_status(temp=temperature, vib=vibration, courant=courant, vitesse=vitesse,
                                                     timestamp=timestamp)

        prediction_payload = {
            "timestamp": timestamp if timestamp else datetime.now().isoformat(),
            "etat_moteur": etat_moteur,
            "anomalie": anomalie
        }

        # Publish the prediction (if you want to send back the result to another MQTT topic)
        # client.publish(MQTT_TOPIC_PUB, json.dumps(prediction_payload))
        print(f"🚀 Prediction: {prediction_payload}")

    except Exception as e:
        print(f"⚠️ Error processing message: {e}")


# --- Start MQTT Client ---
client.on_connect = on_connect
client.on_message = on_message

try:
    print(f"🔌 Connecting to MQTT broker at {MQTT_BROKER}:{MQTT_PORT}")
    client.connect(MQTT_BROKER, MQTT_PORT)
    client.loop_forever()
except Exception as e:
    print(f"❌ MQTT connection error: {e}")
