"""Quick diagnostic: reproduce the eval failure from the Urban Company run."""
import asyncio
import base64
import tempfile

from synthetic_india.config import get_llm_config
from synthetic_india.agents.llm_client import call_anthropic


async def main():
    config = get_llm_config()
    print(f"Eval model: {config.eval_model}")
    print(f"Has API key: {bool(config.anthropic_api_key)}")

    # Test 1: basic text call with eval model
    try:
        resp = await call_anthropic(
            prompt="Say hello in 5 words",
            model=config.eval_model,
            config=config,
            max_tokens=50,
        )
        print(f"Test 1 (text only): OK — {resp.content[:80]}")
    except Exception as e:
        print(f"Test 1 (text only): FAILED — {type(e).__name__}: {e}")

    # Test 2: vision call with eval model (like the failing run)
    # Create a tiny valid PNG (1x1 red pixel)
    import struct
    import zlib

    def make_tiny_png():
        # Minimal 1x1 red PNG
        sig = b"\x89PNG\r\n\x1a\n"
        # IHDR
        ihdr_data = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
        ihdr_crc = zlib.crc32(b"IHDR" + ihdr_data) & 0xFFFFFFFF
        ihdr = struct.pack(">I", 13) + b"IHDR" + ihdr_data + struct.pack(">I", ihdr_crc)
        # IDAT
        raw = zlib.compress(b"\x00\xff\x00\x00")  # filter byte + RGB
        idat_crc = zlib.crc32(b"IDAT" + raw) & 0xFFFFFFFF
        idat = struct.pack(">I", len(raw)) + b"IDAT" + raw + struct.pack(">I", idat_crc)
        # IEND
        iend_crc = zlib.crc32(b"IEND") & 0xFFFFFFFF
        iend = struct.pack(">I", 0) + b"IEND" + struct.pack(">I", iend_crc)
        return sig + ihdr + idat + iend

    png_bytes = make_tiny_png()
    b64 = base64.b64encode(png_bytes).decode()

    try:
        resp = await call_anthropic(
            prompt="What do you see in this image? Reply in 10 words.",
            model=config.eval_model,
            config=config,
            max_tokens=50,
            image_base64=b64,
            image_media_type="image/png",
        )
        print(f"Test 2 (vision): OK — {resp.content[:80]}")
    except Exception as e:
        print(f"Test 2 (vision): FAILED — {type(e).__name__}: {e}")

    # Test 3: recommendation model (this one worked in the failed run)
    try:
        resp = await call_anthropic(
            prompt="Say hello in 5 words",
            model=config.recommendation_model,
            config=config,
            max_tokens=50,
        )
        print(f"Test 3 (rec model): OK — {resp.content[:80]}")
    except Exception as e:
        print(f"Test 3 (rec model): FAILED — {type(e).__name__}: {e}")


if __name__ == "__main__":
    asyncio.run(main())
