---
id: ae-llama
title: AE Llama
leads_for: [studio-ai, product-inhouse]
linked_projects: []
linked_pipelines: []
repo: null
summary: A commercial After Effects panel driven by a local language model, built and shipped alone, with a tool surface that keeps growing.
# The inventory lives here rather than in the sentences above, so the product
# can move without a stale number being left behind in prose. Fill categories
# with the real grouping and counts and the site does the arithmetic; leave it
# empty and the site says nothing. Tool names are deliberately not listed,
# which is what makes this publishable before the aescripts launch.
manifest:
  label: tools
  version: "0.11.0"
  updated: "2026-09-02"
  categories: []
order: 1
---

AE Llama is a CEP panel for After Effects that I built independently on my own hardware. A local llama.cpp model, Qwen2.5-32B sized automatically to whatever VRAM is free, drives After Effects through JSON tool calling across seventy-plus tools, so you describe what you want in a chat panel and the comp changes. There's a hidden ComfyUI backend for image and video generation, bundled ffmpeg and whisper.cpp, a self-updating signed ZXP feed, and a 533-step self-test. A VRAM tier system with a live arbiter keeps the model and the renderer from fighting over the card. Nothing leaves the machine. It runs on Windows for AE 2024 and later, and it's headed for aescripts.com.
