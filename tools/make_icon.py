# -*- coding: utf-8 -*-
"""生成应用图标 assets/app.ico（多尺寸，含 16/32/48/64/128/256）。"""
import os

from PIL import Image, ImageDraw

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   'assets', 'app.ico')


def make_icon(size):
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    # 圆角背景
    r = size // 5
    d.rounded_rectangle([0, 0, size - 1, size - 1], radius=r, fill=(41, 98, 255, 255))
    # 录制圆点（红）与回放三角（白）的组合：左红点右三角
    cx = size * 0.36
    cy = size * 0.5
    rr = size * 0.16
    d.ellipse([cx - rr, cy - rr, cx + rr, cy + rr], fill=(255, 82, 82, 255))
    # 白色播放三角
    p = size * 0.16
    d.polygon([(size * 0.58, size * 0.32), (size * 0.58, size * 0.68),
               (size * 0.82, size * 0.5)], fill=(255, 255, 255, 255))
    return img


def main():
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    sizes = [16, 32, 48, 64, 128, 256]
    images = [make_icon(s) for s in sizes]
    images[0].save(OUT, format='ICO', sizes=[(s, s) for s in sizes],
                   append_images=images[1:])
    print('已生成图标:', OUT)


if __name__ == '__main__':
    main()
