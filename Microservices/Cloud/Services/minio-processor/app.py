import os
import glob
import re
from flask import Flask, jsonify, request
from pydub import AudioSegment, silence
import whisper
from minio import Minio
import tempfile
from urllib.parse import unquote
import requests
import json

minio_client = Minio(
    os.environ.get("MINIO_ENDPOINT", "minio.minio:9000"),
    access_key=os.environ.get("MINIO_ACCESS_KEY", "minioadmin"),
    secret_key=os.environ.get("MINIO_SECRET_KEY", "minioadmin"),
    secure=False
)

app = Flask(__name__)

def send_cloudevent(subject, data):
    broker_url = os.environ.get("K_SINK")
    
    if not broker_url:
        print("Error: K_SINK environment variable is not set. CloudEvent will not be sent.", flush=True)
        return

    headers = {
        "Content-Type": "application/json",
        "ce-specversion": "1.0",
        "ce-type": "dev.knative.minio.object.created",
        "ce-source": "audio-splitter-service",
        "ce-id": subject
    }

    try:
        response = requests.post(broker_url, headers=headers, json=data)
        response.raise_for_status()
        print(f"CloudEvent sent successfully to Broker: {response.status_code}", flush=True)
    except requests.exceptions.RequestException as e:
        print(f"Error sending CloudEvent: {e}", flush=True)
    

@app.route('/minio-event', methods=['POST'])
def handle_minio_event():
    data = request.get_json()
    print("MinIO Event received:", data, flush=True)

    try:
        records = data.get("Records", [])
        for record in records:
            bucket = record["s3"]["bucket"]["name"]
            raw_key = record["s3"]["object"]["key"]

            key = unquote(raw_key)

            if key.startswith(("results/", "locks/", "chunks/")) or key.endswith(("_merged.mp3", "_tts.txt")):
                print(f"Ignored (own file or result): {key}", flush=True)
                continue

            print(f"Bucket: {bucket}, Key: {key}", flush=True)

            event_data = {
                "bucket": bucket,
                "key": key
            }
            send_cloudevent(subject=key, data=event_data)

        return jsonify({"message": "Processing complete"}), 200

    except Exception as e:
        import traceback
        traceback.print_exc()
        print("Error:", e, flush=True)
        return jsonify({"error": str(e)}), 500


@app.route('/')
def home():
    return "Audio Splitter Service is running (MinIO Event Handler)\n"

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(debug=False, host="0.0.0.0", port=port)