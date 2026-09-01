---
slug: comfyui-dancekit
title: comfyui-dancekit
kind: node-pack
status: production
nodes: null
models: [OpenPose BODY_18 output, drives MiniMax H3, Wan and ControlNet, optional EDGE, AtomicDance and OpenDance sources]
hardware: CPU only for the kit, the GPU is for the video model
graph: null
workflow_json: null
demo: null
repo: https://github.com/crypticnull/h3_dance_studio
linked_proof: dancekit
writeup: null
summary: A ComfyUI node pack for beat-locked pose control, with in-node skeleton preview, frame scrubbing, beat markers and a clickable pose library.
order: 2
---

## What it does

dancekit turns a song into a hard timing grid and produces a skeleton sequence that lands on it. The node pack wraps the whole library for ComfyUI: beat analysis, choreography generation, pose harvesting from real or generated clips, retiming, SMPL projection and OpenPose rendering, each as a node with a preview you can scrub.

## Why a node pack

Timing has to live in an explicit control signal because a diffusion model has no clock. Making that signal inside ComfyUI, right next to the video graph that consumes it, means the pose sequence and the generation are one workflow, and the pose library browser makes style a thing you pick rather than a thing you hope for. The output is standard POSE_KEYPOINT plus a rendered skeleton sequence, so it feeds any video graph that takes pose control.
