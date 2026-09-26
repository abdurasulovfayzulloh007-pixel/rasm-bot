import asyncio
import os
from io import BytesIO
from pathlib import Path

from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import CommandStart
from aiogram.types import BufferedInputFile
from PIL import Image, ImageDraw, ImageFont, ImageOps

# ---------------- SOZLAMALAR ----------------
BOT_TOKEN = os.getenv("BOT_TOKEN", "8905452846:AAEwf8sYDO2IDDq7h3AplmsF6wOqlJbwC3Q")

BASE = Path(__file__).parent
LOGO_PATHS = {
    "1": BASE / "logo1.png",   # /logo1 buyrug'i shu faylni yoqadi
    "2": BASE / "logo2.png",   # /logo2 buyrug'i shu faylni yoqadi
}
DEFAULT_LOGO = "1"
user_logo_choice: dict[int, str] = {}   # har bir foydalanuvchining tanlovi (xotirada saqlanadi)

# Barcha o'lchamlar rasm KENGLIGIGA nisbatan (0.10 = 10%)
LOGO_WIDTH_RATIO = 0.365    # logo kengligi (bo'sh chetlari kesib tashlanadi)
LOGO_MARGIN_RATIO = 0.025   # logo chap va yuqori chetdan masofasi

TEXT_CAP_RATIO = 0.027      # bosh harflar balandligi (matn o'lchami)
TEXT_MARGIN_X_RATIO = 0.034 # matn o'ng chetdan masofasi
TEXT_MARGIN_Y_RATIO = 0.023 # matn pastdan masofasi
TEXT_MAX_WIDTH = 0.85       # matn rasm kengligining 85% dan oshsa, qatorga o'tadi
TEXT_COLOR = "black"        # matn rangi
STROKE_COLOR = "white"      # matn atrofidagi yupqa kontur (qorong'i rasmda o'qilishi uchun)
STROKE_RATIO = 0.0          # kontur qalinligi (harf balandligiga nisbatan), 0 = kontursiz

# Shrift: o'zingizning shriftingizni "font.ttf" nomi bilan shu papkaga qo'ysangiz,
# birinchi shu ishlatiladi. Aks holda ro'yxat bo'yicha birinchi topilgani olinadi.
FONT_CANDIDATES = [
    BASE / "font.ttf",
    "COPRGTB.TTF",       # Copperplate Gothic Bold (Microsoft Office bilan o'rnatiladi)
    "ENGR.TTF",          # Engravers MT
    "arialbd.ttf",
    "DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
]
# --------------------------------------------


def load_font(size: int) -> ImageFont.FreeTypeFont:
    for path in FONT_CANDIDATES:
        try:
            return ImageFont.truetype(str(path), size)
        except OSError:
            continue
    return ImageFont.load_default(size)


def font_for_cap_height(cap_px: float) -> ImageFont.FreeTypeFont:
    """Shriftni bosh harflar balandligi aynan cap_px bo'ladigan qilib tanlaydi.
    Shunda qaysi shrift ishlatilishidan qat'i nazar, o'lcham bir xil chiqadi."""
    probe = load_font(100)
    box = probe.getbbox("H")
    cap_at_100 = max(box[3] - box[1], 1)
    return load_font(max(int(round(100 * cap_px / cap_at_100)), 8))


def wrap_text(draw: ImageDraw.ImageDraw, text: str, font, max_width: float) -> str:
    lines = []
    for paragraph in text.split("\n"):
        line = ""
        for word in paragraph.split():
            test = f"{line} {word}".strip()
            if draw.textlength(test, font=font) <= max_width:
                line = test
            else:
                if line:
                    lines.append(line)
                line = word
        lines.append(line)
    return "\n".join(lines)


