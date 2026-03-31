import cv2
import random
import os


class GPUAnalyzer:
    def __init__(self, base_dir=None):
        self.cache = {}
        self.counter = 0
        if base_dir is None:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.base_dir = base_dir

    def find_best_match(self, frame, templates, threshold):
        for path in templates:
            if not os.path.isabs(path):
                abs_path = os.path.join(self.base_dir, path)
            else:
                abs_path = path

            if abs_path not in self.cache:
                img = cv2.imread(abs_path, cv2.IMREAD_GRAYSCALE)
                if img is None:
                    continue
                img = cv2.Canny(img, 50, 150)
                self.cache[abs_path] = cv2.UMat(img)

            temp = self.cache[abs_path]
            h, w = temp.get().shape[:2]

            res = cv2.matchTemplate(frame, temp, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, max_loc = cv2.minMaxLoc(res)

            if max_val >= threshold:
                rand_offset_x = random.randint(-int(w//5), int(w//5)) if w > 5 else 0
                rand_offset_y = random.randint(-int(h//5), int(h//5)) if h > 5 else 0
                x = max_loc[0] + w // 2 + rand_offset_x
                y = max_loc[1] + h // 2 + rand_offset_y
                return (x, y), max_val

        return None, 0
