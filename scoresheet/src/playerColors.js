export function readPlayerColorMap(doc = document) {
  const colorMapNode = doc.getElementById('scoresheet-player-colors');
  if (!colorMapNode) {
    return {};
  }

  try {
    const parsedMap = JSON.parse(colorMapNode.textContent || '{}');
    return parsedMap && typeof parsedMap === 'object' ? parsedMap : {};
  } catch (error) {
    return {};
  }
}
