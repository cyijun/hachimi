# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Hachimi is a modular, multiprocessing voice assistant built with Python that integrates the **Model Context Protocol (MCP)** to allow the LLM to execute tools and interact with external systems. It features real-time wake word detection, interrupt capabilities (barge-in), and connects to high-performance cloud APIs for STT, LLM, and TTS.

## Common Development Commands

### Setup and Installation
```bash
# Create virtual environment (recommended)
python -m venv venv
# On Windows
venv\Scripts\activate
# On Unix/macOS
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### Environment Variables
The project uses environment variable substitution in `config.yaml`. Set these before running:
```bash
export DEEPSEEK_API_KEY="your_deepseek_key"
export SILICONFLOW_API_KEY="your_siliconflow_key"
export MCP_AUTH_TOKEN="your_mcp_token"  # If required by your MCP server
# Optional: Custom wake word model
export WAKE_WORD_MODEL_PATH="path/to/custom/model.tflite"
```

### Running the Assistant
```bash
# Ensure MCP server is running (if using tools)
python main.py
```

The assistant will start four processes and wait for wake word detection ("Hey Jarvis" by default).

### Configuration
Edit `config.yaml` to modify:
- MCP server URLs (supports multiple SSE and Stdio servers)
- API endpoints for DeepSeek LLM, SiliconFlow STT/TTS
- Audio parameters (sample rate, chunk size, VAD settings)
- Tool selection and context management settings

## Architecture Overview

### Multiprocessing Design
The system runs four independent processes connected via `multiprocessing.Queue`:

1. **KWS_Process** (`voice_listener.py`): Wake word detection and Voice Activity Detection (VAD)
   - Uses `openwakeword` for local wake word detection
   - Uses `webrtcvad` for speech endpointing
   - Sends MP3 audio clips to audio_queue

2. **STT_Process** (`stt.py`): Speech-to-Text processing
   - Monitors audio_queue for incoming audio
   - Sends audio to SiliconFlow SenseVoiceSmall API
   - Pushes transcribed text to text_queue

3. **LLM_Process** (`llm_mcp_host/`): MCP host and LLM processing
   - Core intelligence module with `MCPVoiceAgent`
   - Connects to multiple MCP servers (SSE and Stdio)
   - Uses vector search for tool selection
   - Manages chat context and tool execution loop

4. **TTS_Process** (`tts.py`): Text-to-Speech playback
   - Monitors tts_queue for text to synthesize
   - Streams audio from SiliconFlow CosyVoice2 API
   - Handles immediate interruption via interrupt_event

### Inter-Process Communication
- **audio_queue**: KWS → STT (MP3 audio data)
- **text_queue**: STT → LLM (transcribed text)
- **tts_queue**: LLM → TTS (text to synthesize)
- **interrupt_event**: Global interrupt signal set by KWS when wake word detected during TTS playback
- **mic_running_event**: Control signal for microphone operation

### MCP Integration Architecture
The `llm_mcp_host` module provides enhanced MCP functionality:

1. **MCPServerManager** (`mcp_manager.py`): Manages multiple MCP servers
   - Supports SSE (HTTP) and Stdio (subprocess) server types
   - Handles tool name conflicts across servers
   - Maintains server connections and tool discovery

2. **VectorToolSelector** (`vector_tool_selector.py`): Intelligent tool matching
   - Uses BGE-M3 embeddings via SiliconFlow API
   - Vector similarity search for relevant tools
   - Configurable top-k tool selection

3. **ContextManager** (`context_manager.py`): Conversation context
   - Time-based and turn-based context expiration
   - Configurable context window size
   - Automatic context cleanup

4. **PromptManager** (`prompt_manager.py`): Dynamic prompt generation
   - Fetches and integrates MCP server prompts
   - Manages system prompt customization

5. **MCPVoiceAgent** (`agent.py`): Main agent class
   - Orchestrates tool selection, LLM interaction, and MCP tool execution
   - Handles tool call retries and error recovery
   - Integrates with context and prompt managers

### Configuration System
The `config.py` module provides:
- Environment variable substitution in YAML (`${VAR_NAME:default}`)
- Recursive parsing of nested configurations
- Dot-notation access (`config.llm.api_key`)
- Global `config` singleton instance

Configuration is centralized in `config.yaml` with sections for:
- Multiple MCP servers
- LLM, STT, TTS API settings
- Voice listener parameters (VAD, wake word sensitivity)
- Tool selection and vector search settings
- Context management and monitoring

## Key Files and Directories

```
hachimi/
├── main.py                    # Entry point, process management
├── config.py                  # Configuration management with env var substitution
├── config.yaml               # Central configuration file
├── logger.py                 # Unified logging system
├── voice_listener.py         # Wake word detection and VAD
├── stt.py                    # Speech-to-Text API integration
├── tts.py                    # Text-to-Speech API integration
├── llm_mcp_host/             # Enhanced MCP host module
│   ├── agent.py             # Main MCPVoiceAgent class
│   ├── mcp_manager.py       # Multi-MCP server management
│   ├── vector_tool_selector.py # Vector-based tool selection
│   ├── context_manager.py   # Conversation context management
│   ├── prompt_manager.py    # Prompt management system
│   ├── tool_selector.py     # Legacy tool selector (deprecated)
│   └── utils.py             # Utility functions
├── my_mcp_servers/           # Example custom MCP servers
│   └── wol_mcp_server/      # Wake-on-LAN MCP server
└── requirements.txt          # Python dependencies
```

## Data Flow

```
Microphone → VoiceListener (KWS/VAD) → audio_queue → STT Process → text_queue
     ↑                                      ↓
