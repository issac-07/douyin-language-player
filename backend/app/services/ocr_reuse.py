"""Fail-closed, bounded subtitle-stroke reuse. No ROI resizing or hash-only test.

White/high-contrast outlined subtitles only. Other typography falls back to OCR.
Exact stroke agreement is required both inside OCR boxes and across the ROI, so
new lines/words outside previous boxes cannot pass unnoticed. Moving dark/color
background pixels may change without changing this signature. This is still a
heuristic and must be opt-in until validated on broader real-world footage.
"""
import cv2
import numpy as np


class SubtitleReuse:
    VERSION = 'white-strokes-exact-v1'

    def __init__(self, mode='fast'):
        self.maximum_seconds = 1.0 if mode == 'balanced' else 2.0
        self.signature = None
        self.timestamp = None
        self.box_mask = None

    @staticmethod
    def strokes(image):
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        local_dark = cv2.erode(gray, np.ones((5, 5), np.uint8))
        return ((gray >= 200) & (gray.astype(np.int16) - local_dark >= 70)).astype(np.uint8)

    def remember(self, image, observation):
        self.signature = self.timestamp = self.box_mask = None
        if observation.confidence < .95 or len(observation.text.strip()) < 4 or not observation.boxes:
            return
        signature = self.strokes(image)
        mask = np.zeros(signature.shape, np.uint8)
        for box in observation.boxes:
            points = np.array(box, np.float32).reshape(-1, 2)
            x, y, w, h = cv2.boundingRect(points)
            mask[max(0, y-3):min(mask.shape[0], y+h+3), max(0, x-3):min(mask.shape[1], x+w+3)] = 1
        foreground = signature[mask != 0]
        # Refuse weak/blurred/no-stroke or unusually solid regions.
        count = int(foreground.sum())
        if count < max(40, len(observation.text.strip()) * 8) or count > .5 * len(foreground):
            return
        self.signature, self.timestamp, self.box_mask = signature, observation.timestamp, mask

    def can_reuse(self, image, timestamp):
        if self.signature is None or not 0 < timestamp - self.timestamp < self.maximum_seconds:
            return False
        if image.shape[:2] != self.signature.shape:
            return False
        current = self.strokes(image)
        # No averaging: a single changed character stroke forces OCR. Checking
        # outside the old boxes catches new lines, negation and repositioning.
        return (np.array_equal(current[self.box_mask != 0], self.signature[self.box_mask != 0])
                and np.array_equal(current[self.box_mask == 0], self.signature[self.box_mask == 0]))
