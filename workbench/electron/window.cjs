const DOCK_WIDTH = 420
const EXPANDED_WIDTH = 780

function dockBounds(workArea, expanded = false) {
  const width = expanded ? EXPANDED_WIDTH : DOCK_WIDTH
  return {
    x: workArea.x,
    y: workArea.y,
    width,
    height: workArea.height,
  }
}

module.exports = { DOCK_WIDTH, EXPANDED_WIDTH, dockBounds }
