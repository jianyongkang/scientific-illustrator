#target illustrator
(function () {
    function fail(message) { throw new Error(message); }
    function cfg(name, fallback) {
        if (typeof SI_CONFIG !== 'undefined' && SI_CONFIG && SI_CONFIG[name] !== undefined && SI_CONFIG[name] !== null && SI_CONFIG[name] !== '') return SI_CONFIG[name];
        return fallback;
    }
    function findLayer(doc, name) { try { return doc.layers.getByName(name); } catch (e) { return null; } }
    function hasMarker(layer) { try { layer.groupItems.getByName('__SI_GENERATED__'); return true; } catch (e) { return false; } }
    if (app.documents.length === 0) fail('No Illustrator document is open.');
    var doc = app.activeDocument;
    var layerName = String(cfg('layerName', 'SI_redraw'));
    if (layerName.indexOf('SI_') !== 0) fail('Generated layer name must begin with SI_.');
    var layer = findLayer(doc, layerName);
    if (!layer) return 'RESET_NOOP|layer=' + layerName;
    if (!hasMarker(layer)) fail('Refusing to remove an unmarked user layer: ' + layerName);
    if (layer.locked) fail('Generated layer is locked: ' + layerName);
    layer.remove(); app.redraw();
    return 'RESET_OK|layer=' + layerName;
})();
