function renderRelationGraph(container, relations) {
  if (!container) return;
  if (!relations || relations.length === 0) {
    container.innerHTML = '<p class="text-secondary small mb-0">No relations</p>';
    return;
  }
  const nodes = new vis.DataSet();
  const edges = new vis.DataSet();
  relations.forEach(r => {
    if (!nodes.get(r.source)) nodes.add({ id: r.source, label: r.source });
    if (!nodes.get(r.target)) nodes.add({ id: r.target, label: r.target });
    edges.add({ from: r.source, to: r.target, label: r.relation, arrows: 'to' });
  });
  new vis.Network(container, { nodes, edges }, {});
}

window.renderRelationGraph = renderRelationGraph;

document.addEventListener('DOMContentLoaded', () => {
  const container = document.getElementById('topicRelationGraph');
  if (!container) return;
  let relations = [];
  try {
    relations = JSON.parse(container.dataset.relations || '[]');
  } catch (e) {
    relations = [];
  }
  renderRelationGraph(container, relations);
});
