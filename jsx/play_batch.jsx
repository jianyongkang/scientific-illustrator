#target illustrator

(function () {
    function fail(message) { throw new Error(message); }
    function cfg(name, fallback) {
        if (typeof SI_CONFIG !== 'undefined' && SI_CONFIG && SI_CONFIG[name] !== undefined && SI_CONFIG[name] !== null && SI_CONFIG[name] !== '') {
            return SI_CONFIG[name];
        }
        return fallback;
    }
    function startsWithSi(name) { return String(name).indexOf('SI_') === 0; }
    function findLayer(doc, name) {
        try { return doc.layers.getByName(name); } catch (e) { return null; }
    }
    function findGroup(container, name) {
        try { return container.groupItems.getByName(name); } catch (e) { return null; }
    }
    function hasGeneratedMarker(layer) { return !!findGroup(layer, '__SI_GENERATED__'); }
    function readTextFile(path) {
        var f = new File(path);
        if (!f.exists) { fail('JSON file does not exist: ' + path); }
        f.encoding = 'UTF-8';
        if (!f.open('r')) { fail('Cannot open JSON file: ' + path); }
        var text = f.read(); f.close(); return text;
    }
    function parseJson(text) {
        if (typeof JSON !== 'undefined' && JSON.parse) { return JSON.parse(text); }
        return eval('(' + text + ')');
    }
    function rgb(values) {
        var c = new RGBColor();
        c.red = Number(values[0]); c.green = Number(values[1]); c.blue = Number(values[2]);
        return c;
    }
    function applyPathStyle(item, style, strokeScale) {
        var hasFill = style && style.fill_rgb !== null && style.fill_rgb !== undefined;
        var hasStroke = style && style.stroke_rgb !== null && style.stroke_rgb !== undefined && Number(style.stroke_width || 0) > 0;
        item.filled = hasFill;
        if (hasFill) { item.fillColor = rgb(style.fill_rgb); }
        item.stroked = hasStroke;
        if (hasStroke) {
            item.strokeColor = rgb(style.stroke_rgb);
            item.strokeWidth = Math.max(0.01, Number(style.stroke_width || 1) * strokeScale);
            try {
                if (style.linecap === 'round') { item.strokeCap = StrokeCap.ROUNDENDCAP; }
                else if (style.linecap === 'square') { item.strokeCap = StrokeCap.PROJECTINGENDCAP; }
                else { item.strokeCap = StrokeCap.BUTTENDCAP; }
            } catch (e1) {}
            try {
                if (style.linejoin === 'round') { item.strokeJoin = StrokeJoin.ROUNDENDJOIN; }
                else if (style.linejoin === 'bevel') { item.strokeJoin = StrokeJoin.BEVELENDJOIN; }
                else { item.strokeJoin = StrokeJoin.MITERENDJOIN; }
            } catch (e2) {}
        }
        var opacity = Number(style && style.opacity !== undefined ? style.opacity : 1);
        item.opacity = Math.max(0, Math.min(100, opacity * 100));
    }
    function createNativePath(doc, parentGroup, atom, mapPoint, strokeScale) {
        var atomGroup = doc.groupItems.add();
        atomGroup.name = 'SI_' + atom.id;
        atomGroup.move(parentGroup, ElementPlacement.PLACEATEND);
        try { atomGroup.zOrder(ZOrderMethod.BRINGTOFRONT); } catch (e0) {}
        var subs = atom.subpaths || [];
        for (var s = 0; s < subs.length; s++) {
            var sp = subs[s];
            var pts = sp.points || [];
            if (pts.length < 2) { continue; }
            var item = doc.pathItems.add();
            item.name = atom.id + '_sub_' + s;
            var anchors = [];
            for (var i = 0; i < pts.length; i++) { anchors.push(mapPoint(pts[i].anchor)); }
            item.setEntirePath(anchors);
            item.closed = !!sp.closed;
            for (var p = 0; p < pts.length; p++) {
                var pp = item.pathPoints[p];
                pp.anchor = mapPoint(pts[p].anchor);
                pp.leftDirection = mapPoint(pts[p].left);
                pp.rightDirection = mapPoint(pts[p].right);
                try {
                    var a0 = mapPoint(pts[p].anchor);
                    var l0 = mapPoint(pts[p].left);
                    var r0 = mapPoint(pts[p].right);
                    var isCorner = Math.abs(a0[0]-l0[0]) < 0.0001 && Math.abs(a0[1]-l0[1]) < 0.0001 && Math.abs(a0[0]-r0[0]) < 0.0001 && Math.abs(a0[1]-r0[1]) < 0.0001;
                    pp.pointType = isCorner ? PointType.CORNER : PointType.SMOOTH;
                } catch (e) {}
            }
            applyPathStyle(item, atom.style || {}, strokeScale);
            item.move(atomGroup, ElementPlacement.PLACEATEND);
        }
        return atomGroup;
    }
    function chooseFont(fontName) {
        if (!fontName) { return null; }
        try { return app.textFonts.getByName(fontName); } catch (e1) {}
        for (var i = 0; i < app.textFonts.length; i++) {
            try {
                if (String(app.textFonts[i].family).toLowerCase() === String(fontName).toLowerCase()) { return app.textFonts[i]; }
            } catch (e2) {}
        }
        return null;
    }
    function createNativeText(doc, parentGroup, atom, mapPoint, textScale) {
        var pos = mapPoint(atom.position || [0, 0]);
        var frame = doc.textFrames.pointText(pos);
        frame.name = 'SI_' + atom.id;
        frame.contents = String(atom.text || '');
        var tr = frame.textRange;
        try { tr.characterAttributes.size = Math.max(0.1, Number(atom.font_size || 12) * textScale); } catch (e1) {}
        var font = chooseFont(atom.font_family || 'Arial');
        if (font) { try { tr.characterAttributes.textFont = font; } catch (e2) {} }
        if (atom.style && atom.style.fill_rgb !== null && atom.style.fill_rgb !== undefined) {
            try { tr.characterAttributes.fillColor = rgb(atom.style.fill_rgb); } catch (e3) {}
        }
        if (atom.style && atom.style.stroke_rgb !== null && atom.style.stroke_rgb !== undefined && Number(atom.style.stroke_width || 0) > 0) {
            try {
                tr.characterAttributes.strokeColor = rgb(atom.style.stroke_rgb);
                tr.characterAttributes.strokeWeight = Number(atom.style.stroke_width || 1) * textScale;
            } catch (e4) {}
        }
        try {
            if (atom.text_anchor === 'middle') { tr.paragraphAttributes.justification = Justification.CENTER; }
            else if (atom.text_anchor === 'end') { tr.paragraphAttributes.justification = Justification.RIGHT; }
            else { tr.paragraphAttributes.justification = Justification.LEFT; }
        } catch (e5) {}
        try { frame.opacity = Math.max(0, Math.min(100, Number(atom.style && atom.style.opacity !== undefined ? atom.style.opacity : 1) * 100)); } catch (e6) {}
        var rotation = Number(atom.rotation || 0);
        if (Math.abs(rotation) > 0.0001) { try { frame.rotate(-rotation); } catch (e7) {} }
        frame.move(parentGroup, ElementPlacement.PLACEATEND);
        try { frame.zOrder(ZOrderMethod.BRINGTOFRONT); } catch (e8) {}
        return frame;
    }

    if (app.documents.length === 0) { fail('No Illustrator document is open.'); }
    var doc = app.activeDocument;
    var layerName = String(cfg('layerName', 'SI_redraw'));
    var batchPath = String(cfg('batchPath', ''));
    var expectedBatch = Number(cfg('batchIndex', -1));
    var fitMode = String(cfg('fitMode', 'contain')).toLowerCase();
    var margin = Number(cfg('marginPoints', 18));
    var delayMs = Math.max(0, Number(cfg('interObjectDelayMs', 0)));
    var viewBox = cfg('viewBox', null);
    var cacheId = String(cfg('cacheId', ''));
    if (!startsWithSi(layerName)) { fail('Generated layer name must begin with SI_.'); }
    if (!batchPath || !viewBox || viewBox.length !== 4) { fail('batchPath/viewBox missing from SI_CONFIG.'); }
    if (fitMode !== 'contain' && fitMode !== 'artboard' && fitMode !== 'none') { fail('Unsupported fitMode: ' + fitMode); }

    var batch = parseJson(readTextFile(batchPath));
    if (Number(batch.batch_index) !== expectedBatch) { fail('Batch index mismatch.'); }
    if (cacheId && String(batch.cache_id) !== cacheId) { fail('Cache id mismatch for batch.'); }

    var layer = findLayer(doc, layerName);
    if (!layer) {
        layer = doc.layers.add(); layer.name = layerName; layer.visible = true; layer.locked = false;
        var marker = layer.groupItems.add(); marker.name = '__SI_GENERATED__'; marker.hidden = true;
    } else {
        if (!hasGeneratedMarker(layer)) { fail('Refusing to draw into an existing layer not marked by scientific-illustrator: ' + layerName); }
        if (layer.locked) { fail('Generated layer is locked: ' + layerName); }
    }

    var indexText = ('000000' + expectedBatch).slice(-6);
    var doneName = '__SI_BATCH_' + indexText + '__';
    var pendingName = '__SI_BATCH_PENDING_' + indexText + '__';
    var done = findGroup(layer, doneName);
    if (done) { return 'BATCH_ALREADY_DONE|batch=' + expectedBatch + '|atoms=' + Number(batch.atom_count || 0); }
    var stalePending = findGroup(layer, pendingName);
    if (stalePending) { stalePending.remove(); }

    var artboardIndex = doc.artboards.getActiveArtboardIndex();
    var rect = doc.artboards[artboardIndex].artboardRect;
    var left = Number(rect[0]), top = Number(rect[1]), right = Number(rect[2]), bottom = Number(rect[3]);
    var artW = right - left, artH = top - bottom;
    var vbx = Number(viewBox[0]), vby = Number(viewBox[1]), vbw = Number(viewBox[2]), vbh = Number(viewBox[3]);
    if (!(vbw > 0 && vbh > 0 && artW > 0 && artH > 0)) { fail('Invalid viewBox or active artboard bounds.'); }
    var sx = 1, sy = 1, targetLeft = left, targetTop = top;
    if (fitMode === 'contain') {
        var aw = Math.max(1, artW - 2 * margin), ah = Math.max(1, artH - 2 * margin);
        sx = sy = Math.min(aw / vbw, ah / vbh);
        targetLeft = left + (artW - vbw * sx) / 2;
        targetTop = top - (artH - vbh * sy) / 2;
    } else if (fitMode === 'artboard') {
        sx = artW / vbw; sy = artH / vbh; targetLeft = left; targetTop = top;
    }
    var strokeScale = Math.sqrt(Math.abs(sx * sy));
    var textScale = strokeScale;
    function mapPoint(p) {
        return [targetLeft + (Number(p[0]) - vbx) * sx, targetTop - (Number(p[1]) - vby) * sy];
    }

    var pending = layer.groupItems.add();
    pending.name = pendingName;
    pending.note = 'scientific-illustrator cache=' + cacheId + ' batch=' + expectedBatch;
    try { pending.zOrder(ZOrderMethod.BRINGTOFRONT); } catch (ePending) {}
    var created = 0;
    try {
        var atoms = batch.atoms || [];
        for (var i = 0; i < atoms.length; i++) {
            var atom = atoms[i];
            if (atom.type === 'path') { createNativePath(doc, pending, atom, mapPoint, strokeScale); }
            else if (atom.type === 'text') { createNativeText(doc, pending, atom, mapPoint, textScale); }
            else { fail('Unsupported atom type: ' + atom.type); }
            created += 1;
            if (delayMs > 0) { app.redraw(); $.sleep(delayMs); }
        }
        pending.name = doneName;
        pending.note = 'scientific-illustrator COMPLETE cache=' + cacheId + ' batch=' + expectedBatch + ' atoms=' + created;
        app.redraw();
    } catch (err) {
        try { pending.remove(); app.redraw(); } catch (cleanupErr) {}
        throw err;
    }
    return 'BATCH_OK|batch=' + expectedBatch + '|atoms=' + created + '|layer=' + layerName + '|artboard=' + artboardIndex + '|fit=' + fitMode;
})();
