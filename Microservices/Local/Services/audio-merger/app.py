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

def merge_audios(input_files, output_file="merged.mp3"):
    if not input_files:
        raise ValueError("No input files!")

    merged = AudioSegment.empty()
    for file in input_files:
        if not os.path.isfile(file):
            raise FileNotFoundError(f"File not found: {file}")
        audio = AudioSegment.from_file(file, format="mp3")
        merged += audio
        print(f"Merged: {file}")

    merged.export(output_file, format="mp3")
    print(f"Merged file saved as: {output_file}\n")

def numeric_sort(file_list):
    return sorted(file_list, key=lambda x: int(re.search(r"chunk_(\d+)\.mp3", x).group(1)))


@app.route('/', methods=['POST'])
def process_chunks():
    cloudevent = request.get_json()
    print("CloudEvent received:", cloudevent, flush=True)

    try:
        event_data = cloudevent.get("data") if isinstance(cloudevent, dict) and "data" in cloudevent else cloudevent

        bucket = event_data["bucket"]
        result_dir = event_data["result_dir"]
        chunks_raw = event_data["chunks"]
        
        chunks = []
        for local_name, object_name, start_ms, end_ms in chunks_raw:
            os.makedirs(os.path.dirname(local_name), exist_ok=True)
            minio_client.fget_object(bucket, object_name, local_name)
            print(f"Downloaded: {object_name} → {local_name}")
            chunks.append((local_name, start_ms, end_ms))

        files = [c[0] for c in chunks]
        files = numeric_sort(files)
        merge_audios(files, "merged.mp3")

        minio_client.fput_object(bucket, f"{result_dir}merged.mp3", "merged.mp3")

        print(f"Results uploaded: {result_dir}", flush=True)

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