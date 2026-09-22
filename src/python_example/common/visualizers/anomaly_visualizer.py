# Copyright (C) 2018- DEEPX Ltd. All rights reserved.
"""Visualizer for anomaly-detection feature responses."""
from __future__ import annotations

from typing import List

import cv2
import numpy as np

from ..base import AnomalyResult, IVisualizer


class AnomalyVisualizer(IVisualizer):
    """Overlay the feature response on the frame, with its relative severity.

    The severity is labelled "relative" on the frame itself, and that wording is
    deliberate: these are single networks out of multi-network methods (EfficientAD
    needs its teacher, student and autoencoder together; PatchCore needs a memory bank
    of training features), so the number ranks frames against each other and is not
    the published EfficientAD or PatchCore score. Printing a bare "score" would invite
    exactly the comparison it cannot support.
    """

    def __init__(self, alpha: float = 0.5, colormap: int = cv2.COLORMAP_JET):
        self.alpha = float(alpha)
        self.colormap = colormap

    def visualize(self, image: np.ndarray,
                  results: List[AnomalyResult]) -> np.ndarray:
        output = image.copy()
        if not results:
            return output

        result = results[0]
        heatmap = result.heatmap
        if heatmap is None or heatmap.size == 0:
            return output

        height, width = output.shape[:2]
        if heatmap.shape[:2] != (height, width):
            heatmap = cv2.resize(heatmap, (width, height),
                                 interpolation=cv2.INTER_LINEAR)
        coloured = cv2.applyColorMap(
            np.clip(heatmap * 255.0, 0, 255).astype(np.uint8), self.colormap)
        output = cv2.addWeighted(output, 1.0 - self.alpha, coloured, self.alpha, 0.0)

        label = f"relative severity {result.score:.3f}"
        if result.channels:
            label += f"  ({result.channels} ch)"
        cv2.putText(output, label, (12, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.7,
                    (0, 0, 0), 3, cv2.LINE_AA)
        cv2.putText(output, label, (12, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.7,
                    (255, 255, 255), 1, cv2.LINE_AA)
        return output
