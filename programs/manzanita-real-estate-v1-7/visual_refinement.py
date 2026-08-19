#!/usr/bin/env python3
from pathlib import Path

TARGET=Path('programs/manzanita-real-estate-v1-7/build_review.py')
text=TARGET.read_text(encoding='utf-8')
repls={
".hero-copy{position:absolute;left:clamp(22px,4vw,68px);bottom:clamp(62px,10vh,112px);max-width:min(720px,65vw);text-shadow:0 2px 28px rgba(0,0,0,.78)}":".hero-copy{position:absolute;left:clamp(22px,4vw,68px);bottom:clamp(58px,8vh,92px);max-width:min(570px,48vw);padding:18px 20px 20px;background:rgba(12,16,12,.58);backdrop-filter:blur(9px);border-left:3px solid var(--accent);text-shadow:0 2px 22px rgba(0,0,0,.72)}",
".hero h1{margin:0;max-width:700px;font-size:clamp(38px,5.3vw,78px);line-height:.92;letter-spacing:-.055em;font-weight:820}":".hero h1{margin:0;max-width:540px;font-size:clamp(36px,4.25vw,60px);line-height:.94;letter-spacing:-.05em;font-weight:820}",
".hero-copy>p:last-child{max-width:650px;margin:18px 0 0;font-size:clamp(16px,1.45vw,21px);line-height:1.5;color:#e7e2d6}":".hero-copy>p:last-child{max-width:520px;margin:14px 0 0;font-size:clamp(15px,1.15vw,18px);line-height:1.48;color:#e7e2d6}",
".hero-copy{left:16px;right:16px;bottom:170px;max-width:none}.hero h1{font-size:46px;max-width:500px}":".hero-copy{left:16px;right:16px;bottom:176px;max-width:none;padding:14px 15px}.hero h1{font-size:38px;max-width:430px}",
"let aperture='household',seat='resident',active=new Set();const q=new URLSearchParams(location.search);":"let aperture='household',seat='resident',active=new Set(['habitat','access']);const q=new URLSearchParams(location.search);",
}
changed=0
for old,new in repls.items():
    if old in text:
        text=text.replace(old,new,1); changed+=1
if changed < 5:
    raise SystemExit(f'Visual refinement patch drift: applied {changed}/5 replacements')
TARGET.write_text(text,encoding='utf-8')
print(f'Visual refinement applied: {changed}/5')
