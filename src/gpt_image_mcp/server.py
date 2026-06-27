"""GPT Image MCP server.

Exposes OpenAI's GPT Image models (default: gpt-image-2) as MCP tools for
image generation and editing. Runs over stdio for local use with Claude Code
and Claude Desktop. Every result is saved to disk *and* returned inline so the
calling model can both reference the file and see the image.
"""

from __future__ import annotations

import base64
import os
import re
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP
from mcp.types import ImageContent, TextContent

try:  # OpenAI SDK >= 1.x
    from openai import APIError, OpenAI
except Exception:  # pragma: no cover - import guard
    OpenAI = None  # type: ignore
    APIError = Exception  # type: ignore

# --- Config / environment -------------------------------------------------

# Load .env from the current working directory and, if present, from the repo
# root (handy when installed with `pip install -e .`). Values already set in the
# environment (e.g. passed by the MCP client) always win.
load_dotenv()
_repo_env = Path(__file__).resolve().parents[2] / ".env"
if _repo_env.exists():
    load_dotenv(_repo_env, override=False)

# Approximate OpenAI pricing for cost estimates, per 1M tokens. These are
# hardcoded and *will* drift — edit them or ignore the estimate and trust your
# OpenAI usage dashboard.
_RATE_INPUT_PER_M = 8.0
_RATE_OUTPUT_PER_M = 30.0

_VALID_FORMATS = {"png", "jpeg", "webp"}

mcp = FastMCP("gpt-image")


# --- Helpers --------------------------------------------------------------

def _client() -> "OpenAI":
    if OpenAI is None:
        raise RuntimeError(
            "The 'openai' package is not installed. Run `uv sync` or "
            "`pip install -e .` in the repo."
        )
    if not os.environ.get("OPENAI_API_KEY"):
        raise RuntimeError(
            "OPENAI_API_KEY is not set. Add it to the MCP server's env config "
            "or to a .env file in the repo."
        )
    # Reads OPENAI_API_KEY (and optional OPENAI_BASE_URL) from the environment.
    return OpenAI()


def _err(msg: str) -> list:
    return [TextContent(type="text", text=msg)]


def _slugify(text: str, maxlen: int = 40) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "-", text.lower()).strip("-")
    s = s[:maxlen].rstrip("-")
    return s or "image"


def _resolve_output_dir(output_dir: str | None) -> Path:
    base = output_dir or os.environ.get("IMAGE_OUTPUT_DIR") or "generated-images"
    p = Path(base).expanduser()
    if not p.is_absolute():
        p = Path.cwd() / p
    p.mkdir(parents=True, exist_ok=True)
    return p


def _summarize(op: str, model: str, size: str, quality: str, saved: list[str], usage) -> str:
    lines = [
        f"{op} {len(saved)} image(s) with {model} (size={size}, quality={quality}):"
    ]
    lines += [f"  - {p}" for p in saved]
    if usage is not None:
        it = getattr(usage, "input_tokens", None)
        ot = getattr(usage, "output_tokens", None)
        if isinstance(it, int) and isinstance(ot, int):
            cost = it / 1e6 * _RATE_INPUT_PER_M + ot / 1e6 * _RATE_OUTPUT_PER_M
            lines.append(
                f"Tokens: {it} in / {ot} out — approx ${cost:.3f} "
                "(rates hardcoded; verify on your OpenAI dashboard)."
            )
    return "\n".join(lines)


def _save_and_return(
    op: str,
    result,
    *,
    model: str,
    size: str,
    quality: str,
    output_format: str,
    output_dir: str | None,
    filename: str | None,
    prompt: str,
) -> list:
    data = getattr(result, "data", None) or []
    if not data:
        return _err("The API returned no image data.")
    out_dir = _resolve_output_dir(output_dir)
    base = filename or _slugify(prompt)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    ext = output_format if output_format in _VALID_FORMATS else "png"
    mime = f"image/{ext}"

    saved: list[str] = []
    content: list = []
    for i, d in enumerate(data):
        b64 = getattr(d, "b64_json", None)
        if not b64:
            continue
        img_bytes = base64.b64decode(b64)
        suffix = f"-{i + 1}" if len(data) > 1 else ""
        path = out_dir / f"{base}-{stamp}{suffix}.{ext}"
        path.write_bytes(img_bytes)
        saved.append(str(path))
        content.append(ImageContent(type="image", data=b64, mimeType=mime))

    if not saved:
        return _err("The API returned data but no base64 image payload was found.")

    summary = _summarize(op, model, size, quality, saved, getattr(result, "usage", None))
    return [TextContent(type="text", text=summary), *content]


# --- Tools ----------------------------------------------------------------

