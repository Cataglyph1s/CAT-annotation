import os
import json

import numpy as np
import cv2


DEFAULT_INPUT_SIZE = 640
DEFAULT_CONF_THRESHOLD = 0.25
DEFAULT_IOU_THRESHOLD = 0.45
DEFAULT_BOX_FORMAT = 'cxcywh'
MASK_THRESHOLD = 0.5


class Detection:
    """One predicted instance: box is (x1, y1, x2, y2) in original-image pixel
    coordinates. polygon (segment models only) is a flat list of (x, y) points,
    also in original-image pixel coordinates."""

    def __init__(self, class_id, confidence, box, polygon=None):
        self.class_id = class_id
        self.confidence = confidence
        self.box = box
        self.polygon = polygon


class OnnxYoloModel:
    """Runs a YOLOv8/v9/v11-style ONNX export (Ultralytics format) via
    cv2.dnn — detect or segment, auto-detected from the model's own output
    count (1 output = detect, 2 outputs = segment/one is the mask proto).
    No PyTorch/Ultralytics dependency; works with the OpenCV already used
    elsewhere in this app."""

    def __init__(self, net, task, input_size, conf_threshold, iou_threshold,
                 box_format=DEFAULT_BOX_FORMAT):
        self.net = net
        self.task = task  # 'detect' or 'segment'
        self.input_size = input_size
        self.conf_threshold = conf_threshold
        self.iou_threshold = iou_threshold
        self.box_format = box_format  # 'cxcywh' (standard YOLO raw export) or 'xyxy'
        self.n_classes = None  # known after the first predict() call

    @classmethod
    def load(cls, model_path):
        try:
            net = cv2.dnn.readNetFromONNX(model_path)
        except Exception as e:
            msg = str(e)
            if 'TopK' in msg or 'NonMaxSuppression' in msg or 'EfficientNMS' in msg:
                raise RuntimeError(
                    "This model has NMS baked into the ONNX graph itself (an "
                    "'end-to-end' export) — OpenCV's cv2.dnn can't import that "
                    "(TopK/NonMaxSuppression ops aren't supported), and re-exporting "
                    "with nms=False does NOT fix this for architectures where the "
                    "TopK head is part of the model itself, not an optional export "
                    "flag. Use SamiraYoloTrainingScripts/conversion_scripts/"
                    "export_for_catannotation.py instead of a plain model.export(...) "
                    "— it detects and works around this automatically.\n\n"
                    f"Original error:\n{msg}") from e
            raise

        config = {}
        sidecar_path = model_path + '.json'
        if os.path.exists(sidecar_path):
            with open(sidecar_path, 'r') as f:
                config = json.load(f)

        input_size = int(config.get('input_size', DEFAULT_INPUT_SIZE))
        conf_threshold = float(config.get('conf_threshold', DEFAULT_CONF_THRESHOLD))
        iou_threshold = float(config.get('iou_threshold', DEFAULT_IOU_THRESHOLD))
        box_format = config.get('box_format', DEFAULT_BOX_FORMAT)

        n_outputs = len(net.getUnconnectedOutLayersNames())
        task = 'segment' if n_outputs >= 2 else 'detect'

        return cls(net, task, input_size, conf_threshold, iou_threshold, box_format)

    def predict(self, pil_image):
        """pil_image: a PIL.Image (any mode). Returns a list of Detection."""
        image = np.array(pil_image.convert('RGB'))
        orig_h, orig_w = image.shape[:2]

        padded, scale, pad_left, pad_top = self._letterbox(image, self.input_size)
        blob = cv2.dnn.blobFromImage(padded, scalefactor=1.0 / 255.0,
                                      size=(self.input_size, self.input_size),
                                      swapRB=False, crop=False)
        self.net.setInput(blob)
        outputs = self.net.forward(self.net.getUnconnectedOutLayersNames())

        if self.task == 'segment':
            return self._decode_segment(outputs, scale, pad_left, pad_top, orig_w, orig_h)
        return self._decode_detect(outputs, scale, pad_left, pad_top, orig_w, orig_h)

    # ------------------------------------------------------------------
    # Preprocessing
    # ------------------------------------------------------------------

    @staticmethod
    def _letterbox(image, new_size):
        """Resize preserving aspect ratio, pad to a (new_size, new_size)
        square with grey — matches Ultralytics' own preprocessing, which
        the ONNX export's input coordinates assume."""
        h, w = image.shape[:2]
        scale = min(new_size / h, new_size / w)
        new_unpad_w, new_unpad_h = int(round(w * scale)), int(round(h * scale))
        resized = cv2.resize(image, (new_unpad_w, new_unpad_h), interpolation=cv2.INTER_LINEAR)

        pad_w = new_size - new_unpad_w
        pad_h = new_size - new_unpad_h
        top, bottom = pad_h // 2, pad_h - pad_h // 2
        left, right = pad_w // 2, pad_w - pad_w // 2
        padded = cv2.copyMakeBorder(resized, top, bottom, left, right,
                                     cv2.BORDER_CONSTANT, value=(114, 114, 114))
        return padded, scale, left, top

    # ------------------------------------------------------------------
    # Postprocessing
    # ------------------------------------------------------------------

    def _box4_to_xyxy(self, a, b, c, d):
        """Convert a raw 4-column box (still in letterboxed input-pixel
        space) to (x1,y1,x2,y2), honoring self.box_format. Different export
        paths for the same architecture have been observed to disagree on
        whether these 4 columns are center+size or corner coordinates —
        confirmed by comparing decoded boxes against the source .pt model's
        own predictions, not assumed (see export_for_catannotation.py)."""
        if self.box_format == 'xyxy':
            return a, b, c, d
        return a - c / 2, b - d / 2, a + c / 2, b + d / 2

    def _raw_boxes_and_classes(self, pred):
        """pred: (N, 4+nc[+32]) array, box coords (format per self.box_format)
        in letterboxed input-pixel space followed by per-class scores (and
        mask coeffs for segment models, left untouched here). Returns
        xywh-format boxes (x,y = top-left), as cv2.dnn.NMSBoxes expects."""
        x1, y1, x2, y2 = self._box4_to_xyxy(pred[:, 0], pred[:, 1], pred[:, 2], pred[:, 3])
        boxes_xywh = np.stack([x1, y1, x2 - x1, y2 - y1], axis=1)
        return boxes_xywh

    def _nms(self, boxes_xywh, confidences):
        boxes_list = boxes_xywh.tolist()
        scores_list = confidences.tolist()
        indices = cv2.dnn.NMSBoxes(boxes_list, scores_list, self.conf_threshold, self.iou_threshold)
        if len(indices) == 0:
            return []
        return np.array(indices).reshape(-1)

    def _invert_letterbox_box(self, x1, y1, x2, y2, scale, pad_left, pad_top, orig_w, orig_h):
        ox1 = (x1 - pad_left) / scale
        oy1 = (y1 - pad_top) / scale
        ox2 = (x2 - pad_left) / scale
        oy2 = (y2 - pad_top) / scale
        ox1 = max(0.0, min(orig_w, ox1))
        oy1 = max(0.0, min(orig_h, oy1))
        ox2 = max(0.0, min(orig_w, ox2))
        oy2 = max(0.0, min(orig_h, oy2))
        return ox1, oy1, ox2, oy2

    @staticmethod
    def _to_anchor_major(arr):
        """Normalize a 2D (channels, anchors) or (anchors, channels) array to
        (anchors, channels). Different Ultralytics export paths disagree on
        which axis comes first (plain YOLOv8-style raw exports are
        channel-major; some newer/graph-surgered exports are already
        anchor-major) — channel count (4+nc[+32]) is always far smaller than
        the anchor count (thousands), so that's a reliable way to tell them
        apart without needing to know which export produced a given file."""
        if arr.shape[0] < arr.shape[1]:
            return arr.T
        return arr

    @staticmethod
    def _looks_like_score_classid(column):
        """True if a column's values are all (near-)whole numbers — the
        signature of an explicit class-id column, as opposed to a genuine
        per-class probability (which essentially never lands exactly on an
        integer)."""
        return np.allclose(column, np.round(column), atol=1e-3)

    def _decode_detect(self, outputs, scale, pad_left, pad_top, orig_w, orig_h):
        pred = self._to_anchor_major(outputs[0][0])  # (N, C)
        n_extra = pred.shape[1] - 4

        if n_extra == 2 and self._looks_like_score_classid(pred[:, 5]):
            # Some newer NMS-free heads (seen with this project's yolo26
            # detect export, when it loads without needing the graph-surgery
            # fallback) declare their FINAL output already decoded as
            # [cx,cy,w,h,score,class_id] — a single confidence plus an
            # explicit class id — rather than one score per class. There's
            # no per-class vector to argmax here, and no NMS to re-run
            # either: a one-to-one-assignment / NMS-free head is trained
            # specifically so its own top-K selection doesn't need it.
            self.n_classes = None  # not knowable from this output shape alone
            confidences = pred[:, 4]
            class_ids = np.round(pred[:, 5]).astype(int)
            keep = confidences >= self.conf_threshold
            detections = []
            for i in np.nonzero(keep)[0]:
                lx1, ly1, lx2, ly2 = self._box4_to_xyxy(*pred[i, :4])
                ox1, oy1, ox2, oy2 = self._invert_letterbox_box(
                    lx1, ly1, lx2, ly2, scale, pad_left, pad_top, orig_w, orig_h)
                detections.append(Detection(int(class_ids[i]), float(confidences[i]),
                                             (ox1, oy1, ox2, oy2)))
            return detections

        self.n_classes = n_extra
        class_scores = pred[:, 4:]
        class_ids = np.argmax(class_scores, axis=1)
        confidences = np.max(class_scores, axis=1)

        keep = confidences >= self.conf_threshold
        if not np.any(keep):
            return []
        pred, class_ids, confidences = pred[keep], class_ids[keep], confidences[keep]

        boxes_xywh = self._raw_boxes_and_classes(pred)
        nms_idx = self._nms(boxes_xywh, confidences)

        detections = []
        for i in nms_idx:
            x, y, w, h = boxes_xywh[i]
            ox1, oy1, ox2, oy2 = self._invert_letterbox_box(
                x, y, x + w, y + h, scale, pad_left, pad_top, orig_w, orig_h)
            detections.append(Detection(int(class_ids[i]), float(confidences[i]),
                                         (ox1, oy1, ox2, oy2)))
        return detections

    def _decode_segment(self, outputs, scale, pad_left, pad_top, orig_w, orig_h):
        pred = proto = None
        for out in outputs:
            if out.ndim == 4:
                proto = out[0]  # (32, proto_h, proto_w)
            else:
                pred = out[0]  # (4+nc+32, N)
        if pred is None or proto is None:
            return []

        pred = self._to_anchor_major(pred)  # (N, 4+nc+32)
        n_mask = proto.shape[0]
        n_classes = pred.shape[1] - 4 - n_mask
        self.n_classes = n_classes
        class_scores = pred[:, 4:4 + n_classes]
        mask_coeffs = pred[:, 4 + n_classes:]
        class_ids = np.argmax(class_scores, axis=1)
        confidences = np.max(class_scores, axis=1)

        keep = confidences >= self.conf_threshold
        if not np.any(keep):
            return []
        pred, class_ids, confidences, mask_coeffs = (
            pred[keep], class_ids[keep], confidences[keep], mask_coeffs[keep])

        boxes_xywh = self._raw_boxes_and_classes(pred)
        nms_idx = self._nms(boxes_xywh, confidences)

        proto_c, proto_h, proto_w = proto.shape
        proto_flat = proto.reshape(proto_c, -1)

        detections = []
        for i in nms_idx:
            x, y, w, h = boxes_xywh[i]
            lx1, ly1, lx2, ly2 = x, y, x + w, y + h  # letterboxed-space box

            mask = 1.0 / (1.0 + np.exp(-(mask_coeffs[i] @ proto_flat)))
            mask = mask.reshape(proto_h, proto_w)
            mask = cv2.resize(mask, (self.input_size, self.input_size), interpolation=cv2.INTER_LINEAR)

            clx1, cly1 = max(0, int(round(lx1))), max(0, int(round(ly1)))
            clx2 = min(self.input_size, max(clx1 + 1, int(round(lx2))))
            cly2 = min(self.input_size, max(cly1 + 1, int(round(ly2))))
            mask_crop = mask[cly1:cly2, clx1:clx2]

            ox1, oy1, ox2, oy2 = self._invert_letterbox_box(
                lx1, ly1, lx2, ly2, scale, pad_left, pad_top, orig_w, orig_h)
            box_w, box_h = max(1, int(round(ox2 - ox1))), max(1, int(round(oy2 - oy1)))
            if mask_crop.size == 0:
                continue
            mask_resized = cv2.resize(mask_crop, (box_w, box_h), interpolation=cv2.INTER_LINEAR)
            mask_bin = (mask_resized >= MASK_THRESHOLD).astype(np.uint8) * 255

            contours, _ = cv2.findContours(mask_bin, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            contours = [c for c in contours if len(c) >= 3]
            if not contours:
                continue
            largest = max(contours, key=cv2.contourArea).reshape(-1, 2)
            polygon = [(float(px) + ox1, float(py) + oy1) for px, py in largest]

            detections.append(Detection(int(class_ids[i]), float(confidences[i]),
                                         (ox1, oy1, ox2, oy2), polygon=polygon))
        return detections
