    // =========================================================================
    // 1. Definition of the 8 Xianxia Animations by Row & Columns
    // =========================================================================
    const ANIMATION_DEFS = [
      { id: "preview", name: "Nhìn thẳng (Preview)", row: 1, cols: [1, 2], frames: [1, 2], color: "#38bdf8" },
      { id: "idle",    name: "Thở đứng (Idle)",        row: 1, cols: [3, 4], frames: [3, 4], color: "#2dd4bf" },
      { id: "archery", name: "Bắn cung",              row: 2, cols: [1, 2, 3, 4], frames: [5, 6, 7, 8], color: "#fbbf24" },
      { id: "spear",   name: "Đâm thương",            row: 3, cols: [1, 2, 3, 4], frames: [9, 10, 11, 12], color: "#f87171" },
      { id: "jump",    name: "Nhảy (Jump)",           row: 4, cols: [1, 2, 3, 4], frames: [13, 14, 15, 16], color: "#a855f7" },
      { id: "slash",   name: "Vung kiếm (Slash)",     row: 5, cols: [1, 2, 3, 4], frames: [17, 18, 19, 20], color: "#ec4899" },
      { id: "walk",    name: "Đi bộ (Walk)",          row: 6, cols: [1, 2, 3, 4], frames: [21, 22, 23, 24], color: "#3b82f6" },
      { id: "run",     name: "Chạy (Run)",            row: 7, cols: [1, 2, 3, 4], frames: [25, 26, 27, 28], color: "#10b981" }
    ];

    // =========================================================================
    // 2. Aseprite Tool Palette + Profile Target System (Simplified)
    // =========================================================================
    const nativeBrushSelect = document.getElementById("brush");
    const toolButtons = document.querySelectorAll(".aseprite-vertical-toolbox .tool-btn:not(.profile-target-btn)");
    const profileTargetBtns = document.querySelectorAll(".profile-target-btn");
    const paintColorInput = document.getElementById("paintColor");
    const swatchPreview = document.getElementById("colorSwatchPreview");
    const profileBadge = document.getElementById("profileTargetBadge");

    let currentActiveTool = "inspect";  // Visual tool state
    let profileTarget = null;           // null | "head" | "hand"

    function getEffectiveBrush(tool, shiftKey) {
      if (!profileTarget) return tool;
      if (tool === "color" || tool === "inspect") {
        if (shiftKey) return profileTarget === "head" ? "profileBoxHead" : "profileBoxHand";
        return profileTarget === "head" ? "profileHead" : "profileHand";
      }
      if (tool === "unpaint") {
        return shiftKey ? "profileBoxErase" : "profileErase";
      }
      return tool;
    }

    function updateProfileTargetUI() {
      profileTargetBtns.forEach(btn => {
        if (btn.dataset.profileTarget === profileTarget) btn.classList.add("target-active");
        else btn.classList.remove("target-active");
      });
      if (profileBadge) {
        if (profileTarget) {
          profileBadge.textContent = profileTarget === "head" ? "🧑 ĐẦU" : "🤚 TAY";
          profileBadge.classList.remove("hidden");
        } else {
          profileBadge.classList.add("hidden");
        }
      }
      saveLayout();
    }

    function setActiveTool(toolMode) {
      currentActiveTool = toolMode;
      if (nativeBrushSelect) {
        nativeBrushSelect.value = currentActiveTool === "unpaint" ? "auto" : currentActiveTool;
        nativeBrushSelect.dispatchEvent(new Event("change"));
      }
      toolButtons.forEach(btn => {
        if (btn.dataset.brushVal === toolMode) btn.classList.add("active");
        else btn.classList.remove("active");
      });
      saveLayout();
    }

    function toggleProfileTarget(target) {
      if (profileTarget === target) {
        profileTarget = null;  // Toggle off
      } else {
        profileTarget = target;
        // Auto-switch to pen tool if currently on inspect so they can draw immediately
        if (currentActiveTool === "inspect") setActiveTool("color");
      }
      updateProfileTargetUI();
    }

    toolButtons.forEach(btn => btn.addEventListener("click", () => setActiveTool(btn.dataset.brushVal)));
    profileTargetBtns.forEach(btn => btn.addEventListener("click", () => toggleProfileTarget(btn.dataset.profileTarget)));

    if (paintColorInput && swatchPreview) {
      paintColorInput.addEventListener("input", (e) => {
        swatchPreview.style.backgroundColor = e.target.value;
        saveLayout();
      });
    }

    // CAPTURING PHASE: Compute real tool based on which canvas they click!
    [document.getElementById("baseCanvas"), document.getElementById("editCanvas")].forEach(canvas => {
      if (!canvas) return;
      canvas.addEventListener("pointerdown", (e) => {
        if (!nativeBrushSelect) return;
        const isBase = canvas.id === "baseCanvas";
        // Only apply profile tools when drawing on the Base canvas
        if (isBase && profileTarget) {
          nativeBrushSelect.value = getEffectiveBrush(currentActiveTool, e.shiftKey);
        } else {
          nativeBrushSelect.value = currentActiveTool === "unpaint" ? "auto" : currentActiveTool;
        }
      }, true);
    });

    // Keyboard Shortcuts
    window.addEventListener("keydown", (e) => {
      if (["INPUT", "SELECT", "TEXTAREA"].includes(e.target.tagName)) return;
      const key = e.key.toUpperCase();
      if (key === "V") setActiveTool("inspect");
      else if (key === "B") setActiveTool("color");
      else if (key === "I") setActiveTool("sample");
      else if (key === "E") setActiveTool("unpaint");
      else if (key === "R") setActiveTool("base");
      else if (key === "U") setActiveTool("outfit");
      else if (key === "G") setActiveTool("erase");
      else if (key === "A") setActiveTool("auto");
      else if (key === "H") toggleProfileTarget("head");
      else if (key === "J") toggleProfileTarget("hand");
      else if (key === " " && !e.repeat) {
        e.preventDefault();
        togglePlayPause();
      }
      else if (key === "Z" && (e.ctrlKey || e.metaKey)) {
        document.getElementById("undo")?.click();
      }
    });

    // Reset Frame All
    const btnResetFrame = document.getElementById("btnResetFrameAll");
    if (btnResetFrame) {
      btnResetFrame.addEventListener("click", () => {
        const g = (typeof grid === "function") ? grid() : null;
        if (!g) return;
        if (confirm(`Reset Frame ${g.frame + 1} về nguyên gốc?`)) {
          if (typeof checkpoint === "function") checkpoint(corrections, g, [paintLayer, baseMap]);
          if (typeof correctionContext !== "undefined") correctionContext.clearRect(g.x, g.y, g.w, g.h);
          if (typeof paintContext !== "undefined") paintContext.clearRect(g.x, g.y, g.w, g.h);
          if (typeof baseMapContext !== "undefined") baseMapContext.clearRect(g.x, g.y, g.w, g.h);
          if (typeof invalidate === "function") invalidate("Đã reset frame về gốc.");
          if (typeof render === "function") render();
          if (typeof remember === "function") remember();
        }
      });
    }

    // =========================================================================
    // 3. Smooth Continuous Zoom Engine + Pan
    // =========================================================================
    let currentZoom = 4.0;
    const zoomPercentEl = document.getElementById("zoomPercent");
    const zoomSelect = document.getElementById("zoom");
    const sheetZoomSelect = document.getElementById("sheetZoom");

    function applyZoom(newZoom, tabMode = null) {
      // tabMode determines which limit to use. Sheet tab zooms out further.
      const isSheet = tabMode === "sheet" || !document.getElementById("sheetTab")?.classList.contains("hidden");
      const minZoom = isSheet ? 0.5 : 1.0;
      const maxZoom = isSheet ? 8.0 : 32.0;
      
      currentZoom = Math.min(maxZoom, Math.max(minZoom, Math.round(newZoom * 10) / 10));
      zoomPercentEl.textContent = `${Math.round(currentZoom * 100)}%`;

      if (isSheet) {
        // Spritesheet Tab
        let opt = sheetZoomSelect.querySelector(`option[value="${currentZoom}"]`);
        if (!opt) {
          opt = document.createElement("option");
          opt.value = currentZoom;
          sheetZoomSelect.appendChild(opt);
        }
        sheetZoomSelect.value = currentZoom;
      } else {
        // Inspector Tab
        let opt = zoomSelect.querySelector(`option[value="${currentZoom}"]`);
        if (!opt) {
          opt = document.createElement("option");
          opt.value = currentZoom;
          zoomSelect.appendChild(opt);
        }
        zoomSelect.value = currentZoom;
      }

      // We don't apply CSS here directly because calling render() in ui.js handles it beautifully.
      // And because we correctly injected the option, render() will use exactly currentZoom!
      if (typeof render === "function") render();

      saveLayout();
    }

    document.getElementById("btnZoomIn").addEventListener("click", () => applyZoom(currentZoom + (currentZoom < 4 ? 0.5 : 1.0)));
    document.getElementById("btnZoomOut").addEventListener("click", () => applyZoom(currentZoom - (currentZoom <= 4 ? 0.5 : 1.0)));
    document.getElementById("btnZoomReset").addEventListener("click", () => applyZoom(4.0));

    // Wheel Zoom & Pan
    document.querySelectorAll("[data-zoom-container]").forEach(container => {
      container.addEventListener("wheel", (e) => {
        e.preventDefault();
        const step = currentZoom < 4 ? 0.25 : 0.5;
        applyZoom(currentZoom + (e.deltaY < 0 ? step : -step));
      }, { passive: false });

      let isPanning = false, startX = 0, startY = 0, scrollLeft = 0, scrollTop = 0;
      container.addEventListener("mousedown", (e) => {
        const isMiddle = e.button === 1;
        const isInspect = nativeBrushSelect && nativeBrushSelect.value === "inspect";
        if (isMiddle || (isInspect && e.button === 0)) {
          e.preventDefault();
          isPanning = true;
          startX = e.pageX - container.offsetLeft;
          startY = e.pageY - container.offsetTop;
          scrollLeft = container.scrollLeft;
          scrollTop = container.scrollTop;
          container.classList.add("panning");
        }
      });
      window.addEventListener("mousemove", (e) => {
        if (!isPanning) return;
        e.preventDefault();
        container.scrollLeft = scrollLeft - (e.pageX - container.offsetLeft - startX);
        container.scrollTop = scrollTop - (e.pageY - container.offsetTop - startY);
      });
      window.addEventListener("mouseup", () => {
        if (isPanning) { isPanning = false; container.classList.remove("panning"); }
      });
    });

    const resultPreviewImg = document.getElementById("resultPreview");
    if (resultPreviewImg) {
      resultPreviewImg.addEventListener("click", (e) => {
        const cols = Number(document.getElementById("cols")?.value) || 4;
        const rows = Number(document.getElementById("rows")?.value) || 7;
        const rect = resultPreviewImg.getBoundingClientRect();
        const col = Math.floor(((e.clientX - rect.left) / rect.width) * cols);
        const row = Math.floor(((e.clientY - rect.top) / rect.height) * rows);
        const targetFrame = row * cols + col + 1;
        if (targetFrame >= 1 && targetFrame <= cols * rows) {
          frameInput.value = targetFrame;
          frameInput.dispatchEvent(new Event("change"));
          showTab("inspector");
        }
      });
    }

    // =========================================================================
    // 4. Tab Switching
    // =========================================================================
    const btnInspector = document.getElementById("tabBtnInspector");
    const btnSheet = document.getElementById("tabBtnSheet");
    const tabInspector = document.getElementById("inspectorTab");
    const tabSheet = document.getElementById("sheetTab");

    function showTab(tabName) {
      if (tabName === "inspector") {
        btnInspector.classList.add("active", "border-teal-400", "text-teal-300", "bg-as-subpanel");
        btnInspector.classList.remove("border-transparent", "text-slate-400");
        btnSheet.classList.remove("active", "border-teal-400", "text-teal-300", "bg-as-subpanel");
        btnSheet.classList.add("border-transparent", "text-slate-400");
        tabInspector.classList.remove("hidden");
        tabSheet.classList.add("hidden");
        // Sync zoom when switching
        if (zoomSelect) applyZoom(Number(zoomSelect.value) || 4.0, "inspector");
      } else {
        btnSheet.classList.add("active", "border-teal-400", "text-teal-300", "bg-as-subpanel");
        btnSheet.classList.remove("border-transparent", "text-slate-400");
        btnInspector.classList.remove("active", "border-teal-400", "text-teal-300", "bg-as-subpanel");
        btnInspector.classList.add("border-transparent", "text-slate-400");
        tabSheet.classList.remove("hidden");
        tabInspector.classList.add("hidden");
        // Sync zoom when switching
        if (sheetZoomSelect) applyZoom(Number(sheetZoomSelect.value) || 2.0, "sheet");
      }
      saveLayout();
    }

    btnInspector.addEventListener("click", () => showTab("inspector"));
    btnSheet.addEventListener("click", () => showTab("sheet"));

    const observer = new MutationObserver(() => {
      const stage = document.getElementById("resultStage");
      if (stage && stage.classList.contains("loaded") && !btnSheet.dataset.autoSwitched) {
        btnSheet.dataset.autoSwitched = "true";
        showTab("sheet");
        updateFrameThumbnails();
      }
    });
    const resultStage = document.getElementById("resultStage");
    if (resultStage) observer.observe(resultStage, { attributes: true, attributeFilter: ["class"] });

    // =========================================================================
    // 5. Auto Cut Frame Previews & Render Animation Matrix
    // =========================================================================
    const frameInput = document.getElementById("frame");
    const matrixScrollEl = document.getElementById("timelineMatrixScroll");
    const currentAnimBadge = document.getElementById("currentAnimBadge");

    function renderAnimationTimeline() {
      if (!matrixScrollEl) return;
      const currentFrame = parseInt(frameInput.value, 10) || 1;
      let activeAnim = ANIMATION_DEFS.find(a => a.frames.includes(currentFrame)) || ANIMATION_DEFS[0];

      if (currentAnimBadge) currentAnimBadge.textContent = `${activeAnim.name} (F${currentFrame})`;
      document.getElementById("playerAnimName").textContent = activeAnim.name.toUpperCase();
      document.getElementById("playerFrameBadge").textContent = `F${currentFrame}`;

      if (matrixScrollEl.childElementCount === 0) {
        matrixScrollEl.innerHTML = "";
        ANIMATION_DEFS.forEach(anim => {
          const row = document.createElement("div");
          row.className = "anim-row" + (anim.id === activeAnim.id ? " current-row" : "");
          row.dataset.animId = anim.id;

          let framesHtml = "";
          anim.frames.forEach((f, idx) => {
            framesHtml += `
              <div class="frame-card ${f === currentFrame ? 'active' : ''}" data-frame="${f}" title="${anim.name} · C${anim.cols[idx]}">
                <div class="frame-card-idx">F${f}</div>
                <div class="frame-card-canvas-box"><canvas width="32" height="32" id="thumbCanvas_${f}"></canvas></div>
              </div>`;
          });

          row.innerHTML = `
            <div class="anim-row-title-box" title="${anim.name}">
              <span class="anim-row-dot" style="background:${anim.color}"></span>
              <span class="anim-row-label">${anim.name}</span>
            </div>
            <div class="anim-frames-strip">${framesHtml}</div>`;

          row.querySelector(".anim-row-title-box").addEventListener("click", () => {
            frameInput.value = anim.frames[0];
            frameInput.dispatchEvent(new Event("change"));
          });
          row.querySelectorAll(".frame-card").forEach(card => {
            card.addEventListener("click", (e) => {
              e.stopPropagation();
              frameInput.value = parseInt(card.dataset.frame, 10);
              frameInput.dispatchEvent(new Event("change"));
            });
          });
          matrixScrollEl.appendChild(row);
        });
      } else {
        matrixScrollEl.querySelectorAll(".anim-row").forEach(row => {
          row.classList.toggle("current-row", row.dataset.animId === activeAnim.id);
        });
        matrixScrollEl.querySelectorAll(".frame-card").forEach(card => {
          card.classList.toggle("active", parseInt(card.dataset.frame, 10) === currentFrame);
        });
      }
      updateFrameThumbnails();
      renderLivePlayerFrame(currentFrame);
    }

    function updateFrameThumbnails() {
      const srcImg = (state && state.result) || (state && state.outfit) || (state && state.base);
      if (!srcImg) return;
      const cols = Number(document.getElementById("cols")?.value) || 4;
      const rows = Number(document.getElementById("rows")?.value) || 7;
      const fw = srcImg.width / cols, fh = srcImg.height / rows;
      for (let f = 1; f <= cols * rows; f++) {
        const cvs = document.getElementById(`thumbCanvas_${f}`);
        if (!cvs) continue;
        const ctx = cvs.getContext("2d");
        ctx.imageSmoothingEnabled = false;
        ctx.clearRect(0, 0, cvs.width, cvs.height);
        const colIdx = (f - 1) % cols, rowIdx = Math.floor((f - 1) / cols);
        ctx.drawImage(srcImg, colIdx * fw, rowIdx * fh, fw, fh, 0, 0, cvs.width, cvs.height);
      }
    }

    // =========================================================================
    // 6. Live Animation Player
    // =========================================================================
    let isPlaying = false, playTimer = null, animPlayFrameIdx = 0;
    const btnPlayPause = document.getElementById("btnPlayPause");
    const animFpsSelect = document.getElementById("animFpsSelect");
    const animPreviewCanvas = document.getElementById("animPreviewCanvas");

    function renderLivePlayerFrame(frameNumber) {
      if (!animPreviewCanvas) return;
      const srcImg = (state && state.result) || (state && state.outfit) || (state && state.base);
      if (!srcImg) return;
      const cols = Number(document.getElementById("cols")?.value) || 4;
      const rows = Number(document.getElementById("rows")?.value) || 7;
      const fw = srcImg.width / cols, fh = srcImg.height / rows;
      animPreviewCanvas.width = fw;
      animPreviewCanvas.height = fh;
      const ctx = animPreviewCanvas.getContext("2d");
      ctx.imageSmoothingEnabled = false;
      ctx.clearRect(0, 0, fw, fh);
      const colIdx = (frameNumber - 1) % cols, rowIdx = Math.floor((frameNumber - 1) / cols);
      ctx.drawImage(srcImg, colIdx * fw, rowIdx * fh, fw, fh, 0, 0, fw, fh);
      document.getElementById("playerFrameBadge").textContent = `F${frameNumber}`;
    }

    function togglePlayPause() {
      isPlaying = !isPlaying;
      if (isPlaying) {
        btnPlayPause.textContent = "❚❚ STOP";
        btnPlayPause.style.background = "#f43f5e";
        btnPlayPause.style.color = "#fff";
        startPlaybackLoop();
      } else {
        btnPlayPause.textContent = "▶ PLAY";
        btnPlayPause.style.background = "";
        btnPlayPause.style.color = "";
        stopPlaybackLoop();
      }
    }

    btnPlayPause.addEventListener("click", togglePlayPause);
    animFpsSelect.addEventListener("change", () => {
      if (isPlaying) { stopPlaybackLoop(); startPlaybackLoop(); }
      saveLayout();
    });

    function startPlaybackLoop() {
      const fps = parseInt(animFpsSelect.value, 10) || 8;
      playTimer = setInterval(() => {
        const currentFrame = parseInt(frameInput.value, 10) || 1;
        let activeAnim = ANIMATION_DEFS.find(a => a.frames.includes(currentFrame)) || ANIMATION_DEFS[0];
        animPlayFrameIdx = (animPlayFrameIdx + 1) % activeAnim.frames.length;
        renderLivePlayerFrame(activeAnim.frames[animPlayFrameIdx]);
      }, 1000 / fps);
    }

    function stopPlaybackLoop() {
      if (playTimer) clearInterval(playTimer);
      playTimer = null;
    }

    frameInput.addEventListener("input", renderAnimationTimeline);
    frameInput.addEventListener("change", renderAnimationTimeline);
    document.getElementById("prev")?.addEventListener("click", () => setTimeout(renderAnimationTimeline, 20));
    document.getElementById("next")?.addEventListener("click", () => setTimeout(renderAnimationTimeline, 20));

    // Hook into render for thumbnail updates
    const origRender = window.render;
    if (typeof origRender === "function") {
      window.render = function() {
        origRender.apply(this, arguments);
        updateFrameThumbnails();
      };
    }

    // =========================================================================
    // 7. Resizable Panel Splitters (Drag-to-Resize)
    // =========================================================================
    function initSplitter(splitterId, panelId, direction, side) {
      const splitter = document.getElementById(splitterId);
      const panel = document.getElementById(panelId);
      if (!splitter || !panel) return;

      let isDragging = false, startPos = 0, startSize = 0;

      splitter.addEventListener("mousedown", (e) => {
        e.preventDefault();
        isDragging = true;
        startPos = direction === "h" ? e.clientY : e.clientX;
        startSize = direction === "h" ? panel.offsetHeight : panel.offsetWidth;
        splitter.classList.add("dragging");
        document.body.classList.add("resizing-panels", direction === "h" ? "resizing-h" : "resizing-v");
      });

      window.addEventListener("mousemove", (e) => {
        if (!isDragging) return;
        e.preventDefault();
        const delta = (direction === "h" ? e.clientY : e.clientX) - startPos;
        const sign = (side === "before") ? 1 : -1;
        const newSize = Math.max(
          parseInt(getComputedStyle(panel).minWidth || getComputedStyle(panel).minHeight || "80"),
          Math.min(
            parseInt(getComputedStyle(panel).maxWidth || getComputedStyle(panel).maxHeight || "600"),
            startSize + delta * sign
          )
        );
        if (direction === "h") panel.style.height = newSize + "px";
        else panel.style.width = newSize + "px";
      });

      window.addEventListener("mouseup", () => {
        if (!isDragging) return;
        isDragging = false;
        splitter.classList.remove("dragging");
        document.body.classList.remove("resizing-panels", "resizing-v", "resizing-h");
        saveLayout();
      });
    }

    initSplitter("leftSplitter", "leftPanel", "v", "before");
    initSplitter("rightSplitter", "rightPanel", "v", "after");
    initSplitter("bottomSplitter", "bottomPanel", "h", "after");

    // =========================================================================
    // 8. Layout & State Persistence (localStorage)
    // =========================================================================
    const LAYOUT_KEY = "hkt-pf-layout-v2";
    let saveTimeout = null;

    function saveLayout() {
      clearTimeout(saveTimeout);
      saveTimeout = setTimeout(() => {
        try {
          const data = {
            leftW: document.getElementById("leftPanel")?.style.width,
            rightW: document.getElementById("rightPanel")?.style.width,
            bottomH: document.getElementById("bottomPanel")?.style.height,
            zoom: currentZoom,
            tab: tabSheet?.classList.contains("hidden") ? "inspector" : "sheet",
            tool: currentActiveTool,
            profileTarget: profileTarget,
            brushSize: document.getElementById("brushSize")?.value,
            showMask: document.getElementById("showMask")?.checked,
            maskOpacity: document.getElementById("maskOpacity")?.value,
            showProfile: document.getElementById("showProfile")?.checked,
            fps: animFpsSelect?.value,
            paintColor: paintColorInput?.value,
          };
          localStorage.setItem(LAYOUT_KEY, JSON.stringify(data));
        } catch(_) {}
      }, 150);
    }

    function restoreLayout() {
      try {
        const data = JSON.parse(localStorage.getItem(LAYOUT_KEY));
        if (!data) return;
        const lp = document.getElementById("leftPanel");
        const rp = document.getElementById("rightPanel");
        const bp = document.getElementById("bottomPanel");
        if (data.leftW && lp) lp.style.width = data.leftW;
        if (data.rightW && rp) rp.style.width = data.rightW;
        if (data.bottomH && bp) bp.style.height = data.bottomH;
        
        if (data.tool) setActiveTool(data.tool);
        if (data.profileTarget) { profileTarget = data.profileTarget; updateProfileTargetUI(); }
        if (data.brushSize) document.getElementById("brushSize").value = data.brushSize;
        if (data.showMask !== undefined) document.getElementById("showMask").checked = data.showMask;
        if (data.maskOpacity) document.getElementById("maskOpacity").value = data.maskOpacity;
        if (data.showProfile !== undefined) document.getElementById("showProfile").checked = data.showProfile;
        if (data.fps) animFpsSelect.value = data.fps;
        if (data.paintColor && paintColorInput && swatchPreview) {
          paintColorInput.value = data.paintColor;
          swatchPreview.style.backgroundColor = data.paintColor;
        }

        if (data.tab === "sheet") showTab("sheet");
        
        if (data.zoom != null) applyZoom(data.zoom, data.tab);
      } catch(_) {}
    }

    document.getElementById("brushSize")?.addEventListener("change", saveLayout);
    document.getElementById("showMask")?.addEventListener("change", saveLayout);
    document.getElementById("maskOpacity")?.addEventListener("input", saveLayout);
    document.getElementById("showProfile")?.addEventListener("change", saveLayout);

    // =========================================================================
    // 9. Init
    // =========================================================================
    restoreLayout();
    renderAnimationTimeline();
    window.addEventListener("DOMContentLoaded", renderAnimationTimeline);
    window.addEventListener("load", renderAnimationTimeline);
    setTimeout(renderAnimationTimeline, 250);
