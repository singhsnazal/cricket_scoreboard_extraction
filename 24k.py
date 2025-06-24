import streamlit as st
import os
import cv2
import easyocr
import json
import tempfile
import re
from pathlib import Path

# ==== OCR Configuration ====
reader = easyocr.Reader(['en'], gpu=False)

# ==== Clip Saving Function ====
def save_clip(video_path, start_f, end_f, over_label, ball_number, run_type, output_dir):
    over_folder = f"over_{int(float(over_label))}"
    over_path = output_dir / over_folder
    over_path.mkdir(parents=True, exist_ok=True)
    clip_name = f"ball{ball_number}_{run_type}.mp4"
    clip_path = over_path / clip_name

    cap = cv2.VideoCapture(str(video_path))
    cap.set(cv2.CAP_PROP_POS_FRAMES, start_f)
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    out = cv2.VideoWriter(str(clip_path), fourcc, fps, (width, height))

    for _ in range(start_f, end_f + 1):
        ret, frame = cap.read()
        if not ret:
            break
        out.write(frame)

    out.release()
    cap.release()
    return str(clip_path)

# ==== OCR helper ====
def extract_over_and_runs(text):
    over = None
    run = None
    over_match = re.search(r"\b(\d{1,2}\.\d)\b", text)
    run_match = re.search(r"\b(\d{1,3})\b", text)
    if over_match:
        over = over_match.group(1)
    if run_match:
        run = int(run_match.group(1))
    return over, run

# ==== Streamlit UI ====
st.set_page_config(page_title="🏏 Cricket Clip Analyzer")
st.title("🏏 Cricket Ball-by-Ball Clip Extractor & Viewer")

uploaded_file = st.file_uploader("Upload Cricket Match Video", type=["mp4"])

if uploaded_file:
    with tempfile.TemporaryDirectory() as tmpdir:
        video_path = Path(tmpdir) / uploaded_file.name
        with open(video_path, "wb") as f:
            f.write(uploaded_file.read())

        st.success("Video uploaded. Processing...")

        cap = cv2.VideoCapture(str(video_path))
        fps = cap.get(cv2.CAP_PROP_FPS)
        frame_interval = 10
        frame_number = 0

        previous_over = None
        previous_run = None
        start_frame = None
        ball_number = 1
        json_log = []

        output_dir = Path(tmpdir) / "clips"
        output_dir.mkdir(exist_ok=True)

        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break

            if frame_number % frame_interval == 0:
                h = frame.shape[0]
                cropped = frame[int(h * 0.85):, :]
                gray = cv2.cvtColor(cropped, cv2.COLOR_BGR2GRAY)
                results = reader.readtext(gray, detail=0)
                text = " ".join(results)

                over, run = extract_over_and_runs(text)

                if over and over != previous_over:
                    if previous_over is not None:
                        run_type = "dot"
                        if previous_run is not None and run is not None:
                            diff = run - previous_run
                            run_type = str(diff) if diff in [1, 2, 3, 4, 6] else "other"

                        clip_path = save_clip(
                            video_path, start_frame, frame_number - 1,
                            previous_over, ball_number, run_type, output_dir
                        )

                        json_log.append({
                            "over": previous_over,
                            "ball": ball_number,
                            "start_frame": start_frame,
                            "end_frame": frame_number - 1,
                            "run_type": run_type,
                            "clip_path": clip_path
                        })

                        ball_number += 1

                    previous_over = over
                    previous_run = run
                    start_frame = frame_number

            frame_number += 1

        cap.release()

        # Save last
        if previous_over:
            run_type = "dot"
            clip_path = save_clip(video_path, start_frame, frame_number - 1, previous_over, ball_number, run_type, output_dir)
            json_log.append({
                "over": previous_over,
                "ball": ball_number,
                "start_frame": start_frame,
                "end_frame": frame_number - 1,
                "run_type": run_type,
                "clip_path": clip_path
            })

        st.success("✅ All clips extracted!")

        # ==== Display section ====
        st.header("📊 View Clips by Run Type")
        run_types = sorted(set(entry["run_type"] for entry in json_log))
        selected_run = st.selectbox("Select Run Type", run_types)

        for entry in json_log:
            if entry["run_type"] == selected_run:
                st.markdown(f"**Over {entry['over']} - Ball {entry['ball']}**")
                st.video(entry["clip_path"])
