#target illustrator

(function () {
    function fail(message) {
        throw new Error(message);
    }

    function cfg(name, fallback) {
        if (typeof SI_CONFIG !== 'undefined' && SI_CONFIG && SI_CONFIG[name] !== undefined && SI_CONFIG[name] !== null && SI_CONFIG[name] !== '') {
            return SI_CONFIG[name];
        }
        return fallback;
    }

    if (app.documents.length === 0) {
        fail('No Illustrator document is open.');
    }

    var doc = app.activeDocument;
    var pngPath = cfg('pngPath', '');
    var scale = Number(cfg('previewScale', 150));
    if (!pngPath) {
        fail('pngPath is missing from SI_CONFIG.');
    }
    if (!(scale > 0 && scale <= 1600)) {
        fail('previewScale must be greater than 0 and at most 1600.');
    }

    var pngFile = new File(pngPath);
    if (pngFile.exists && !pngFile.remove()) {
        fail('Unable to replace existing preview: ' + pngPath);
    }

    var options = new ExportOptionsPNG24();
    options.antiAliasing = true;
    options.transparency = false;
    options.artBoardClipping = true;
    options.horizontalScale = scale;
    options.verticalScale = scale;

    doc.exportFile(pngFile, ExportType.PNG24, options);
    app.redraw();

    return 'EXPORT_PREVIEW_OK|png=' + pngPath + '|scale=' + scale + '|artboard=' + doc.artboards.getActiveArtboardIndex();
})();
