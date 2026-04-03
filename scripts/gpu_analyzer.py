import cv2
import random
import os

class GPUAnalyzer:
  def __init__(self, base_dir=None):
    self.cache = {}
    self.counter = 0
    # Базовая директория проекта для относительных путей
    if base_dir is None:
      base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    self.base_dir = base_dir

  def find_best_match(self, frame, templates, threshold, region=None):
    """
    Find best match for templates on the frame.

    Args:
      frame: The full screenshot frame (can be cv2.UMat or numpy array)
      templates: List of template paths to search for
      threshold: Match threshold
      region: Optional tuple (x, y, w, h) to limit search area.
              If None, searches the entire frame.
              Coordinates are relative to the full frame.

    Returns:
      Tuple of (coords, score) where coords are relative to the full frame.
    """
    # If region is specified, crop the frame
    if region is not None:
      rx, ry, rw, rh = region
      # Handle both cv2.UMat and numpy array
      if isinstance(frame, cv2.UMat):
        # For UMat, we need to use get() to convert to numpy, then crop, then convert back
        frame_np = frame.get()
        cropped_np = frame_np[ry:ry+rh, rx:rx+rw]
        search_frame = cv2.UMat(cropped_np)
      else:
        search_frame = frame[ry:ry+rh, rx:rx+rw]
    else:
      search_frame = frame
    
    print('Counter:', self.counter)
    for path in templates:
      # Преобразуем относительный путь в абсолютный
      if not os.path.isabs(path):
        abs_path = os.path.join(self.base_dir, path)
      else:
        abs_path = path
      
      if abs_path not in self.cache:
        # Загружаем шаблон в Ч/Б и сразу отправляем в VRAM (GPU)
        img = cv2.imread(abs_path, cv2.IMREAD_GRAYSCALE)
        if img is None:
          print(f"[!] Шаблон не загружен: {abs_path}")
          continue
        img = cv2.Canny(img, 50, 150)
        self.cache[abs_path] = cv2.UMat(img)
      temp = self.cache[abs_path]
      h, w = temp.get().shape[:2]

      # cv2.imwrite(f'{self.counter}_screenshot.png', frame)
      # cv2.imwrite(f'{self.counter}_template.png', temp)

      res = cv2.matchTemplate(search_frame, temp, cv2.TM_CCOEFF_NORMED)
      _, max_val, _, max_loc = cv2.minMaxLoc(res)
      print(f"Search {abs_path}")
      print(f"Max_loc {max_loc}, {max_val}")
      if max_val >= threshold:
        # 3. Сохранение
        # cv2.imwrite(f'{self.counter}_screenshot.png', frame)
        # cv2.imwrite(f'{self.counter}_template.png', temp)
        self.counter += 1

        # Calculate center position with random offset
        rand_offset_x = random.randint(-int(w//5), int(w//5)) if w > 5 else 0
        rand_offset_y = random.randint(-int(h//5), int(h//5)) if h > 5 else 0
        
        # If region was used, convert coordinates back to full frame
        if region is not None:
          rx, ry, rw, rh = region
          full_x = max_loc[0] + w // 2 + rand_offset_x + rx
          full_y = max_loc[1] + h // 2 + rand_offset_y + ry
        else:
          full_x = max_loc[0] + w // 2 + rand_offset_x
          full_y = max_loc[1] + h // 2 + rand_offset_y
        
        print(f"Found {abs_path}")
        print(f"Max_loc {full_x, full_y}")
        return (full_x, full_y), max_val
    return None, 0
