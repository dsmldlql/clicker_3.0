import cv2
import random
import os


class GPUAnalyzer:
  def __init__(self, base_dir=None):
    self.cache = {}
    if base_dir is None:
      base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    self.base_dir = base_dir

  def find_best_match(self, frame, templates, threshold, region=None):
    if region is not None:
      rx, ry, rw, rh = region
      if isinstance(frame, cv2.UMat):
        frame_np = frame.get()
        cropped_np = frame_np[ry:ry+rh, rx:rx+rw]
        search_frame = cv2.UMat(cropped_np)
      else:
        search_frame = frame[ry:ry+rh, rx:rx+rw]
    else:
      search_frame = frame

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

      res = cv2.matchTemplate(search_frame, temp, cv2.TM_CCOEFF_NORMED)
      _, max_val, _, max_loc = cv2.minMaxLoc(res)
      if max_val >= threshold:
        rand_offset_x = random.randint(-int(w//5), int(w//5)) if w > 5 else 0
        rand_offset_y = random.randint(-int(h//5), int(h//5)) if h > 5 else 0

        if region is not None:
          rx, ry, rw, rh = region
          full_x = max_loc[0] + w // 2 + rand_offset_x + rx
          full_y = max_loc[1] + h // 2 + rand_offset_y + ry
        else:
          full_x = max_loc[0] + w // 2 + rand_offset_x
          full_y = max_loc[1] + h // 2 + rand_offset_y

        return (full_x, full_y), max_val
    return None, 0
