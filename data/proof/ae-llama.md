---
id: ae-llama
title: AE Llama
leads_for: [studio-ai, product-inhouse]
linked_projects: []
linked_pipelines: []
repo: null
summary: A commercial After Effects panel driven by a local language model across roughly 77 tools, built and shipped alone.
order: 1
---

AE Llama is a CEP panel for After Effects that I built independently on my own hardware. A local llama.cpp model, Qwen2.5-32B sized automatically to whatever VRAM is free, drives After Effects through JSON tool calling across roughly 77 tools, so you describe what you want in a chat panel and the comp changes. There's a hidden ComfyUI backend for image and video generation, bundled ffmpeg and whisper.cpp, a self-updating signed ZXP feed, a 533-step self-test, and a VRAM tier system with a live arbiter that keeps the model and the renderer from fighting over the card. Nothing leaves the machine. It's at v0.11.0 on Windows for AE 2024 and later, and it's headed for aescripts.com.
