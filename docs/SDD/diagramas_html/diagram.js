/* GammaLab 2.0 — diagramas de clases editables.
   initDiagram(): dibuja las líneas entre cajas calculando su posición real en pantalla
                  (no coordenadas fijas), permite arrastrar cajas desde su barra superior,
                  agregar líneas nuevas a mano y editar/borrar el texto de cualquier línea.
   exportBoardAsPNG(): exporta el diagrama (cajas + líneas) como PNG en alta resolución. */

function initDiagram(boardId, svgId, initialConnections) {
    const board = document.getElementById(boardId);
    const svg = document.getElementById(svgId);
    const connections = (initialConnections || []).map(function (c) { return Object.assign({}, c); });

    let connectMode = false;
    let pendingFrom = null;
    let dragEl = null, dragOffsetX = 0, dragOffsetY = 0, dragMoved = false;

    if (!board || !svg) {
        return { render: function () {}, setConnectMode: function () {}, getConnections: function () { return connections; } };
    }

    function pointOnRectTowards(rect, targetX, targetY) {
        const cx = rect.left + rect.width / 2;
        const cy = rect.top + rect.height / 2;
        const dx = targetX - cx;
        const dy = targetY - cy;
        if (dx === 0 && dy === 0) return { x: cx, y: cy };
        const halfW = rect.width / 2, halfH = rect.height / 2;
        const scaleX = halfW / (Math.abs(dx) || 1e-6);
        const scaleY = halfH / (Math.abs(dy) || 1e-6);
        const scale = Math.min(scaleX, scaleY);
        return { x: cx + dx * scale, y: cy + dy * scale };
    }

    function render() {
        const boardRect = board.getBoundingClientRect();
        svg.setAttribute('width', board.scrollWidth);
        svg.setAttribute('height', board.scrollHeight);
        svg.innerHTML =
            '<defs>' +
            '<marker id="arrow-solid" markerWidth="10" markerHeight="10" refX="8" refY="3" orient="auto" markerUnits="userSpaceOnUse">' +
            '<path d="M0,0 L8,3 L0,6 Z" fill="#5a6b57"></path></marker>' +
            '<marker id="arrow-hollow" markerWidth="14" markerHeight="12" refX="11" refY="5" orient="auto" markerUnits="userSpaceOnUse">' +
            '<path d="M1,1 L12,5 L1,9 Z" fill="#faf9f6" stroke="#555" stroke-width="1"></path></marker>' +
            '</defs>';

        connections.forEach(function (conn) {
            const fromEl = document.getElementById(conn.from);
            const toEl = document.getElementById(conn.to);
            if (!fromEl || !toEl) return;

            const fr = fromEl.getBoundingClientRect();
            const tr = toEl.getBoundingClientRect();
            const fRect = { left: fr.left - boardRect.left, top: fr.top - boardRect.top, width: fr.width, height: fr.height };
            const tRect = { left: tr.left - boardRect.left, top: tr.top - boardRect.top, width: tr.width, height: tr.height };
            const fCenter = { x: fRect.left + fRect.width / 2, y: fRect.top + fRect.height / 2 };
            const tCenter = { x: tRect.left + tRect.width / 2, y: tRect.top + tRect.height / 2 };
            const p1 = pointOnRectTowards(fRect, tCenter.x, tCenter.y);
            const p2 = pointOnRectTowards(tRect, fCenter.x, fCenter.y);

            const isInherit = conn.type === 'inherit';
            const stroke = isInherit ? '#555' : '#5a6b57';
            const marker = isInherit ? 'url(#arrow-hollow)' : 'url(#arrow-solid)';

            const line = document.createElementNS('http://www.w3.org/2000/svg', 'line');
            line.setAttribute('x1', p1.x);
            line.setAttribute('y1', p1.y);
            line.setAttribute('x2', p2.x);
            line.setAttribute('y2', p2.y);
            line.setAttribute('stroke', stroke);
            line.setAttribute('stroke-width', '1.4');
            if (isInherit) line.setAttribute('stroke-dasharray', '6,4');
            line.setAttribute('marker-end', marker);
            line.setAttribute('pointer-events', 'stroke');
            line.style.cursor = 'pointer';
            line.addEventListener('click', function (e) {
                e.stopPropagation();
                if (confirm('¿Eliminar esta línea (' + conn.from + ' → ' + conn.to + ')?')) {
                    const idx = connections.indexOf(conn);
                    if (idx >= 0) connections.splice(idx, 1);
                    render();
                }
            });
            svg.appendChild(line);

            const mx = (p1.x + p2.x) / 2;
            const my = (p1.y + p2.y) / 2;
            const text = document.createElementNS('http://www.w3.org/2000/svg', 'text');
            text.setAttribute('x', mx);
            text.setAttribute('y', my - 5);
            text.setAttribute('font-size', '10.5');
            text.setAttribute('fill', '#444');
            text.setAttribute('text-anchor', 'middle');
            text.setAttribute('pointer-events', 'auto');
            text.style.cursor = 'pointer';
            text.setAttribute('style', 'cursor:pointer; font-family: Segoe UI, Arial, sans-serif; paint-order: stroke; stroke: #faf9f6; stroke-width: 4px;');
            text.textContent = conn.label || '(clic para nombrar)';
            text.addEventListener('click', function (e) {
                e.stopPropagation();
                const newLabel = prompt('Texto de la línea (déjalo vacío para quitarlo):', conn.label || '');
                if (newLabel !== null) {
                    conn.label = newLabel;
                    render();
                }
            });
            svg.appendChild(text);
        });
    }

    // ---------- arrastrar y conectar cajas (ambos desde la barra gris superior) ----------
    board.querySelectorAll('.drag-handle').forEach(function (handle) {
        handle.addEventListener('mousedown', function (e) {
            dragEl = handle.closest('.uml-class');
            if (!dragEl) return;
            dragMoved = false;
            const elRect = dragEl.getBoundingClientRect();
            dragOffsetX = e.clientX - elRect.left;
            dragOffsetY = e.clientY - elRect.top;
            dragEl.style.zIndex = 50;
            e.preventDefault();
        });

        handle.addEventListener('click', function (e) {
            if (dragMoved) return; // fue un arrastre, no un clic de conexión
            if (!connectMode) return;
            const box = handle.closest('.uml-class');
            if (!box) return;
            if (!pendingFrom) {
                pendingFrom = box;
                box.classList.add('connect-source');
            } else if (pendingFrom === box) {
                pendingFrom.classList.remove('connect-source');
                pendingFrom = null;
            } else {
                const label = prompt('Texto de la línea (puedes dejarlo vacío):', '');
                if (label !== null) {
                    const isInherit = confirm('¿Es una relación de herencia / implementación?\n\nAceptar = sí (línea punteada con flecha hueca)\nCancelar = no (asociación normal, flecha sólida)');
                    connections.push({ from: pendingFrom.id, to: box.id, type: isInherit ? 'inherit' : 'assoc', label: label });
                    render();
                }
                pendingFrom.classList.remove('connect-source');
                pendingFrom = null;
            }
        });
    });

    document.addEventListener('mousemove', function (e) {
        if (!dragEl) return;
        dragMoved = true;
        const boardRect = board.getBoundingClientRect();
        let x = e.clientX - boardRect.left - dragOffsetX + board.scrollLeft;
        let y = e.clientY - boardRect.top - dragOffsetY + board.scrollTop;
        x = Math.max(0, x);
        y = Math.max(0, y);
        dragEl.style.left = x + 'px';
        dragEl.style.top = y + 'px';
        render();
    });

    document.addEventListener('mouseup', function () {
        if (dragEl) dragEl.style.zIndex = 2;
        dragEl = null;
    });

    // ---------- guardar / cargar estado ----------
    // El primer hijo de cada caja siempre es la barra de arrastre (drag-handle);
    // se preserva tal cual para no perder sus listeners de eventos al restaurar.
    function getBoxContentHTML(box) {
        let html = '';
        for (let i = 1; i < box.children.length; i++) html += box.children[i].outerHTML;
        return html;
    }

    function setBoxContentHTML(box, html) {
        while (box.children.length > 1) box.removeChild(box.lastChild);
        box.insertAdjacentHTML('beforeend', html);
    }

    function saveState() {
        const boxes = [];
        board.querySelectorAll('.uml-class').forEach(function (box) {
            boxes.push({
                id: box.id,
                left: box.style.left,
                top: box.style.top,
                nuevo: box.classList.contains('nuevo'),
                html: getBoxContentHTML(box)
            });
        });
        return { boxes: boxes, connections: connections };
    }

    function loadState(state) {
        if (!state) return;
        (state.boxes || []).forEach(function (b) {
            const box = document.getElementById(b.id);
            if (!box) return;
            if (b.left) box.style.left = b.left;
            if (b.top) box.style.top = b.top;
            if (typeof b.nuevo === 'boolean') box.classList.toggle('nuevo', b.nuevo);
            if (typeof b.html === 'string') setBoxContentHTML(box, b.html);
        });
        connections.length = 0;
        (state.connections || []).forEach(function (c) { connections.push(c); });
        render();
    }

    render();
    window.addEventListener('resize', render);
    window.addEventListener('load', render);
    setTimeout(render, 150);
    if (window.ResizeObserver) new ResizeObserver(render).observe(board);

    return {
        render: render,
        getConnections: function () { return connections; },
        saveState: saveState,
        loadState: loadState,
        setConnectMode: function (on) {
            connectMode = !!on;
            if (!connectMode && pendingFrom) {
                pendingFrom.classList.remove('connect-source');
                pendingFrom = null;
            }
            board.style.cursor = connectMode ? 'crosshair' : '';
        }
    };
}

