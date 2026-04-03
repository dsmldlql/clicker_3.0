# Region Search Feature

## Overview

You can now specify a search region for template matching in scenario configurations. This helps avoid false positives when there are similar-looking buttons/elements on the screen.

## Configuration

Add a `region` field to any `expect` or `condition` block in `config_main.yaml`:

```yaml
state_name:
  expect:
    templates:
      - templates/chromium/gemini/more.png
    threshold: 0.7
    region: [x, y, width, height]  # Search only in this area
  action: click
  ...
```

## Region Format

The region is specified as a list of 4 integers:
- **x**: Left coordinate (pixels from left edge of screen)
- **y**: Top coordinate (pixels from top edge of screen)
- **width**: Width of the search area (pixels)
- **height**: Height of the search area (pixels)

Example: `region: [1700, 800, 200, 150]`
- Searches only in the rectangle starting at (1700, 800) with size 200x150 pixels

## Behavior

- **If `region` is specified**: Template matching is performed only within the specified rectangular area
- **If `region` is NOT specified**: Template matching searches the entire screen (default behavior, backward compatible)

## Use Cases

### Example 1: More button in Gemini
If the "more" button (3 dots) always appears in a specific area of the screen:

```yaml
find_copy_button:
  expect:
    templates:
      - templates/chromium/gemini/more.png
    threshold: 0.7
    region: [1700, 800, 200, 150]  # Only search in this area
  action: click
```

### Example 2: Condition with region
You can also specify regions for condition checks:

```yaml
answer_processing:
  expect:
    templates:
      - templates/chromium/gemini/voice_mode_0.png
    threshold: 0.7
  action: mousemove
  condition:
    templates:
      - templates/chromium/gemini/more.png
    threshold: 0.7
    region: [1700, 800, 200, 150]  # Check only in this area
```

## How to Find the Right Region

1. Take a screenshot of the bot in action
2. Identify the area where the button always appears
3. Measure the coordinates (x, y, width, height)
4. Add the `region` field to your config

You can use tools like:
- GNOME Screenshot with area selection
- `scrot -s` for interactive area selection
- Image editors to measure coordinates

## Backward Compatibility

All existing configurations without `region` field continue to work exactly as before. The feature is fully backward compatible.

## Notes

- Coordinates are in screen pixels (not relative)
- The region should be large enough to accommodate small variations in button position
- If the region is too small and the button is outside it, the match will fail
- Test thoroughly after adding regions to ensure they work correctly
