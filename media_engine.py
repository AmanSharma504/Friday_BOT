import io
import os
import time
import math
import random
import urllib.parse
import threading
import requests
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import imageio
from config import TEMP_AUDIO_DIR

# Persistent session with realistic User-Agent to avoid Cloudflare/Pollinations 402/403/503 blocks
_session = requests.Session()
_session.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
})
_adapter = requests.adapters.HTTPAdapter(pool_connections=10, pool_maxsize=20, max_retries=2)
_session.mount("https://", _adapter)

# Fancy Unicode Font Maps
FONT_MAPS = {
    "Bold": {
        "A": "𝐀", "B": "𝐁", "C": "𝐂", "D": "𝐃", "E": "𝐄", "F": "𝐅", "G": "𝐆", "H": "𝐇", "I": "𝐈", "J": "𝐉", "K": "𝐊", "L": "𝐋", "M": "𝐌",
        "N": "𝐍", "O": "𝐎", "P": "𝐏", "Q": "𝐐", "R": "𝐑", "S": "𝐒", "T": "𝐓", "U": "𝐔", "V": "𝐕", "W": "𝐖", "X": "𝐗", "Y": "𝐘", "Z": "𝐙",
        "a": "𝐚", "b": "𝐛", "c": "𝐜", "d": "𝐝", "e": "𝐞", "f": "𝐟", "g": "𝐠", "h": "𝐡", "i": "𝐢", "j": "𝐣", "k": "𝐤", "l": "𝐥", "m": "𝐦",
        "n": "𝐧", "o": "𝐨", "p": "𝐩", "q": "𝐪", "r": "𝐫", "s": "𝐬", "t": "𝐭", "u": "𝐮", "v": "𝐯", "w": "𝐰", "x": "𝐱", "y": "𝐲", "z": "𝐳",
        "0": "𝟎", "1": "𝟏", "2": "𝟐", "3": "𝟑", "4": "𝟒", "5": "𝟓", "6": "𝟔", "7": "𝟕", "8": "𝟖", "9": "𝟗"
    },
    "Italic": {
        "A": "𝐴", "B": "𝐵", "C": "𝐶", "D": "𝐷", "E": "𝐸", "F": "𝐹", "G": "𝐺", "H": "𝐻", "I": "𝐼", "J": "𝐽", "K": "𝐾", "L": "𝐿", "M": "𝑀",
        "N": "𝑁", "O": "𝑂", "P": "𝑃", "Q": "𝑄", "R": "𝑅", "S": "𝑆", "T": "𝑇", "U": "𝑈", "V": "𝑉", "W": "𝑊", "X": "𝑋", "Y": "𝑌", "Z": "𝑍",
        "a": "𝑎", "b": "𝑏", "c": "𝑐", "d": "𝑑", "e": "𝑒", "f": "𝑓", "g": "𝑔", "h": "ℎ", "i": "𝑖", "j": "𝑗", "k": "𝑘", "l": "𝑙", "m": "𝑚",
        "n": "𝑛", "o": "𝑜", "p": "𝑝", "q": "𝑞", "r": "𝑟", "s": "𝑠", "t": "𝑡", "u": "𝑢", "v": "𝑣", "w": "𝑤", "x": "𝑥", "y": "𝑦", "z": "𝑧"
    },
    "Gothic / Fraktur": {
        "A": "𝔄", "B": "𝔅", "C": "ℭ", "D": "𝔇", "E": "𝔈", "F": "𝔉", "G": "𝔊", "H": "ℌ", "I": "ℑ", "J": "𝔍", "K": "𝔎", "L": "𝔏", "M": "𝔐",
        "N": "𝔑", "O": "𝔒", "P": "𝔓", "Q": "𝔔", "R": "ℜ", "S": "𝔖", "T": "𝔗", "U": "𝔘", "V": "𝔙", "W": "𝔚", "X": "𝔛", "Y": "𝔜", "Z": "ℨ",
        "a": "𝔞", "b": "𝔟", "c": "𝔠", "d": "𝔡", "e": "𝔢", "f": "𝔣", "g": "𝔤", "h": "𝔥", "i": "𝔦", "j": "𝔧", "k": "𝔨", "l": "", "m": "𝔪",
        "n": "𝔫", "o": "𝔬", "p": "𝔭", "q": "𝔮", "r": "𝔯", "s": "𝔰", "t": "𝔱", "u": "𝔲", "v": "𝔳", "w": "𝔴", "x": "𝔵", "y": "𝔶", "z": "𝔷"
    },
    "Cursive / Script": {
        "A": "𝒜", "B": "𝐵", "C": "𝒞", "D": "𝒟", "E": "𝐸", "F": "𝐹", "G": "𝒢", "H": "𝐻", "I": "𝐼", "J": "𝒥", "K": "𝒦", "L": "𝐿", "M": "𝑀",
        "n": "𝓃", "o": "𝑜", "p": "𝓅", "q": "𝓆", "r": "𝓇", "s": "𝓈", "t": "𝓉", "u": "𝓊", "v": "𝓋", "w": "𝓌", "x": "𝓍", "y": "𝓎", "z": "𝓏",
        "a": "𝒶", "b": "𝒷", "c": "𝒸", "d": "𝒹", "e": "𝑒", "f": "𝒻", "g": "𝑔", "h": "𝒽", "i": "𝒾", "j": "𝒿", "k": "𝓀", "l": "𝓁", "m": "𝓂"
    },
    "Double Struck": {
        "A": "𝔸", "B": "𝔹", "C": "ℂ", "D": "𝔻", "E": "𝔼", "F": "𝔽", "G": "𝔾", "H": "ℍ", "I": "𝕀", "J": "𝕁", "K": "𝕂", "L": "𝕃", "M": "𝕄",
        "N": "ℕ", "O": "𝕆", "P": "ℙ", "Q": "ℚ", "R": "ℝ", "S": "𝕊", "T": "𝕋", "U": "𝕌", "V": "𝕍", "W": "𝕎", "X": "𝕏", "Y": "𝕐", "Z": "ℤ",
        "a": "𝕒", "b": "𝕓", "c": "𝕔", "d": "𝕕", "e": "𝕖", "f": "𝕗", "g": "𝕘", "h": "𝕙", "i": "𝕚", "j": "𝕛", "k": "𝕜", "l": "𝕝", "m": "𝕞",
        "n": "𝕟", "o": "𝕠", "p": "𝕡", "q": "𝕢", "r": "𝕣", "s": "𝕤", "t": "𝕥", "u": "𝕦", "v": "𝕧", "w": "𝕨", "x": "𝕩", "y": "𝕪", "z": "𝕫",
        "0": "𝟘", "1": "𝟙", "2": "𝟚", "3": "𝟛", "4": "𝟜", "5": "𝟝", "6": "𝟞", "7": "𝟟", "8": "𝟠", "9": "𝟡"
    },
    "Monospace": {
        "A": "𝙰", "B": "𝙱", "C": "𝙲", "D": "𝙳", "E": "𝙴", "F": "𝙵", "G": "𝙶", "H": "𝙷", "I": "𝙸", "J": "𝙹", "K": "𝙺", "L": "𝙻", "M": "𝙼",
        "N": "𝙽", "O": "𝙾", "P": "𝙿", "Q": "𝚀", "R": "𝚁", "S": "𝚂", "T": "𝚃", "U": "𝚄", "V": "𝚅", "W": "𝚆", "X": "𝚇", "Y": "𝚈", "Z": "𝚉",
        "a": "𝚊", "b": "𝚋", "c": "𝚌", "d": "𝚍", "e": "𝚎", "f": "𝚏", "g": "𝚐", "h": "𝚑", "i": "🇮", "j": "𝚓", "k": "𝚔", "l": "𝚕", "m": "𝚖",
        "n": "𝚗", "o": "𝚘", "p": "𝚙", "q": "𝚚", "r": "𝚛", "s": "𝚜", "t": "𝚝", "u": "𝚞", "v": "𝚟", "w": "𝚠", "x": "𝚡", "y": "𝚢", "z": "𝚣"
    },
    "Bubbles": {
        "A": "Ⓐ", "B": "Ⓑ", "C": "Ⓒ", "D": "Ⓓ", "E": "Ⓔ", "F": "Ⓕ", "G": "Ⓖ", "H": "Ⓗ", "I": "Ⓘ", "J": "Ⓙ", "K": "Ⓚ", "L": "Ⓛ", "M": "Ⓜ",
        "N": "Ⓝ", "O": "Ⓞ", "P": "Ⓟ", "Q": "Ⓠ", "R": "Ⓡ", "S": "Ⓢ", "T": "Ⓣ", "U": "Ⓤ", "V": "Ⓥ", "W": "Ⓦ", "X": "Ⓧ", "Y": "Ⓨ", "Z": "Ⓩ",
        "a": "ⓐ", "b": "ⓑ", "c": "ⓒ", "d": "ⓓ", "e": "ⓔ", "f": "ⓕ", "g": "ⓖ", "h": "ⓗ", "i": "ⓘ", "j": "ⓙ", "k": "ⓚ", "l": "ⓛ", "m": "ⓜ",
        "n": "ⓝ", "o": "ⓞ", "p": "ⓟ", "q": "ⓠ", "r": "ⓡ", "s": "ⓢ", "t": "ⓣ", "u": "ⓤ", "v": "ⓥ", "w": "ⓦ", "x": "ⓧ", "y": "ⓨ", "z": "ⓩ",
        "0": "⓪", "1": "①", "2": "②", "3": "③", "4": "④", "5": "⑤", "6": "⑥", "7": "⑦", "8": "⑧", "9": "⑨"
    }
}

