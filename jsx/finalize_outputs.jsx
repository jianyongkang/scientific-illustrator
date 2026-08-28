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

    function normPath(value) {
        return String(value).replace(/\//g, '\\').toLowerCase();
    }

    function samePath(a, b) {
        return normPath(a) === normPath(b);
    }

    if (app.documents.length === 0) {
        fail('No Illustrator document is open.');
    }

    var doc = app.activeDocument;
    var aiPath = cfg('aiCopyPath', '');
    var pdfPath = cfg('pdfPath', '');
    var allowOverwriteOriginal = Boolean(cfg('allowOverwriteOriginal', false));
    var allowOverwriteOutput = Boolean(cfg('allowOverwriteOutput', false));

    if (!aiPath) {
        fail('aiCopyPath is missing from SI_CONFIG.');
    }
    if (!pdfPath) {
        fail('pdfPath is missing from SI_CONFIG.');
    }
    if (samePath(aiPath, pdfPath)) {
        fail('AI and PDF output paths must be different.');
    }

    var originalPath = '';
    try {
        if (doc.fullName) {
            originalPath = doc.fullName.fsName;
        }
    } catch (e) {
        originalPath = '';
    }

    if (originalPath && samePath(originalPath, aiPath) && !allowOverwriteOriginal) {
        fail('Refusing to overwrite the active document original. Choose a different AiCopyPath or explicitly allow overwrite.');
    }

    var aiFile = new File(aiPath);
    var pdfFile = new File(pdfPath);

    if (aiFile.exists && !allowOverwriteOutput) {
        fail('AI output already exists. Choose a new path or explicitly allow output overwrite: ' + aiPath);
    }
    if (pdfFile.exists && !allowOverwriteOutput) {
        fail('PDF output already exists. Choose a new path or explicitly allow output overwrite: ' + pdfPath);
    }

    if (allowOverwriteOutput) {
        if (aiFile.exists && (!originalPath || !samePath(aiFile.fsName, originalPath) || allowOverwriteOriginal)) {
            aiFile.remove();
        }
        if (pdfFile.exists) {
            pdfFile.remove();
        }
    }

    var aiOptions = new IllustratorSaveOptions();
    aiOptions.pdfCompatible = true;
    aiOptions.compressed = true;

    var pdfOptions = new PDFSaveOptions();
    pdfOptions.preserveEditability = true;
    pdfOptions.generateThumbnails = true;

    doc.saveAs(aiFile, aiOptions);

    var pdfSaved = false;
    try {
        doc.saveAs(pdfFile, pdfOptions);
        pdfSaved = true;
    } finally {
        doc.saveAs(aiFile, aiOptions);
    }

    if (!pdfSaved) {
        fail('PDF save did not complete. The AI working copy was restored.');
    }

    app.redraw();
    return 'FINALIZE_OK|ai=' + aiPath + '|pdf=' + pdfPath + '|original=' + originalPath;
})();
