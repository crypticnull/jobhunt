---
id: local-pipeline
title: The local generative pipeline
leads_for: [ai-video]
linked_projects: []
linked_pipelines: [h3-i2v]
repo: null
summary: A hand-built ComfyUI image to video graph, 38 nodes, MiniMax H3 with local prompt rewriting and RTX super resolution, running entirely on my own hardware.
order: 2
---

The pipeline is a ComfyUI graph I built by hand, not a downloaded template. It takes a still, rewrites the prompt with a local language model, runs MiniMax H3 for image to video, and finishes with RTX video super resolution, all on one workstation with an RTX 5090. Around that core sit the graphs for upscaling, picture repair and character replacement, and the same stack runs Wan, LTX, Flux and Krea 2 when the job wants them. Running a model is the easy part. The point is that I can judge the frame that comes out and change the graph until it's right.
