from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any

from paddleocr import PaddleOCR


@dataclass
class OCRResult:
    text: str
    confidence: float
    bbox: list[list[float]]
    page_number: int


class PolluxOCR:
    """
    OCR engine used by Pollux.

    Stores:
    - detected text
    - confidence score
    - bounding box
    - page number

    Bounding boxes are retained because financial statements
    require positional information for table reconstruction.
    """

    def __init__(self) -> None:
        self.engine = PaddleOCR(
            lang="en",
            use_doc_orientation_classify=False,
            use_doc_unwarping=False,
            use_textline_orientation=False,
        )

    def process_image(
        self,
        image_path: str | Path,
        page_number: int = 1,
    ) -> list[OCRResult]:
        """
        Run OCR on a single image.

        Parameters
        ----------
        image_path:
            Path to the image file.

        page_number:
            Page number associated with the image.

        Returns
        -------
        list[OCRResult]
            OCR detections containing text, confidence,
            coordinates and page number.
        """

        # PaddleOCR 3.x expects a string path or numpy.ndarray.
        # Convert pathlib.Path objects explicitly to string.
        image_path = str(image_path)

        results = self.engine.predict(image_path)

        output: list[OCRResult] = []

        for result in results:
            data = _extract_result_data(result)

            if not data:
                continue

            res = data.get("res", data)

            texts = res.get("rec_texts", [])
            scores = res.get("rec_scores", [])
            boxes = res.get("rec_boxes", [])

            for index, text in enumerate(texts):
                if not text:
                    continue

                score = (
                    float(scores[index])
                    if index < len(scores)
                    else 0.0
                )

                box = (
                    boxes[index]
                    if index < len(boxes)
                    else None
                )

                output.append(
                    OCRResult(
                        text=str(text),
                        confidence=score,
                        bbox=_normalize_bbox(box),
                        page_number=page_number,
                    )
                )

        return output


def _extract_result_data(
    result: Any,
) -> dict[str, Any]:
    """
    Extract the JSON-compatible result dictionary from
    PaddleOCR result objects.

    PaddleOCR versions can expose result data slightly
    differently, so this function keeps that handling
    isolated from the main OCR pipeline.
    """

    if result is None:
        return {}

    # PaddleOCR result objects normally expose `.json`.
    data = getattr(result, "json", None)

    if callable(data):
        data = data()

    if isinstance(data, str):
        import json

        try:
            data = json.loads(data)
        except json.JSONDecodeError:
            return {}

    if isinstance(data, dict):
        return data

    # Defensive fallback for dictionary-like objects.
    if hasattr(result, "to_dict"):
        data = result.to_dict()

        if isinstance(data, dict):
            return data

    return {}


def _normalize_bbox(
    box: Any,
) -> list[list[float]]:
    """
    Normalize PaddleOCR bounding-box formats into:

    [
        [x1, y1],
        [x2, y2],
        [x3, y3],
        [x4, y4]
    ]
    """

    if box is None:
        return []

    # Convert numpy arrays / tuples to ordinary lists where possible.
    if hasattr(box, "tolist"):
        box = box.tolist()

    if isinstance(box, tuple):
        box = list(box)

    if not isinstance(box, list):
        return []

    # Polygon:
    # [
    #   [x1, y1],
    #   [x2, y2],
    #   [x3, y3],
    #   [x4, y4]
    # ]
    if (
        len(box) == 4
        and all(
            isinstance(point, (list, tuple))
            and len(point) >= 2
            for point in box
        )
    ):
        return [
            [
                float(point[0]),
                float(point[1]),
            ]
            for point in box
        ]

    # Rectangle:
    # [x1, y1, x2, y2]
    if (
        len(box) == 4
        and all(
            isinstance(value, (int, float))
            for value in box
        )
    ):
        x1, y1, x2, y2 = map(float, box)

        return [
            [x1, y1],
            [x2, y1],
            [x2, y2],
            [x1, y2],
        ]

    return []


def results_to_dict(
    results: list[OCRResult],
) -> list[dict[str, Any]]:
    """
    Convert OCRResult objects into JSON-compatible dictionaries.
    """

    return [
        asdict(result)
        for result in results
    ]