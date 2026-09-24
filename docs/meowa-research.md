# Meowa Research Notes

This document records public workflow ideas adopted by HKT Pixel Forge. It does not reproduce Meowa's proprietary generation models or private server implementation.

## Public architecture

Meowa's public skill is primarily a client and product contract. Generation and animation happen behind hosted API endpoints. The public repository exposes routing, request validation, padding rules, output allowlists, job polling, and asset-delivery contracts, but not the trained pixel-generation or animation models.

## Principles adopted

1. Generate or author one object at its final native pixel dimensions.
2. Treat the approved still sprite as the identity source of truth.
3. Do not pixelate an already-native pixel asset again.
4. Do not generate a mixed action sheet as the source asset.
5. Prepare an action-ready first pose before animation.
6. Add transparent motion space without resampling the source.
7. Use directional padding based on the action.
8. Prefer eight frames for ordinary actions; use explicit keyframes when intermediate poses matter.
9. Keep every keyframe on the same canvas, scale, anchor, and palette contract.
10. Validate dimensions, alpha, palette, edge contact, anchors, drift, and loop closure before export.
11. Export only declared final deliverables through a sanitized manifest.

## Project-specific decisions

- Native gameplay frame: `64x64`.
- Recommended character height: `48-54 px` inside the native frame.
- Animation preparation canvas: no larger than `128x128`.
- Alpha: sharp, values `0` or `255` only.
- Default palette limit: none; enforce a limit only when required by the runtime. Never reduce colors silently during export.
- Facing: right; runtime may mirror to face left when asymmetry is acceptable.
- Default action set: idle, run, jump, hit, attack, dead.
- Default action length: 4 native 64x64 frames, matching the current game contract. More frames are explicit per-action choices.

## Sources

- Meowa game-assets skill: https://github.com/Meowa-AI/meowa-skills/blob/main/skills/game-assets/SKILL.md
- Pixel and HD assets: https://github.com/Meowa-AI/meowa-skills/blob/main/skills/game-assets/references/pixel-and-hd-assets.md
- Animation and video: https://github.com/Meowa-AI/meowa-skills/blob/main/skills/game-assets/references/animation-and-video.md
- Capability routing: https://github.com/Meowa-AI/meowa-skills/blob/main/skills/game-assets/references/capability-routing.md
- Running and outputs: https://github.com/Meowa-AI/meowa-skills/blob/main/skills/game-assets/references/running-and-outputs.md
