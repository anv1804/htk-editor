export interface GridInfo {
  cols: number;
  rows: number;
  count: number;
  frame: number;
  w: number;
  h: number;
  x: number;
  y: number;
}

export interface UndoItem {
  canvas: HTMLCanvasElement;
  data: ImageData;
  x: number;
  y: number;
  other: { canvas: HTMLCanvasElement; data: ImageData }[];
}

export interface RepairSettings {
  rows: number;
  cols: number;
  colors: number;
  threshold: number;
  outline: boolean;
  paint: number;
  cleanup: number;
  composition: string;
}

export interface FrameReport {
  // Add necessary fields if any
  version?: number;
  composition?: string;
}

export interface RepairReport {
  version: number;
  composition: string;
  // ... other fields
}

export interface AppState {
  base: HTMLImageElement | null;
  outfit: HTMLImageElement | null;
  result: HTMLImageElement | null;
  mask: HTMLImageElement | null;
  report: RepairReport | null;
  undo: UndoItem[];
  redo: UndoItem[];
  busy: boolean;
  revision: number;
  outfitLayer?: string;
  headwearLayer?: string;
}

export interface StrokeState {
  point: { x: number; y: number };
  grid: GridInfo;
  canvas: HTMLCanvasElement;
  mode: string;
}

export interface AnimationDef {
  id: string;
  name: string;
  row: number;
  cols: number[];
  frames: number[];
  color: string;
}

export interface LayoutState {
  leftW?: string;
  rightW?: string;
  bottomH?: string;
  zoom?: number;
  tab?: string;
  tool?: string;
  profileTarget?: string | null;
  brushSize?: string;
  showMask?: boolean;
  maskOpacity?: string;
  showProfile?: boolean;
  fps?: string;
  paintColor?: string;
}