interrupt_event                        LLM Process (MCPVoiceAgent)
     ↓                                      ↓
TTS Process ← tts_queue ← LLM API ← Tool Execution ← MCP Servers
     ↓
Speaker
```

### Interruption Flow
1. Wake word detected during TTS playback → `interrupt_event.set()`
2. TTS process checks interrupt signal → immediately stops audio playback
3. KWS process clears queues → starts recording new command
4. After command processed → `interrupt_event.clear()`

## Development Notes

### Adding New MCP Servers
1. Add server configuration to `config.yaml` under `mcp_servers:`
   ```yaml
   server_name:
     type: "sse"  # or "stdio"
     url: "http://host:port/path"  # for SSE
     # or for Stdio:
     command: "python"
     args: ["path/to/server.py"]
   ```
2. Update system prompt in `config.yaml` to mention new tools
3. Restart the assistant

### Modifying Tool Selection
- Adjust `tool_selection.top_k` in `config.yaml` to change number of tools considered
- Set `tool_selection.use_vector_search` to `false` to use simple keyword matching
- Configure embedding API settings in `tool_selection.embedding` section

### Debugging
- Check logs for `[ERROR]` or `[WARNING]` messages
- Verify MCP server connections in initialization logs
- Monitor queue sizes if experiencing latency
- Check API key configuration and environment variables

### Performance Considerations
- Queue sizes configurable via `process.queue_size` (0 for unlimited)
- VAD frame size and silence limits affect recording sensitivity
- Wake word threshold balances false positives vs. detection rate
- Context management settings impact memory usage and LLM context length

## Dependencies

Core Python packages (see `requirements.txt`):
- `requests`, `pyyaml`, `numpy`
- `pyaudio` (audio I/O), `webrtcvad-wheels` (VAD), `openwakeword` (wake word)
- `pydub` (audio format conversion)
- `openai` (DeepSeek API client), `mcp` (Model Context Protocol)

External services:
- **LLM**: DeepSeek (OpenAI-compatible API)
- **STT**: SiliconFlow SenseVoiceSmall
- **TTS**: SiliconFlow CosyVoice2
- **Embeddings**: SiliconFlow BGE-M3 (for vector search)