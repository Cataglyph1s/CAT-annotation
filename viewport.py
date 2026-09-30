def compute_axis(orig_dim, canvas_dim, scale_factor, view_center):
    """Compute the crop window and canvas offset for one axis of a
    zoomed/panned image viewport.

    Returns (crop_lo, crop_hi, offset):
      - crop_lo/crop_hi: the image-pixel range to crop from the original image.
      - offset: the canvas position of image-pixel 0 on this axis, i.e. the
        value to use as x_offset/y_offset so that
        canvas_coord = image_coord * scale_factor + offset
        stays valid for every other coordinate calculation in the app.

    If the image fits entirely within the canvas at this scale (the
    classic "fit to canvas" case, or a not-very-zoomed-in axis), the image
    is centered on this axis and view_center is ignored — matching the
    letterboxing behavior the app already had before zoom/pan existed.
    Otherwise, a canvas_dim/scale_factor-wide window centered on
    view_center is cropped, clamped so it never goes past the image edges.
    """
    if scale_factor <= 0 or orig_dim <= 0:
        return 0.0, float(orig_dim), 0.0

    visible_span = canvas_dim / scale_factor
    if visible_span >= orig_dim:
        crop_lo = 0.0
        offset = (canvas_dim - orig_dim * scale_factor) / 2
    else:
        crop_lo = view_center - visible_span / 2
        crop_lo = max(0.0, min(orig_dim - visible_span, crop_lo))
        offset = -crop_lo * scale_factor

    crop_hi = crop_lo + min(visible_span, orig_dim)
    return crop_lo, crop_hi, offset