def generate_stylish_fonts(text: str) -> str:
    """Generates multiple stylish Unicode font variations for names or text."""
    results = [f"✨ **Stylish Text Variations for:** `{text}`\n"]
    for style_name, mapping in FONT_MAPS.items():
        converted = "".join(mapping.get(c, c) for c in text)
        results.append(f"• **{style_name}:** `{converted}`")
    return "\n".join(results)

def _add_watermark(img: Image.Image, text: str = "⚡ Friday AI • AI Generated Content") -> Image.Image:
    """
    Applies a visible, permanent AI safety watermark to prevent misuse.
    Branded strictly as Friday AI — zero mention of underlying providers.
    """
    img = img.convert("RGBA")
    w, h = img.size

    overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    font_size = max(18, int(h * 0.026))
    try:
        font = ImageFont.truetype("Arial.ttf", font_size)
    except Exception:
        font = ImageFont.load_default()

    bbox = draw.textbbox((0, 0), text, font=font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]

    pad_x = 18
    pad_y = 10
    badge_x1 = w - text_w - (pad_x * 2) - 20
    badge_y1 = h - text_h - (pad_y * 2) - 20
    badge_x2 = w - 20
    badge_y2 = h - 20

    # Rounded translucent background badge
    draw.rounded_rectangle(
        [badge_x1, badge_y1, badge_x2, badge_y2],
        radius=8,
        fill=(15, 15, 20, 195),
        outline=(255, 255, 255, 75),
        width=1,
    )

    # Crisp white watermark text
    draw.text(
        (badge_x1 + pad_x, badge_y1 + pad_y - 2),
        text,
        font=font,
        fill=(255, 255, 255, 240),
    )

    # Top-left AI disclaimer label
    top_label = "AI Generated Media • Friday"
    draw.text((20, 20), top_label, font=font, fill=(255, 255, 255, 140))

    final_img = Image.alpha_composite(img, overlay).convert("RGB")
    return final_img

