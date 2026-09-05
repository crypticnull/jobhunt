---
slug: character-pipeline
title: The eight-angle character pipeline
kind: comfyui-graph
status: production
nodes: 219
models: [Qwen-Image-Edit, a self-trained character LoRA, SDXL]
hardware: RTX 5090, Ryzen 9 9950X3D, 64GB DDR5, fully local
graph: null
workflow_json: null
demo: null
repo: null
linked_proof: game-project
writeup: null
summary: A 219-node ComfyUI graph that solves multi-angle character consistency structurally rather than by prompting, and a scripted correction chain that turns the frames into sprites.
order: 3
---

## What the graph does

One reference character is generated, and then an image-edit model re-renders that same character from eight viewpoints, because the prompts describe the camera and not the character. One run produces a complete, correctly foldered directional set including the class-select portrait, off a character LoRA I trained for the purpose. That's the structural answer to consistency: the character is an input, and only the camera changes.

## What happens after the graph

Generated frames are an input, not an asset. A scripted correction chain normalises the eight facings onto a common ground line, measured at five pixels of spread on a 96 pixel frame, and synthesises the second walk frame procedurally from the silhouette rather than drawing or diffusing it. The output is 98 sprite sheets, all 8-bit RGBA, and they're what the game runs on.

## Why it's shaped this way

It's 219 nodes because every decision that touches a frame is a node, so the graph can be changed one decision at a time and looked at. The annotated export lands here once the widget values are stripped, and the eight raw angles beside the corrected ones are the figure the study is built around.
