#!/usr/bin/env python3
"""Build an 8-wide thumbnail contact sheet from the AViDD-OSF YouTube channel.

Install: python3 -m pip install -U yt-dlp Pillow requests
Run:     python3 avidd_thumbnail_sheet.py
"""
from __future__ import annotations
import argparse
import csv
import io
import math
import re
import sys
from pathlib import Path

try:
    import requests
    from PIL import Image, ImageDraw, ImageFont, ImageOps
    import yt_dlp
except ImportError:
    sys.exit('Missing dependencies. Run: python3 -m pip install -U yt-dlp Pillow requests')

URL = 'https://www.youtube.com/@AViDD-OSF/videos'

def font(size: int, bold: bool = False):
    paths = (["/System/Library/Fonts/Supplemental/Arial Bold.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"] if bold else ["/System/Library/Fonts/Supplemental/Arial.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"])
    for p in paths:
        if Path(p).exists():
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()

def wrapped_lines(draw, s, f, limit, maxlines=3):
    words = re.sub(r'\s+', ' ', s).strip().split(' ')
    lines, line = [], ''
    for word in words:
        test = (line + ' ' + word).strip()
        if draw.textbbox((0,0), test, font=f)[2] <= limit or not line:
            line = test
        else:
            lines.append(line)
            line = word
    if line: lines.append(line)
    if len(lines) > maxlines:
        lines = lines[:maxlines]
        while lines[-1] and draw.textbbox((0,0), lines[-1] + '…', font=f)[2] > limit:
            lines[-1] = lines[-1][:-1]
        lines[-1] += '…'
    return lines

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--url', default=URL)
    ap.add_argument('--columns', type=int, default=8)
    ap.add_argument('--output', default='AViDD-OSF-thumbnails-8-wide.png')
    ap.add_argument('--max-videos', type=int, default=0, help='0 means all videos')
    args = ap.parse_args()
    print('Retrieving channel video list…', flush=True)
    opts = {'quiet': True, 'no_warnings': True, 'extract_flat': 'in_playlist', 'skip_download': True, 'ignoreerrors': True, 'playlistend': args.max_videos or None}
    with yt_dlp.YoutubeDL(opts) as ydl:
        data = ydl.extract_info(args.url, download=False)
    entries = [v for v in data.get('entries', []) if v and (v.get('id') or v.get('url'))]
    if not entries:
        sys.exit('Could not retrieve channel videos. Update yt-dlp and retry: python3 -m pip install -U yt-dlp')
    print(f'Found {len(entries)} videos. Downloading thumbnails…', flush=True)
    session = requests.Session()
    session.headers.update({'User-Agent': 'Mozilla/5.0'})
    images = []
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    csv_path = output.with_suffix('.csv')
    with csv_path.open('w', newline='', encoding='utf-8') as fp:
        writer = csv.writer(fp)
        writer.writerow(['position','title','url','thumbnail_retrieved'])
        for k,v in enumerate(entries, 1):
            vid = v.get('id', '')
            if not vid and v.get('url'):
                vid = v['url'].rsplit('=',1)[-1]
            title = v.get('title') or f'Video {k}'
            watch = f'https://www.youtube.com/watch?v={vid}'
            candidates = [f'https://i.ytimg.com/vi/{vid}/hqdefault.jpg', f'https://i.ytimg.com/vi/{vid}/mqdefault.jpg']
            candidates += [t['url'] for t in (v.get('thumbnails') or []) if t.get('url')]
            img = None
            for candidate in candidates:
                try:
                    res = session.get(candidate, timeout=12)
                    res.raise_for_status()
                    candidate_img = Image.open(io.BytesIO(res.content)).convert('RGB')
                    if candidate_img.width >= 240:
                        img = candidate_img
                        break
                except Exception: pass
            images.append((title, img, watch))
            writer.writerow([k, title, watch, bool(img)])
            print(f'{k}/{len(entries)}: {title[:58]}', flush=True)

    cols = args.columns
    tile_w, tile_h, gap, pad = 320, 256, 16, 24
    thumb_h = 180
    header = 112
    rows = math.ceil(len(images) / cols)
    W = pad * 2 + cols * tile_w + (cols - 1) * gap
    H = header + pad + rows * tile_h + max(0, rows - 1) * gap + pad
    page = Image.new('RGB',(W,H),'#f6f8fb')
    d=ImageDraw.Draw(page)
    d.text((pad,23),'AViDD Open Science Forum',font=font(40,True),fill='#16233b')
    d.text((pad,76),f'{len(images)} videos  •  {cols} thumbnails per row  •  youtube.com/@AViDD-OSF',font=font(20),fill='#526076')
    f=font(18,True)
    small=font(15)
    for i,(title,img,watch) in enumerate(images):
        x=pad+(i%cols)*(tile_w+gap)
        y=header+pad+(i//cols)*(tile_h+gap)
        d.rounded_rectangle((x,y,x+tile_w,y+tile_h),radius=10,fill='white',outline='#dfe5ed',width=2)
        if img is not None:
            crop=ImageOps.fit(img,(tile_w,thumb_h),method=Image.Resampling.LANCZOS,centering=(.5,.5))
            page.paste(crop,(x,y))
        else:
            d.rectangle((x,y,x+tile_w,y+thumb_h),fill='#dce2e9')
            d.text((x+20,y+70),'Thumbnail unavailable',font=small,fill='#46566d')
        d.rectangle((x+8,y+8,x+45,y+33),fill='#152238')
        d.text((x+14,y+11),str(i+1),font=small,fill='white')
        for j,line in enumerate(wrapped_lines(d,title,f,tile_w-20,3)):
            d.text((x+10,y+thumb_h+8+j*22),line,font=f,fill='#1b283b')
    page.save(output,optimize=True)
    print(f'Created {output} ({W}×{H}) and {csv_path}', flush=True)

if __name__=='__main__':
    main()