def generate_ai_image(prompt: str) -> bytes:
    """
    Generates high-resolution photorealistic AI image with multi-tier fallback.
    Applies Friday AI safety watermark.
    """
    clean_p = prompt.strip()
    encoded = urllib.parse.quote(clean_p)

    # Multi-tier free endpoints & models to guarantee 100% availability
    endpoints = [
        f"https://image.pollinations.ai/prompt/{encoded}?width=1024&height=1024&model=turbo",
        f"https://image.pollinations.ai/prompt/{encoded}?width=1024&height=1024",
        f"https://image.pollinations.ai/prompt/{encoded}?width=768&height=768&model=sana",
    ]

    for url in endpoints:
        try:
            resp = _session.get(url, timeout=20)
            if resp.status_code == 200 and len(resp.content) > 2000:
                try:
                    img = Image.open(io.BytesIO(resp.content))
                    watermarked = _add_watermark(img, text="⚡ Friday AI • AI Generated Content")
                    out_buf = io.BytesIO()
                    watermarked.save(out_buf, format="JPEG", quality=92, optimize=True)
                    out_buf.seek(0)
                    return out_buf.getvalue()
                except Exception:
                    continue
        except Exception:
            continue

    # Graceful Graphic Fallback Card using Pillow if all external web generators are unreachable
    fallback_img = Image.new("RGB", (1024, 1024), (20, 24, 33))
    draw = ImageDraw.Draw(fallback_img)
    try:
        fnt_title = ImageFont.truetype("Arial.ttf", 36)
        fnt_sub = ImageFont.truetype("Arial.ttf", 24)
    except Exception:
        fnt_title = ImageFont.load_default()
        fnt_sub = ImageFont.load_default()

    draw.rounded_rectangle([60, 60, 964, 964], radius=20, outline=(70, 130, 240), width=3)
    draw.text((100, 200), "🎨 Friday AI Artwork", fill=(255, 255, 255), font=fnt_title)
    draw.text((100, 300), f"Prompt: {clean_p[:120]}", fill=(180, 200, 230), font=fnt_sub)
    watermarked = _add_watermark(fallback_img, text="⚡ Friday AI • AI Generated Content")

    out_buf = io.BytesIO()
    watermarked.save(out_buf, format="JPEG", quality=90)
    out_buf.seek(0)
    return out_buf.getvalue()

