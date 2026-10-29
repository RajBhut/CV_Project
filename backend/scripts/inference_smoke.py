"""Run pretrained YOLO inference on an image and a short video."""

from __future__ import annotations

import argparse
from pathlib import Path

import cv2
import torch
from ultralytics import YOLO


def select_device() -> str:
    if torch.cuda.is_available():
        name = torch.cuda.get_device_name(0)
        print(f"CUDA available: {name}")
        return "0"
    print("CUDA unavailable: using CPU fallback")
    return "cpu"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image", type=Path, help="Input image path")
    parser.add_argument("video", type=Path, help="Input short video path")
    parser.add_argument("--model", default="yolo11n.pt")
    parser.add_argument("--image-size", type=int, default=640, choices=(480, 640))
    parser.add_argument("--output-dir", type=Path, default=Path("smoke-output"))
    args = parser.parse_args()

    for source in (args.image, args.video):
        if not source.is_file():
            raise SystemExit(f"Input does not exist: {source}")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    device = select_device()
    model = YOLO(args.model)

    image_result = model.predict(
        source=str(args.image), imgsz=args.image_size, conf=0.4, device=device, verbose=False
    )[0]
    image_output = args.output_dir / f"{args.image.stem}-annotated.jpg"
    if not cv2.imwrite(str(image_output), image_result.plot()):
        raise RuntimeError(f"Could not write annotated image: {image_output}")
    print(f"Image detections: {len(image_result.boxes)}; output: {image_output}")

    capture = cv2.VideoCapture(str(args.video))
    if not capture.isOpened():
        raise RuntimeError(f"OpenCV could not open video: {args.video}")
    width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = capture.get(cv2.CAP_PROP_FPS) or 25.0
    output_path = args.output_dir / f"{args.video.stem}-annotated.mp4"
    writer = cv2.VideoWriter(
        str(output_path), cv2.VideoWriter_fourcc(*"mp4v"), fps, (width, height)
    )
    if not writer.isOpened():
        capture.release()
        raise RuntimeError(f"OpenCV could not create output video: {output_path}")

    processed = 0
    detections = 0
    try:
        while processed < 30:
            ok, frame = capture.read()
            if not ok:
                break
            result = model.predict(
                source=frame, imgsz=args.image_size, conf=0.4, device=device, verbose=False
            )[0]
            writer.write(result.plot())
            detections += len(result.boxes)
            processed += 1
    finally:
        capture.release()
        writer.release()

    if processed == 0:
        raise RuntimeError(f"Video contained no readable frames: {args.video}")
    print(
        f"Video frames processed: {processed}; detections: {detections}; "
        f"output: {output_path}"
    )


if __name__ == "__main__":
    main()
