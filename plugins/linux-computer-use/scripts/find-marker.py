#!/usr/bin/python3
"""Locate the fixture's colored button in returned screenshot pixels."""
import io
import json
import sys
from PIL import Image
image = Image.open(io.BytesIO(sys.stdin.buffer.read())).convert('RGB')
step = 3
points = set()
for y in range(0, image.height, step):
    for x in range(0, image.width, step):
        r, g, b = image.getpixel((x, y))
        if abs(r - 233) < 5 and abs(g - 52) < 5 and abs(b - 188) < 5:
            points.add((x // step, y // step))
components = []
while points:
    seed = points.pop()
    group = [seed]
    todo = [seed]
    while todo:
        x, y = todo.pop()
        for p in [(x-1,y), (x+1,y), (x,y-1), (x,y+1)]:
            if p in points:
                points.remove(p)
                group.append(p)
                todo.append(p)
    if len(group) > 150:
        xs, ys = zip(*group)
        w, h = max(xs) - min(xs), max(ys) - min(ys)
        if h and 2 < w / h < 9:
            components.append((len(group), (min(xs) + max(xs)) * step / 2,
                               (min(ys) + max(ys)) * step / 2))
if not components:
    sys.exit('Test window marker not found. Select the monitor showing the Linux Computer Use Test window.')
_, x, y = max(components)
print(json.dumps({'x': x, 'y': y}))