@mcp.tool()
def generate_image(
    prompt: str,
    model: str = "gpt-image-2",
    size: str = "1024x1024",
    quality: str = "high",
    n: int = 1,
    background: str = "auto",
    output_format: str = "png",
    output_dir: str | None = None,
    filename: str | None = None,
) -> list:
    """Generate image(s) from a text prompt with OpenAI GPT Image and save them to disk.

    Use this to create new images from scratch: UI mockups, icons, hero images,
    diagrams, illustrations, and social/marketing graphics. GPT Image renders
    in-image text unusually well, so write any text you want to appear in the
    image literally and describe its placement.

    Args:
        prompt: What to generate. Be specific about subject, style, composition,
            lighting, and any text that should appear in the image.
        model: GPT Image model. Default "gpt-image-2" (best quality + reasoning).
            Use "gpt-image-1-mini" for cheap/fast iteration, then re-render the
            final asset with "gpt-image-2".
        size: "1024x1024" (square), "1536x1024" (landscape), "1024x1536"
            (portrait), or "auto". gpt-image-2 also supports larger / 2K sizes.
        quality: "low", "medium", "high", or "auto". Higher is better and costs
            more.
        n: Number of images to generate (1-10).
        background: "auto", "opaque", or "transparent". NOTE: gpt-image-2 does
            NOT support "transparent" — pass model="gpt-image-1.5" (or another
            alpha-capable model) when you need a transparent background.
        output_format: "png", "jpeg", or "webp".
        output_dir: Directory to save images into. Defaults to $IMAGE_OUTPUT_DIR,
            or ./generated-images relative to the current working directory.
        filename: Base filename without extension. Defaults to a slug of the
            prompt plus a timestamp.

    Returns:
        A text summary with the saved file path(s), followed by the image(s)
        inline.
    """
    try:
        client = _client()
    except RuntimeError as e:
        return _err(str(e))

    n = max(1, min(int(n), 10))
    kwargs = {"model": model, "prompt": prompt, "size": size, "quality": quality, "n": n}
    if background and background != "auto":
        kwargs["background"] = background
    if output_format and output_format != "png":
        kwargs["output_format"] = output_format

    try:
        result = client.images.generate(**kwargs)
    except APIError as e:
        return _err(f"OpenAI API error: {e}")
    except Exception as e:  # network, validation, etc.
        return _err(f"Image generation failed: {e}")

    return _save_and_return(
        "Generated",
        result,
        model=model,
        size=size,
        quality=quality,
        output_format=output_format,
        output_dir=output_dir,
        filename=filename,
        prompt=prompt,
    )


@mcp.tool()
def edit_image(
    prompt: str,
    images: list[str],
    mask: str | None = None,
    model: str = "gpt-image-2",
    size: str = "auto",
    quality: str = "high",
    n: int = 1,
    output_format: str = "png",
    output_dir: str | None = None,
    filename: str | None = None,
) -> list:
    """Edit, restyle, or combine existing image(s) using a text instruction.

    Use this for image-to-image work: modify an image, restyle it, composite
    several inputs into one, inpaint a masked region, or extend / outpaint.

    Args:
        prompt: Instruction describing the desired edit or final result.
        images: One or more paths to input image files (PNG/JPEG/WEBP, <=50MB
            each). Multiple images are used together as references / inputs.
        mask: Optional path to a PNG mask. Transparent areas of the mask mark the
            region to edit/replace; opaque areas are preserved.
        model: GPT Image model. Default "gpt-image-2".
        size: "1024x1024", "1536x1024", "1024x1536", or "auto".
        quality: "low", "medium", "high", or "auto".
        n: Number of variations to generate (1-10).
        output_format: "png", "jpeg", or "webp".
        output_dir: Where to save. Defaults to $IMAGE_OUTPUT_DIR or
            ./generated-images.
        filename: Base filename without extension.

    Returns:
        A text summary with the saved file path(s), followed by the image(s)
        inline.
    """
    try:
        client = _client()
    except RuntimeError as e:
        return _err(str(e))

    paths = [Path(p).expanduser() for p in images]
    for p in paths:
        if not p.exists():
            return _err(f"Input image not found: {p}")
    mask_path = Path(mask).expanduser() if mask else None
    if mask_path is not None and not mask_path.exists():
        return _err(f"Mask file not found: {mask_path}")

    n = max(1, min(int(n), 10))
    open_files = [p.open("rb") for p in paths]
    mask_file = mask_path.open("rb") if mask_path else None
    try:
        kwargs = {
            "model": model,
            "prompt": prompt,
            "image": open_files if len(open_files) > 1 else open_files[0],
            "n": n,
            "size": size,
            "quality": quality,
        }
        if mask_file is not None:
            kwargs["mask"] = mask_file
        if output_format and output_format != "png":
            kwargs["output_format"] = output_format
        try:
            result = client.images.edit(**kwargs)
        except APIError as e:
            return _err(f"OpenAI API error: {e}")
        except Exception as e:
            return _err(f"Image edit failed: {e}")
    finally:
        for f in open_files:
            f.close()
        if mask_file is not None:
            mask_file.close()

    return _save_and_return(
        "Edited into",
        result,
        model=model,
        size=size,
        quality=quality,
        output_format=output_format,
        output_dir=output_dir,
        filename=filename,
        prompt=prompt,
    )


def main() -> None:
    """Console-script / module entry point. Runs the server over stdio."""
    mcp.run()


if __name__ == "__main__":
    main()
