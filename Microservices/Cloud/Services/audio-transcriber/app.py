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

def format_timestamp(ms):
    hours = ms // (3600 * 1000)
    ms -= hours * 3600 * 1000
    minutes = ms // (60 * 1000)
    ms -= minutes * 60 * 1000
    seconds = ms // 1000
    ms -= seconds * 1000
    return f"{hours:02}:{minutes:02}:{seconds:02},{ms:03}"

def transcribe_chunks(chunk_files, output_srt="output.txt", model_size="base"):
    model = whisper.load_model(model_size)

    with open(output_srt, "w", encoding="utf-8") as f:
        for idx, (chunk_filename, start_ms, end_ms) in enumerate(chunk_files, start=1):
            start = format_timestamp(start_ms)
            end = format_timestamp(end_ms)

            result = model.transcribe(chunk_filename, language="en")
            text = result["text"].strip()

            f.write(f"{idx}\n")
            f.write(f"{start} --> {end}\n")
            f.write(f"{text}\n\n")

            print(f"Recognized: {chunk_filename} → {text}")

    print(f"Transcription completed: {output_srt}")

def send_cloudevent(subject, data):
    broker_url = os.environ.get("K_SINK")
    
    if not broker_url:
        print("Error: K_SINK environment variable is not set. CloudEvent will not be sent.", flush=True)
        return

    headers = {
        "Content-Type": "application/json",
        "ce-specversion": "1.0",
        "ce-type": "dev.knative.audio.chunk.processed",
        "ce-source": "audio-splitter-service",
        "ce-id": subject
    }

    try:
        response = requests.post(broker_url, headers=headers, json=data)
        response.raise_for_status()
        print(f"CloudEvent successfully sent to Broker: {response.status_code}", flush=True)
    except requests.exceptions.RequestException as e:
        print(f"Error occurred while sending CloudEvent: {e}", flush=True)


@app.route('/', methods=['POST'])
def process_chunks():
    cloudevent = request.get_json()
    print("CloudEvent received:", cloudevent, flush=True)

    try:
        event_data = cloudevent.get("data") if isinstance(cloudevent, dict) and "data" in cloudevent else cloudevent

        bucket = event_data["bucket"]
        result_dir = event_data["result_dir"]
        chunks_raw = event_data["chunks"]
        key = event_data["key"]
        
        chunks = []
        for local_name, object_name, start_ms, end_ms in chunks_raw:
            os.makedirs(os.path.dirname(local_name), exist_ok=True)
            minio_client.fget_object(bucket, object_name, local_name)
            print(f"Downloaded: {object_name} → {local_name}")
            chunks.append((local_name, start_ms, end_ms))

        transcribe_chunks(chunks, output_srt="tts.txt", model_size="tiny")
        minio_client.fput_object(bucket, f"{result_dir}tts.txt", "tts.txt")

        event_data = {
            "bucket": bucket,
            "result_dir": result_dir,
            "chunks": chunks_raw
        }
        send_cloudevent(subject=key, data=event_data)

        return jsonify({"message": "Processing complete"}), 200

    except Exception as e:
        import traceback
        traceback.print_exc()
        print("Error:", e, flush=True)
        return jsonify({"error": str(e)}), 500

@app.route('/', methods=['GET'])
def home():
    return "Audio Processor Service is running (CloudEvent Sink)\n"

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(debug=False, host="0.0.0.0", port=port)