def process_image(data: bytes, text: str, logo_path: Path) -> bytes:
    img = ImageOps.exif_transpose(Image.open(BytesIO(data))).convert("RGBA")
    w, h = img.size

    # 1) Logo: chap yuqori burchak
    if logo_path.exists():
        logo = Image.open(logo_path).convert("RGBA")
        content = logo.getchannel("A").getbbox()   # shaffof bo'sh chetlarni kesamiz
        if content:
            logo = logo.crop(content)
        logo_w = int(w * LOGO_WIDTH_RATIO)
        logo_h = max(int(logo.height * logo_w / logo.width), 1)
        logo = logo.resize((logo_w, logo_h), Image.LANCZOS)
        lm = int(w * LOGO_MARGIN_RATIO)
        img.alpha_composite(logo, (lm, lm))

    # 2) Matn: o'ng pastki burchak
    draw = ImageDraw.Draw(img)
    cap_px = w * TEXT_CAP_RATIO
    font = font_for_cap_height(cap_px)
    stroke = int(round(cap_px * STROKE_RATIO))

    wrapped = wrap_text(draw, text, font, w * TEXT_MAX_WIDTH)
    bbox = draw.multiline_textbbox(
        (0, 0), wrapped, font=font, align="right", stroke_width=stroke
    )
    text_w, text_h = bbox[2] - bbox[0], bbox[3] - bbox[1]
    x = w - int(w * TEXT_MARGIN_X_RATIO) - text_w - bbox[0]
    y = h - int(w * TEXT_MARGIN_Y_RATIO) - text_h - bbox[1]

    draw.multiline_text(
        (x, y), wrapped, font=font, fill=TEXT_COLOR,
        stroke_width=stroke, stroke_fill=STROKE_COLOR, align="right",
    )

    out = BytesIO()
    img.convert("RGB").save(out, "JPEG", quality=95)
    return out.getvalue()


dp = Dispatcher()


@dp.message(CommandStart())
async def start(m: types.Message):
    await m.answer(
        "Salom! Menga rasm yuboring va rasm izohiga (caption) matn yozing.\n"
        "Men matnni o'ng pastki burchakka, logoni chap yuqori burchakka qo'yib qaytaraman.\n\n"
        "Ikkita logo bor, tanlash uchun:\n"
        "/logo1 — birinchi logo\n"
        "/logo2 — ikkinchi logo"
    )


@dp.message(F.text == "/logo1")
async def choose_logo1(m: types.Message):
    user_logo_choice[m.from_user.id] = "1"
    await m.answer("Birinchi logo tanlandi. Endi shu logo bilan ishlanadi.")


@dp.message(F.text == "/logo2")
async def choose_logo2(m: types.Message):
    user_logo_choice[m.from_user.id] = "2"
    await m.answer("Ikkinchi logo tanlandi. Endi shu logo bilan ishlanadi.")


async def handle(m: types.Message, bot: Bot, file, as_document: bool):
    if not m.caption:
        await m.answer("Rasm bilan birga izohga matn ham yozing.")
        return

    choice = user_logo_choice.get(m.from_user.id, DEFAULT_LOGO)
    logo_path = LOGO_PATHS[choice]

    buf = await bot.download(file)
    result = await asyncio.to_thread(process_image, buf.getvalue(), m.caption, logo_path)
    out_file = BufferedInputFile(result, filename="result.jpg")

    if as_document:
        await m.answer_document(out_file)  # sifat pasaymaydi
    else:
        await m.answer_photo(out_file)


@dp.message(F.photo)
async def on_photo(m: types.Message, bot: Bot):
    await handle(m, bot, m.photo[-1], as_document=False)


@dp.message(F.document.mime_type.startswith("image/"))
async def on_document(m: types.Message, bot: Bot):
    # Rasm "fayl" sifatida yuborilsa, sifati saqlanadi va natija ham fayl bo'lib qaytadi
    await handle(m, bot, m.document, as_document=True)


async def main():
    bot = Bot(BOT_TOKEN)
    await bot.delete_webhook(drop_pending_updates=True)  # eski webhook bo'lsa, o'chiramiz
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
