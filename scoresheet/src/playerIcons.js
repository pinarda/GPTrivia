import { getDisplayNameForPlayerField } from './playerScores';

export function readPlayerIconMap(doc = document) {
  const iconMapNode = doc.getElementById('scoresheet-player-icons');
  if (!iconMapNode) {
    return {};
  }

  try {
    const parsedMap = JSON.parse(iconMapNode.textContent || '{}');
    return parsedMap && typeof parsedMap === 'object' ? parsedMap : {};
  } catch (error) {
    return {};
  }
}

export function getPlayerIconUrl(playerIconMap, playerField) {
  if (!playerIconMap || typeof playerIconMap !== 'object') {
    return '';
  }

  return (
    playerIconMap[playerField] ||
    playerIconMap[getDisplayNameForPlayerField(playerField)] ||
    ''
  );
}
