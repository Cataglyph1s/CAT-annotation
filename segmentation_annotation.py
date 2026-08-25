class SegmentationAnnotation:
    def __init__(self, points, class_num):
        self.points = list(points)  # [(x, y), ...] image pixel coords
        self.class_num = int(class_num)
        self.polygon_id = None
        self.text_id = None

    def to_normalized(self, img_width, img_height):
        coords = ' '.join(
            f'{x / img_width:.6f} {y / img_height:.6f}'
            for x, y in self.points
        )
        return f'{self.class_num} {coords}'

    @classmethod
    def from_normalized(cls, class_num, flat_coords, img_width, img_height):
        points = [
            (flat_coords[i] * img_width, flat_coords[i + 1] * img_height)
            for i in range(0, len(flat_coords) - 1, 2)
        ]
        return cls(points, int(class_num))

    def copy(self):
        ann = SegmentationAnnotation(list(self.points), self.class_num)
        ann.polygon_id = self.polygon_id
        ann.text_id = self.text_id
        return ann
