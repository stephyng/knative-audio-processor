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

def split_audio(input_file, output_dir="chunks", silence_thresh=-40, min_silence_len=500):
    if not os.path.isfile(input_file):
        raise FileNotFoundError(f"File not found: {input_file}")

    os.makedirs(output_dir, exist_ok=True)

    audio = AudioSegment.from_file(input_file, format="mp3")

    nonsilent_ranges = silence.detect_nonsilent(
        audio,
        min_silence_len=min_silence_len,
        silence_thresh=audio.dBFS + silence_thresh
    )

    chunk_files = []
    for idx, (start_ms, end_ms) in enumerate(nonsilent_ranges, start=1):
        chunk = audio[start_ms:end_ms]
        chunk_filename = os.path.join(output_dir, f"chunk_{idx}.mp3")
        chunk.export(chunk_filename, format="mp3")
        chunk_files.append((chunk_filename, start_ms, end_ms))
        print(f"Saved: {chunk_filename}")

    print(f"Audio split complete: {len(chunk_files)} chunks created")
    return chunk_files

def send_cloudevent(subject, data):
    broker_url = os.environ.get("K_SINK")
    
    if not broker_url:
        print("K_SINK environment variable is not set. CloudEvent will not be sent.", flush=True)
        return

    headers = {
        "Content-Type": "application/json",
        "ce-specversion": "1.0",
        "ce-type": "dev.knative.audio.chunks.ready",
        "ce-source": "audio-splitter-service",
        "ce-id": subject
    }

    try:
        response = requests.post(broker_url, headers=headers, json=data)
        response.raise_for_status()
        print(f"CloudEvent sent: {response.status_code}", flush=True)
    except requests.exceptions.RequestException as e:
        print(f"CloudEvent error: {e}", flush=True)


@app.route('/', methods=['POST'])
def process_chunks():
    cloudevent = request.get_json()
    print("CloudEvent received:", cloudevent, flush=True)

    try:
        event_data = cloudevent.get("data") if isinstance(cloudevent, dict) and "data" in cloudevent else cloudevent

        bucket = event_data["bucket"]
        key = event_data["key"]
        
        temp_path = os.path.join(tempfile.gettempdir(), os.path.basename(key))
        print(f"Temp path: {temp_path}", flush=True)

        minio_client.fget_object(bucket, key, temp_path)
        print(f"File downloaded: {temp_path}", flush=True)

        chunks = split_audio(temp_path, output_dir="chunks", silence_thresh=-40, min_silence_len=700)
        print(f"Chunks created: {len(chunks)}", flush=True)

        result_dir = f"results/{os.path.splitext(os.path.basename(key))[0]}/"
        chunks_event_list = []
        for chunk_file, start_ms, end_ms in chunks:
            remote_path = f"{result_dir}chunks/{os.path.basename(chunk_file)}"
            minio_client.fput_object(bucket, remote_path, chunk_file)
            print(f"Chunk uploaded: {remote_path}", flush=True)
            chunks_event_list.append([chunk_file, remote_path, start_ms, end_ms])

        event_data = {
            "bucket": bucket,
            "result_dir": result_dir,
            "chunks": chunks_event_list,
            "key": key
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