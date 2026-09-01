---
id: dancekit
title: dancekit and the ComfyUI node pack
leads_for: [ai-video, studio-ai]
linked_projects: []
linked_pipelines: [comfyui-dancekit]
repo: https://github.com/crypticnull/h3_dance_studio
summary: Beat-locked pose control for AI video generation, a library, CLI and ComfyUI node pack that makes generated dance land on the beat.
order: 3
---

A LoRA can't fix timing. It improves how movement reads, but it has no clock, so the moment motion needs to hit on the one, timing has to live in an explicit control signal. dancekit turns a song into a hard timing grid, generates or harvests choreography against it, and drives MiniMax H3, Wan or ControlNet workflows with a skeleton sequence that actually lands on the beat. The composer is built around motif repetition, because random poses landing on every beat still look like flailing, but a phrase stated, mirrored and brought back with the chorus reads as intent. It ships as a CPU-only library and CLI plus a ComfyUI node pack with in-node preview, and it's public.
