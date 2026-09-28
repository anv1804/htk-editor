import type { AppState } from './types';

export const state: AppState = { 
  base: null, 
  greenBase: null,
  headBase: null,
  bodyBase: null,
  outfit: null, 
  result: null, 
  mask: null, 
  report: null, 
  undo: [], 
  redo: [], 
  busy: false, 
  revision: 0 
};

export const corrections = document.createElement("canvas");
export const correctionContext = corrections.getContext("2d", { willReadFrequently: true })!;

export const baseMap = document.createElement("canvas");
export const baseMapContext = baseMap.getContext("2d", { willReadFrequently: true })!;

export const paintLayer = document.createElement("canvas");
export const paintContext = paintLayer.getContext("2d", { willReadFrequently: true })!;
// Animation and timeline always show the assembled character, independent of
// which isolated layer is open in the editing canvas.
export const compositePreview = document.createElement('canvas');

export const storageKey = "outfit-repair-v2";

export let profileState = {
  key: null as string | null,
  source: null as string | null,
  grid: null as string | null
};

export function setProfileState(key: string | null, source: string | null, grid: string | null) {
  profileState.key = key;
  profileState.source = source;
  profileState.grid = grid;
}
