# gpt-image-mcp

A tiny, self-contained [MCP](https://modelcontextprotocol.io) server that gives
**Claude Code** and **Claude Desktop** image generation and editing via OpenAI's
**gpt-image-2** (and other GPT Image models). Every result is saved to disk and
returned inline, so Claude can both wire the file into your project and show you
the image.

Two tools:

- **`generate_image`** — text → image (UI mockups, icons, hero art, diagrams,
  social graphics). GPT Image renders in-image text well, so describe any text
  literally.
- **`edit_image`** — image(s) + instruction → image (restyle, composite,
  inpaint with a mask, outpaint).

This runs **locally over stdio**. It is for Claude Code and Claude Desktop, which
support local servers. It is *not* a remote connector and will not appear in
claude.ai in the browser (that requires a hosted, OAuth-protected server).

---

## Prerequisites

- **Python 3.10+**
- **[uv](https://docs.astral.sh/uv/)** (recommended) or `pip`
- An **OpenAI API key** with credits. ⚠️ **gpt-image-2 may require
  Organization Verification** on your OpenAI org — without it, calls return
  HTTP 403. Verify under *OpenAI dashboard → Settings → Organization*.

---

## Install (do this on each PC after cloning)

```bash
git clone <your-repo-url> gpt-image-mcp
cd gpt-image-mcp
./install.sh
```

`install.sh` installs the dependencies and then **prints the exact config for
both clients with the absolute paths already filled in for that machine**. Copy
what it prints. (On Windows without WSL, follow *Manual setup* below.)

> Tip: paths differ per machine, so re-run `./install.sh` on each PC rather than
> copying a config file between them.

---

## Configure Claude Code

Export your key, then run the command `install.sh` printed (it looks like this):

```bash
export OPENAI_API_KEY=sk-...
claude mcp add gpt-image --scope user \
  -e OPENAI_API_KEY=$OPENAI_API_KEY \
  -e IMAGE_OUTPUT_DIR="$HOME/gpt-image-output" \
  -- uv run --directory /abs/path/to/gpt-image-mcp gpt-image-mcp
```

`--scope user` makes it available in every project on that machine. Verify with
`claude mcp list`, or `/mcp` inside a session. In Claude Code, leave
`IMAGE_OUTPUT_DIR` off if you'd rather images land in each project's
`./generated-images` folder.

---

## Configure Claude Desktop

Add the block `install.sh` printed under `"mcpServers"` in
`claude_desktop_config.json`, replace the key, and **fully quit and relaunch
Desktop**.

```json
{
  "mcpServers": {
    "gpt-image": {
      "command": "/absolute/path/to/uv",
      "args": ["run", "--directory", "/abs/path/to/gpt-image-mcp", "gpt-image-mcp"],
      "env": {
        "OPENAI_API_KEY": "sk-...",
        "IMAGE_OUTPUT_DIR": "/Users/joe/gpt-image-output"
      }
    }
  }
}
```

Config file location:

| OS | Path |
| --- | --- |
| macOS | `~/Library/Application Support/Claude/claude_desktop_config.json` |
| Windows | `%APPDATA%\Claude\claude_desktop_config.json` |

Open it from Desktop via **Settings → Developer → Edit Config**.

**Two gotchas that bite on Desktop specifically:**

1. Use the **absolute path** to `uv` (or to `.venv/bin/gpt-image-mcp`). Desktop
   launches configs with a minimal `PATH`, so bare `uv`/`npx` often fail even
   though they work in your terminal. Find it with `which uv`.
2. **Set `IMAGE_OUTPUT_DIR` to an absolute path.** Desktop's working directory
   is unpredictable, so without this you may not find your images.

---

## Manual setup (no uv, or Windows)

```bash
python3 -m venv .venv
# macOS/Linux:
.venv/bin/pip install -e .
# Windows (PowerShell):
.\.venv\Scripts\pip install -e .
```

Then point the `command` at the installed script:

- macOS/Linux: `/abs/path/to/gpt-image-mcp/.venv/bin/gpt-image-mcp`
- Windows: `C:\abs\path\to\gpt-image-mcp\.venv\Scripts\gpt-image-mcp.exe`

(args can be `[]` since the script is the entry point), and set
`OPENAI_API_KEY` / `IMAGE_OUTPUT_DIR` in `env`.

---

## Usage

Just ask in natural language:

- *"Generate a 1536x1024 hero image: a calm modern fintech dashboard, soft
  gradients, the headline 'Self-Directed IRAs, Simplified' in clean sans-serif."*
- *"Make three square app icons for a swim-tracking tool — minimalist line art."*
- *"Edit `./logo.png` to put it on a transparent... "* → use
  `model="gpt-image-1.5"` for transparency (see limitations).
- In Claude Code: *"Generate a background image and use it in `hero.tsx`."* —
  it saves the file into the project and references it for you.

### Tool parameters (most useful)

`generate_image`: `prompt`, `model` (default `gpt-image-2`), `size`
(`1024x1024` | `1536x1024` | `1024x1536` | `auto`), `quality`
(`low`|`medium`|`high`|`auto`), `n` (1–10), `background`
(`auto`|`opaque`|`transparent`), `output_format` (`png`|`jpeg`|`webp`),
`output_dir`, `filename`.

`edit_image`: `prompt`, `images` (list of paths), `mask` (PNG path), plus the
same `model`/`size`/`quality`/`n`/`output_format`/`output_dir`/`filename`.

---

## Limitations & notes

- **No transparent background on gpt-image-2.** Passing
  `background="transparent"` to it will error. For alpha (icons/UI assets), pass
  `model="gpt-image-1.5"` or another alpha-capable model.
- **Cost.** GPT Image is token-priced; most generations land roughly
  $0.04–$0.35 each depending on size/quality. The tool prints a rough estimate
  (rates are hardcoded in `server.py` and may drift — trust your OpenAI
  dashboard).
- **Cheap iteration.** Use `model="gpt-image-1-mini"` to rough things out, then
  re-render the final with `gpt-image-2`.
- **Org verification.** A 403 almost always means your OpenAI org isn't verified
  for GPT Image yet.

## License

MIT — see [LICENSE](LICENSE).
