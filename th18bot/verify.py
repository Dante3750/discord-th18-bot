"""Geometric check: are two screenshots the same base layout?

Clash uses a fixed camera angle, so two screenshots of one base differ only by zoom and pan
(plus UI and scenery). We find SIFT keypoints in both images, pair them up, and ask RANSAC for a
single zoom+shift (similarity transform) that lines them up. Many points agreeing on one
transform = the same layout. A different base can't line up, no matter how alike it looks.
"""

import numpy as np

MAX_SIDE = 1280
SAME_BASE_INLIERS = 30   # points that must line up to call it the same base


def _gray(img):
    import cv2
    arr = np.asarray(img.convert("L"))
    scale = MAX_SIDE / max(arr.shape)
    if scale < 1:
        arr = cv2.resize(arr, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    return arr


def features(img):
    import cv2
    sift = cv2.SIFT_create(nfeatures=3000)
    return sift.detectAndCompute(_gray(img), None)


def inliers(img_a, img_b, feats_a=None) -> int:
    """How many keypoints agree on one zoom+shift between the two images (0 = no match)."""
    import cv2
    kp_a, des_a = feats_a or features(img_a)
    kp_b, des_b = features(img_b)
    if des_a is None or des_b is None or len(kp_a) < 8 or len(kp_b) < 8:
        return 0
    pairs = cv2.BFMatcher(cv2.NORM_L2).knnMatch(des_a, des_b, k=2)
    good = [m for m, n in (p for p in pairs if len(p) == 2) if m.distance < 0.75 * n.distance]
    if len(good) < 8:
        return 0
    src = np.float32([kp_a[m.queryIdx].pt for m in good])
    dst = np.float32([kp_b[m.trainIdx].pt for m in good])
    M, mask = cv2.estimateAffinePartial2D(src, dst, method=cv2.RANSAC, ransacReprojThreshold=6.0)
    if M is None or mask is None:
        return 0
    scale = float(np.hypot(M[0, 0], M[1, 0]))
    angle = abs(float(np.degrees(np.arctan2(M[1, 0], M[0, 0]))))
    if not (0.2 < scale < 5.0) or angle > 10:  # Clash camera never rotates
        return 0
    return int(mask.sum())
