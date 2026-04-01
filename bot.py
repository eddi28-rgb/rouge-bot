import os
from pathlib import Path

import discord
from discord.ext import commands
from PIL import Image, ImageDraw, ImageFont
from moviepy import CompositeVideoClip, ImageClip, VideoFileClip

TOKEN = os.environ["DISCORD_TOKEN"]
WATERMARK_TEXT = "YARRAK"
WORKDIR = Path("discord_bot/temp_files")

intents = discord.Intents.default()
intents.message_content = True
intents.messages = True

bot = commands.Bot(command_prefix="!", intents=intents)


def get_font(font_size: int) -> ImageFont.ImageFont:
    for font_name in ("arial.ttf", "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(font_name, font_size)
        except OSError:
            continue
    return ImageFont.load_default()


def create_text_overlay(size: tuple[int, int]) -> Image.Image:
    width, height = size
    overlay = Image.new("RGBA", size, (255, 255, 255, 0))
    draw = ImageDraw.Draw(overlay)

    font_size = max(300, min(width, height))
    font = get_font(font_size)
    bbox = draw.textbbox((0, 0), WATERMARK_TEXT, font=font)
    text_width = bbox[2] - bbox[0]

    if text_width > 0:
        font_size = int(font_size * (width * 0.9) / text_width)
    font = get_font(font_size)

    bbox = draw.textbbox((0, 0), WATERMARK_TEXT, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    position = ((width - text_width) // 2, (height - text_height) // 2)

    draw.text(position, WATERMARK_TEXT, font=font, fill=(255, 255, 255, 255))
    return overlay


def add_watermark_image(input_path: Path, output_path: Path) -> None:
    image = Image.open(input_path).convert("RGBA")
    overlay = create_text_overlay(image.size)
    combined = Image.alpha_composite(image, overlay)
    combined.convert("RGB").save(output_path)


def add_watermark_video(input_path: Path, output_path: Path) -> None:
    clip = VideoFileClip(str(input_path))

    try:
        overlay_image = create_text_overlay((clip.w, clip.h))
        overlay_path = output_path.with_name(f"{output_path.stem}_overlay.png")
        overlay_image.save(overlay_path)

        try:
            watermark = (
                ImageClip(str(overlay_path))
                .with_duration(clip.duration)
                .with_position((0, 0))
            )

            video = CompositeVideoClip([clip, watermark])

            try:
                video.write_videofile(
                    str(output_path),
                    codec="libx264",
                    audio_codec="aac",
                    fps=clip.fps,
                    logger=None,
                )
            finally:
                video.close()
                watermark.close()
        finally:
            if overlay_path.exists():
                overlay_path.unlink()
    finally:
        clip.close()


def is_image(filename: str) -> bool:
    return filename.lower().endswith((".png", ".jpg", ".jpeg"))


def is_video(filename: str) -> bool:
    return filename.lower().endswith((".mp4", ".mov", ".avi", ".mkv"))


@bot.event
async def on_ready():
    WORKDIR.mkdir(parents=True, exist_ok=True)
    print(f"Bot is online as {bot.user}")


@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return

    if not message.attachments:
        await bot.process_commands(message)
        return

    attachment = message.attachments[0]
    safe_name = Path(attachment.filename).name
    input_path = WORKDIR / f"input_{safe_name}"
    output_path = WORKDIR / f"output_{safe_name}"

    await attachment.save(input_path)

    try:
        await message.delete()
    except Exception:
        pass

    try:
        if is_image(safe_name):
            add_watermark_image(input_path, output_path)
        elif is_video(safe_name):
            add_watermark_video(input_path, output_path)
        else:
            return

        await message.channel.send(file=discord.File(str(output_path)))
    except Exception:
        return
    finally:
        for path in (input_path, output_path):
            if path.exists():
                try:
                    path.unlink()
                except OSError:
                    pass

    await bot.process_commands(message)


bot.run(TOKEN)