function downloadJSON(obj, filename) {
    const blob = new Blob([JSON.stringify(obj, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename || 'estado.json';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    setTimeout(function () { URL.revokeObjectURL(url); }, 2000);
}

function wireSaveLoadButtons(diagram, saveBtnId, loadBtnId, loadInputId, filename) {
    const saveBtn = document.getElementById(saveBtnId);
    const loadBtn = document.getElementById(loadBtnId);
    const loadInput = document.getElementById(loadInputId);
    if (saveBtn) {
        saveBtn.addEventListener('click', function () {
            downloadJSON(diagram.saveState(), filename || 'estado.json');
        });
    }
    if (loadBtn && loadInput) {
        loadBtn.addEventListener('click', function () { loadInput.click(); });
        loadInput.addEventListener('change', function (e) {
            const file = e.target.files[0];
            if (!file) return;
            const reader = new FileReader();
            reader.onload = function () {
                try {
                    diagram.loadState(JSON.parse(reader.result));
                } catch (err) {
                    alert('El archivo no es un estado válido (.json) para este diagrama.');
                    console.error(err);
                }
            };
            reader.readAsText(file);
            e.target.value = '';
        });
    }
}

/* CSS mínimo necesario para que las cajas se vean igual dentro del PNG exportado
   (el <foreignObject> no hereda el <link> de la página, así que se embebe aparte). */
const EXPORT_CSS =
    '.uml-class{position:absolute;width:300px;border-radius:6px;border:1.5px solid #7fae72;' +
    'background:#eaf3e6;overflow:hidden;font-family:"Segoe UI",Arial,sans-serif;color:#222;}' +
    '.uml-class.nuevo{border-color:#c98a8a;background:#fbe9e9;}' +
    '.drag-handle{display:none;}' +
    '.stereotype{text-align:center;font-style:italic;font-size:11px;padding-top:6px;color:#444;}' +
    '.class-name{text-align:center;font-weight:700;font-size:14px;padding:2px 10px 8px 10px;' +
    'border-bottom:1px solid rgba(0,0,0,0.25);}' +
    '.section{padding:6px 10px;border-bottom:1px solid rgba(0,0,0,0.15);' +
    'font-family:Consolas,"Courier New",monospace;font-size:11.5px;line-height:1.55;white-space:pre-wrap;}' +
    '.section:last-child{border-bottom:none;}' +
    '.section.empty{color:#888;font-style:italic;font-family:"Segoe UI",Arial,sans-serif;}' +
    '.new-badge{display:inline-block;font-family:"Segoe UI",Arial,sans-serif;font-size:9.5px;' +
    'font-weight:700;color:#a23b3b;background:#fbe4e4;border:1px solid #c98a8a;border-radius:3px;' +
    'padding:0 4px;margin-left:4px;vertical-align:middle;}';

function exportBoardAsPNG(boardId, svgId, filename, scale) {
    scale = scale || 3;
    const board = document.getElementById(boardId);
    const svgLines = document.getElementById(svgId);
    if (!board) return;

    const width = board.scrollWidth;
    const height = board.scrollHeight;

    const boxesWrap = document.createElement('div');
    boxesWrap.setAttribute('xmlns', 'http://www.w3.org/1999/xhtml');
    boxesWrap.style.position = 'relative';
    boxesWrap.style.width = width + 'px';
    boxesWrap.style.height = height + 'px';
    board.querySelectorAll('.uml-class').forEach(function (box) {
        const clone = box.cloneNode(true);
        clone.classList.remove('connect-source');
        clone.querySelectorAll('[contenteditable]').forEach(function (el) {
            el.removeAttribute('contenteditable');
        });
        boxesWrap.appendChild(clone);
    });

    const svgNS = 'http://www.w3.org/2000/svg';
    const exportSvg = document.createElementNS(svgNS, 'svg');
    exportSvg.setAttribute('xmlns', svgNS);
    exportSvg.setAttribute('width', width);
    exportSvg.setAttribute('height', height);
    exportSvg.setAttribute('viewBox', '0 0 ' + width + ' ' + height);

    const styleEl = document.createElementNS(svgNS, 'style');
    styleEl.textContent = EXPORT_CSS;
    exportSvg.appendChild(styleEl);

    const bg = document.createElementNS(svgNS, 'rect');
    bg.setAttribute('width', width);
    bg.setAttribute('height', height);
    bg.setAttribute('fill', '#faf9f6');
    exportSvg.appendChild(bg);

    if (svgLines) {
        const linesClone = svgLines.cloneNode(true);
        while (linesClone.firstChild) {
            exportSvg.appendChild(linesClone.firstChild);
        }
    }

    const fo = document.createElementNS(svgNS, 'foreignObject');
    fo.setAttribute('x', '0');
    fo.setAttribute('y', '0');
    fo.setAttribute('width', width);
    fo.setAttribute('height', height);
    fo.appendChild(boxesWrap);
    exportSvg.appendChild(fo);

    const svgString = new XMLSerializer().serializeToString(exportSvg);
    const svgUrl = 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(svgString);

    const img = new Image();
    img.onload = function () {
        const canvas = document.createElement('canvas');
        canvas.width = Math.max(1, Math.round(width * scale));
        canvas.height = Math.max(1, Math.round(height * scale));
        const ctx = canvas.getContext('2d');
        ctx.fillStyle = '#faf9f6';
        ctx.fillRect(0, 0, canvas.width, canvas.height);
        ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
        canvas.toBlob(function (blob) {
            if (!blob) {
                alert('No se pudo generar el PNG. Revisa la consola (F12).');
                return;
            }
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = filename || 'diagrama.png';
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            setTimeout(function () { URL.revokeObjectURL(url); }, 2000);
        }, 'image/png');
    };
    img.onerror = function (e) {
        alert('No se pudo generar la imagen. Revisa la consola (F12) para más detalle.');
        console.error('Export error', e);
    };
    img.src = svgUrl;
}
