class BoundingBox:
    def __init__(self, x1, y1, x2, y2, class_num):
        self.x1 = x1
        self.y1 = y1
        self.x2 = x2
        self.y2 = y2
        self.class_num = class_num
        self.rect_id = None  # ID of the rectangle in the canvas
        self.text_id = None  # ID of the class label text in the canvas

    def to_normalized(self, img_width, img_height):
        x_center = (self.x1 + self.x2) / 2 / img_width
        y_center = (self.y1 + self.y2) / 2 / img_height
        width = abs(self.x2 - self.x1) / img_width
        height = abs(self.y2 - self.y1) / img_height
        return f"{self.class_num} {x_center} {y_center} {width} {height}"

    def copy(self):
        copied = BoundingBox(self.x1, self.y1, self.x2, self.y2, self.class_num)
        copied.rect_id = self.rect_id
        copied.text_id = self.text_id
        return copied

    @classmethod
    def from_normalized(cls, class_num, x_center, y_center, width, height, img_width, img_height):
        x1 = int((x_center - width / 2) * img_width)
        y1 = int((y_center - height / 2) * img_height)
        x2 = int((x_center + width / 2) * img_width)
        y2 = int((y_center + height / 2) * img_height)
        return cls(x1, y1, x2, y2, class_num)