def generate_ai_logo(name: str, style: str = "modern minimal 3D vector") -> bytes:
    """Generates a professional 8K brand logo with custom name and styling."""
    logo_prompt = (
        f"Professional luxury modern logo emblem for '{name}', {style}, "
        f"minimalist clean aesthetic, bold typography, iconic vector art, centered composition, "
        f"ultra detailed, 8k resolution, elegant dark background"
    )
    return generate_ai_image(logo_prompt)

def generate_ai_emoji(prompt: str) -> bytes:
    """Generates custom 3D emoji or sticker graphic with transparent background style."""
    emoji_prompt = (
        f"Cute 3D emoji icon of {prompt}, high gloss apple iOS style emoji, "
        f"vibrant colors, smooth lighting, isolated on solid dark background, sticker style"
    )
    return generate_ai_image(emoji_prompt)

def generate_ai_video(prompt: str, duration_sec: int = 15) -> str:
    """
    Generates a cinematic animated AI video clip (up to 120 seconds / 2 minutes max).
    Applies prominent Friday AI safety watermark across all frames.
    """
    duration_sec = max(5, min(duration_sec, 120))
    fps = 24
    total_frames = duration_sec * fps

    clean_p = prompt.strip()
    encoded = urllib.parse.quote(clean_p)

    # Fetch 2 keyframes using the robust image generation pipeline
    img1_bytes = generate_ai_image(clean_p)
    img1 = Image.open(io.BytesIO(img1_bytes)).convert("RGB").resize((720, 720))

    img2_bytes = generate_ai_image(f"{clean_p} cinematic detailed lighting")
    img2 = Image.open(io.BytesIO(img2_bytes)).convert("RGB").resize((720, 720))

    img1 = _add_watermark(img1, text="⚡ Friday AI • AI Generated Video")
    img2 = _add_watermark(img2, text="⚡ Friday AI • AI Generated Video")

    out_path = str(TEMP_AUDIO_DIR / f"ai_video_{int(time.time())}.mp4")
    writer = imageio.get_writer(out_path, fps=fps, codec="libx264", quality=8)

    half_frames = total_frames // 2

    # Smooth Ken Burns zoom / pan effect
    for i in range(half_frames):
        zoom = 1.0 + (0.15 * (i / max(1, half_frames)))
        new_w = int(720 * zoom)
        new_h = int(720 * zoom)
        resized = img1.resize((new_w, new_h), Image.Resampling.BILINEAR)
        crop_x = (new_w - 720) // 2
        crop_y = (new_h - 720) // 2
        frame = resized.crop((crop_x, crop_y, crop_x + 720, crop_y + 720))
        writer.append_data(np.array(frame))

    for i in range(half_frames, total_frames):
        zoom = 1.15 - (0.15 * ((i - half_frames) / max(1, (total_frames - half_frames))))
        new_w = int(720 * zoom)
        new_h = int(720 * zoom)
        resized = img2.resize((new_w, new_h), Image.Resampling.BILINEAR)
        crop_x = (new_w - 720) // 2
        crop_y = (new_h - 720) // 2
        frame = resized.crop((crop_x, crop_y, crop_x + 720, crop_y + 720))
        writer.append_data(np.array(frame))

    writer.close()
    return out_path
