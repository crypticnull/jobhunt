---
slug: h3-i2v
title: MiniMax H3 image to video pipeline
kind: comfyui-graph
status: production
nodes: 38
models: [MiniMax H3, local LLM prompt rewriter, RTX Video Super Resolution]
hardware: RTX 5090, Ryzen 9 9950X3D, 64GB DDR5, fully local
graph: null
workflow_json: null
demo: null
repo: null
linked_proof: local-pipeline
writeup: null
summary: A hand-built 38-node ComfyUI graph that takes a still to finished video with local prompt rewriting and super resolution, nothing leaving the machine.
order: 1
---

## What the graph does

The graph takes a single still and returns finished video, and every stage of it runs on the workstation.

The prompt goes first. A local language model rewrites the working prompt into the form the video model responds to best, so the person driving the graph writes intent and the model gets instructions. Then MiniMax H3 generates the motion from the still. Then RTX video super resolution brings the result up to delivery resolution, which is what lets the generation stage run at a size the card can handle without the output looking like it did.

## Why it's shaped this way

It's 38 nodes because each decision that affects the frame is exposed as a node rather than buried in a preset. That's what makes it possible to change one thing, look at the result, and change it again, which is the whole job. The annotated graph export and the walkthrough of each stage land here when the export is ready.
