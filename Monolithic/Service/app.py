import os
import glob
import re
from flask import Flask, jsonify, request

from pydub import AudioSegment, silence
import whisper

from minio import Minio
import tempfile
from urllib.parse import unquote

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

    print(f"Created {len(chunk_files)} audio files in the '{output_dir}' folder.")
    return chunk_files

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

@app.route('/')
def home():
    return "Audio processor Knative service is running\n"

@app.route('/process', methods=['POST'])
def process_audio():
    input_file = request.args.get("input", "tts.mp3")
    chunk_dir = "chunks"

    try:
        chunks = split_audio(input_file, output_dir=chunk_dir, silence_thresh=-40, min_silence_len=700)
        transcribe_chunks(chunks, output_srt="tts.txt", model_size="small")

        files = [c[0] for c in chunks]
        files = numeric_sort(files)
        merge_audios(files, "merged.mp3")

        return jsonify({
            "message": "Processing complete",
            "chunks": len(chunks),
            "output_files": {
                "transcript": "tts.txt",
                "merged": "merged.mp3"
            }
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/minio-event', methods=['POST'])
def handle_minio_event():
    data = request.get_json()
    print("MinIO event received:", data, flush=True)

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

            temp_path = os.path.join(tempfile.gettempdir(), os.path.basename(key))
            print(f"Temp path: {temp_path}", flush=True)

            minio_client.fget_object(bucket, key, temp_path)
            print(f"File downloaded: {temp_path}", flush=True)

            chunks = split_audio(temp_path, output_dir="chunks", silence_thresh=-40, min_silence_len=700)
            print(f"Created {len(chunks)} chunks", flush=True)

            result_dir = f"results/{os.path.splitext(os.path.basename(key))[0]}/"
            for chunk_file, start_ms, end_ms in chunks:
                remote_path = f"{result_dir}chunks/{os.path.basename(chunk_file)}"
                minio_client.fput_object(bucket, remote_path, chunk_file)
                print(f"Chunk uploaded: {remote_path}", flush=True)

            transcribe_chunks(chunks, output_srt="tts.txt", model_size="tiny")
            files = [c[0] for c in chunks]
            files = numeric_sort(files)
            merge_audios(files, "merged.mp3")

            minio_client.fput_object(bucket, f"{result_dir}merged.mp3", "merged.mp3")
            minio_client.fput_object(bucket, f"{result_dir}tts.txt", "tts.txt")

            print(f"Results uploaded: {result_dir}", flush=True)

        return jsonify({"message": "Processing complete"}), 200

    except Exception as e:
        import traceback
        traceback.print_exc()
        print("Error:", e, flush=True)
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(debug=False, host="0.0.0.0", port=port)
