```
   █████╗ ███╗   ██╗██╗  ██╗██╗   ██╗██╗      ██████╗ 
  ██╔══██╗████╗  ██║██║ ██╔╝╚██╗ ██╔╝██║     ██╔═══██╗
  ███████║██╔██╗ ██║█████╔╝  ╚████╔╝ ██║     ██║   ██║
  ██╔══██║██║╚██╗██║██╔═██╗   ╚██╔╝  ██║     ██║   ██║
  ██║  ██║██║ ╚████║██║  ██╗   ██║   ███████╗╚██████╔╝
  ╚═╝  ╚═╝╚═╝  ╚═══╝╚═╝  ╚═╝   ╚═╝   ╚══════╝ ╚═════╝
```

**One command to install and run a local LLM on your machine.**

Ankylosaurus detects your hardware, selects the best runtime and models, and installs everything - no cloud, no subscription, no data leaving your machine.

```bash
curl -fsSL https://raw.githubusercontent.com/PhilV1tt/ankylosaurus/main/bootstrap.sh | bash
```

> Works on macOS, Linux, and Windows. Python does not need to be installed beforehand.

---

## What it does

1. **Detects hardware** - CPU, GPU, RAM, disk (macOS / Linux / Windows)
2. **Picks optimal setup** - runtime (Ollama), backend (MLX, CUDA, ROCm, CPU), quantization
3. **Searches models live** - queries HuggingFace Hub in real-time, zero hardcoded model names
4. **Installs everything** - runtime, models, CLI tools (llm, fabric-ai), GUI apps (Open WebUI, AnythingLLM)
5. **Resumes on interruption** - Ctrl-C mid-install, re-run, picks up where it left off
6. **Manages extensions** - MCP servers, fabric patterns, Obsidian, Raycast
7. **Includes 8 personas** - coder, researcher, writer, tutor, analyst, translator, summarizer, general

---

## Quick start

### Bootstrap (recommended)

```bash
curl -fsSL https://raw.githubusercontent.com/PhilV1tt/ankylosaurus/main/bootstrap.sh | bash
ankylosaurus install
```

The bootstrap script installs Python 3.10+, git, clones the repo to `~/.ankylosaurus/app/`, creates a virtualenv, and adds `ankylosaurus` (alias: `ankyl` or `ankylo`) to your PATH.

### Manual install

```bash
git clone https://github.com/PhilV1tt/ankylosaurus.git
cd ankylosaurus
python3 -m venv .venv && source .venv/bin/activate
pip install -e .
ankylosaurus install
```

---

## Commands

```
ankylosaurus install          Full interactive setup
ankyl install                 Same - short alias
ankylo install                Same - short alias

ankylosaurus status           Dashboard: installed components, running services
ankylosaurus check            Check for updates and trending models
ankylosaurus update           Update runtimes, models, tools

ankylosaurus personas list    List built-in and custom personas
ankylosaurus personas create  Create a new persona interactively
ankylosaurus personas delete  Remove a custom persona

ankylosaurus uninstall        Clean removal of all installed components
```

---

## Hardware decision matrix

| GPU | OS | Runtime | Backend |
|-----|-----|---------|---------|
| Apple Silicon | macOS | Ollama | MLX |
| None | macOS Intel | Ollama | llama.cpp |
| NVIDIA | Linux | Ollama | CUDA |
| AMD | Linux | Ollama | ROCm |
| NVIDIA | Windows | Ollama | CUDA |
| Fallback | Any | Ollama | CPU |

Quantization is chosen from available RAM:

| RAM | Quantization |
|-----|-------------|
| 24 GB+ | Q6_K |
| 16 - 24 GB | Q4_K_M |
| 8 - 16 GB | Q3_K_M |
| < 8 GB | Q2_K |

---

## Optional features

### RAG (Retrieval-Augmented Generation)

Ingest PDFs and query them locally. Requires additional dependencies:

```bash
pip install -e ".[rag]"
```

> Note: the `mlx` dependency in `[rag]` is macOS Apple Silicon only. On Linux/Windows, install `pyarrow` and `lancedb` separately.

### Extensions

Ankylosaurus can install and manage:
- **MCP servers** for Claude Desktop / Cursor
- **fabric-ai** patterns
- **Obsidian** and **Raycast** integrations

### Personas

8 built-in personas ship out of the box: `coder`, `researcher`, `writer`, `tutor`, `analyst`, `translator`, `summarizer`, `general`. Create your own with `ankylosaurus personas create`.

---

## Project layout

```
ankylosaurus/
  cli.py              Entry point (Typer app, commands)
  tui.py              Interactive TUI (Textual)
  splash.py           Animated gradient splash screen
  modules/
    detect.py         Hardware detection (CPU / GPU / RAM / disk)
    decision.py       Runtime, backend, and quantization selection
    questionnaire.py  Interactive preference gathering
    models.py         HuggingFace Hub model search and filtering
    installer.py      Component installer with step tracking
    extensions.py     MCP servers, fabric patterns, external tools
    personas.py       Persona CRUD + built-in templates
    state.py          Install state persistence and resume logic
    runner.py         Model execution wrapper
    checker.py        Version checking and trending model discovery
    updater.py        Component update logic
    status.py         Rich status dashboard
    guide.py          Personalized GUIDE.md generator
    uninstaller.py    Reverse-order clean removal
    rag/
      embedder.py     Text embedding (MLX on Apple Silicon)
      chunker.py      Document chunking
      store.py        LanceDB vector store
      server.py       FastAPI server for PDF ingestion and search
bootstrap.sh          One-command installer (curl | bash)
```

---

## Development

```bash
git clone https://github.com/PhilV1tt/ankylosaurus.git
cd ankylosaurus
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pip install pyarrow lancedb   # for RAG tests

python -m pytest tests/ -v
```

CI runs on Ubuntu, macOS, and Windows against Python 3.10, 3.12, and 3.13.

---

## Dependencies

| Package | Purpose |
|---------|---------|
| [Typer](https://typer.tiangolo.com/) | CLI framework |
| [Rich](https://rich.readthedocs.io/) | Terminal formatting |
| [Textual](https://textual.textualize.io/) | Interactive TUI |
| [huggingface-hub](https://huggingface.co/docs/huggingface_hub/) | Model discovery and download |
| [psutil](https://github.com/giampaolo/psutil) | Hardware detection |
| [httpx](https://www.python-httpx.org/) | HTTP client |
| [questionary](https://github.com/tmbo/questionary) | Interactive prompts |
| [PyYAML](https://pyyaml.org/) | Configuration parsing |

---

## License

MIT
