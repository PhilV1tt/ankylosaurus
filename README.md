# ANKYLOSAURUS

**Automated local LLM setup CLI** -- detect your hardware, pick the best runtime & models, install everything in one command.

No cloud. No subscription. No data leaves your machine.

Named after a friend nicknamed Ankyl.

---

## What it does

1. **Detects hardware** — CPU, GPU, RAM, disk (macOS / Linux / Windows)
2. **Picks optimal setup** — runtime (LM Studio or Ollama), backend (MLX, CUDA, ROCm, CPU), quantization
3. **Searches models live** — queries HuggingFace Hub in real-time, zero hardcoded model names
4. **Installs everything** — runtime, models, CLI tools (llm, fabric-ai), GUI apps (Msty, AnythingLLM)
5. **Resumes on interruption** — Ctrl-C mid-install, re-run, picks up where it left off
6. **Manages extensions** — MCP servers, fabric patterns, Obsidian, Raycast
7. **Includes 8 personas** — coder, researcher, writer, tutor, analyst, translator, summarizer, general

## Install

One command. Works even if Python is not installed -- the script handles everything (Python, git, dependencies).

```bash
curl -fsSL https://raw.githubusercontent.com/PhilV1tt/ankylosaurus/main/bootstrap.sh | bash
```

Then:

```bash
ankylosaurus install
```

The bootstrap script:
- Installs Python 3.10+ if missing (via Homebrew, apt, dnf, pacman, winget)
- Installs git if missing
- Clones the repo to `~/.ankylosaurus/app/`
- Creates a virtualenv with all dependencies
- Adds `ankylosaurus` command to your PATH

### Manual install

```bash
git clone https://github.com/PhilV1tt/ankylosaurus.git
cd ankylosaurus
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python install.py install
```

## Commands

| Command | Description |
|---------|-------------|
| `ankylosaurus install` | Full interactive setup |
| `ankylosaurus status` | Dashboard of current installation |
| `ankylosaurus check` | Check for updates & trending models |
| `ankylosaurus update` | Update installed components |
| `ankylosaurus personas list` | List all personas |
| `ankylosaurus personas create` | Create a custom persona |
| `ankylosaurus uninstall` | Clean removal |

## Hardware decision matrix

| GPU | OS | Runtime | Backend |
|-----|-----|---------|---------|
| Apple Silicon | macOS | LM Studio | MLX |
| None | macOS Intel | Ollama | llama.cpp |
| NVIDIA | Linux | Ollama | CUDA |
| AMD | Linux | Ollama | ROCm |
| NVIDIA | Windows | LM Studio | CUDA |
| Fallback | Any | Ollama | CPU |

RAM to quantization: >=24 GB -> Q6\_K, 16-24 -> Q4\_K\_M, 8-16 -> Q3\_K\_M, <8 -> Q2\_K.

## Project structure

```
install.py              CLI entry point (Typer)
splash.py               Animated gradient text splash
bootstrap.sh            One-command installer (curl | bash)
modules/
  state.py              Install state persistence + auto-resume
  detect.py             Hardware detection
  decision.py           Runtime/backend/quantization engine
  questionnaire.py      Interactive preferences
  models.py             HuggingFace Hub model search
  installer.py          Component installer with step tracking
  extensions.py         MCP servers, fabric patterns, tools
  personas.py           Persona CRUD + 8 built-in templates
  uninstaller.py        Clean reverse-order removal
  checker.py            Version checking + trending models
  updater.py            Component-by-component updates
  status.py             Rich dashboard
  guide.py              Personalized GUIDE.md generator
```

## Dependencies

- Python 3.10+
- [Typer](https://typer.tiangolo.com/) + [Rich](https://rich.readthedocs.io/) — CLI & UI
- [huggingface-hub](https://huggingface.co/docs/huggingface_hub/) — model discovery & download
- [psutil](https://github.com/giampaolo/psutil) — hardware detection
- [httpx](https://www.python-httpx.org/) — HTTP client

## Tests

```bash
python -m pytest tests/ -v
```

## License

MIT
