const dataUrl = '../../output/graph_view/3d_view.json';

const layerColorRGB = {
    1: '77, 255, 77',
    2: '77, 166, 255',
    3: '255, 77, 77'
};

const layerName = {
    1: '📄 Patent (明細書)',
    2: '🔑 Keyword (キーワード)',
    3: '🏷️ Cluster (クラスタ)'
};

const infoPanel = document.getElementById('info-panel');
const infoName = document.getElementById('node-name');
const infoType = document.getElementById('node-type');
const infoRels = document.getElementById('node-relations');
const distSlider = document.getElementById('z-distance-slider');
const distValLabel = document.getElementById('z-dist-val');

let activeGroup = null;
let zBaseDistance = parseInt(distSlider.value);
let zThickness = 120;
let maxPatents = 1;

let graphDataRef = { nodes: [], links: [] };

let focusNodeId = null;
let highlightNodes = new Set();
let highlightLinks = new Set();

// ★Shiftキーのホールド状態を管理するフラグ
let isShiftPressed = false;

// -----------------------------------------
// キーボードイベント (Shift押下でパネル固定)
// -----------------------------------------
window.addEventListener('keydown', (e) => {
    if (e.key === 'Shift' && !isShiftPressed) {
        isShiftPressed = true;
        // マウスイベントを有効にしてスクロール可能にする
        infoPanel.style.pointerEvents = 'auto';
        infoPanel.style.borderColor = '#ffeb3b'; // ホールド中がわかるように枠線を黄色に
    }
});

window.addEventListener('keyup', (e) => {
    if (e.key === 'Shift') {
        isShiftPressed = false;
        // マウスイベントを無効に戻す
        infoPanel.style.pointerEvents = 'none';
        infoPanel.style.borderColor = '#444'; // 枠線を元に戻す
    }
});


// -----------------------------------------
// Utility
// -----------------------------------------
function getNodeId(nodeOrId) {
    return typeof nodeOrId === 'object'
        ? nodeOrId.id
        : nodeOrId;
}

function getNodeGroup(nodeId) {
    const node = graphDataRef.nodes.find(n => n.id === nodeId);
    return node ? node.group : null;
}

function refreshGraphStyle() {
    Graph
        .nodeColor(Graph.nodeColor())
        .linkColor(Graph.linkColor())
        .linkWidth(Graph.linkWidth())
        .linkDirectionalParticles(Graph.linkDirectionalParticles());
}


// -----------------------------------------
// Node Color
// -----------------------------------------
function getNodeColor(node) {

    if (focusNodeId) {
        if (node.id === focusNodeId) {
            return 'rgba(255, 235, 59, 1)';
        }
        if (highlightNodes.has(node.id)) {
            return `rgba(${layerColorRGB[node.group]}, 1)`;
        }
        return `rgba(${layerColorRGB[node.group]}, 0.01)`;
    }

    const rgb = layerColorRGB[node.group] || '255,255,255';

    if (activeGroup === null || activeGroup === node.group) {
        return `rgba(${rgb}, 1)`;
    }
    return `rgba(${rgb}, 0.1)`;
}


// -----------------------------------------
// Link Color
// -----------------------------------------
function getLinkColor(link) {

    const isClusterLink = link.type === 'cluster-cluster';

    if (focusNodeId) {
        if (highlightLinks.has(link)) {
            return isClusterLink
                ? 'rgba(255,255,255,0.95)'
                : 'rgba(255,255,255,0.55)';
        }
        return 'rgba(255,255,255,0)';
    }

    if (isClusterLink) {
        return 'rgba(255,255,255,0.6)';
    }

    if (activeGroup === null) {
        return 'rgba(255,255,255,0.2)';
    }

    const sGroup = getNodeGroup(getNodeId(link.source));
    const tGroup = getNodeGroup(getNodeId(link.target));

    if (sGroup === activeGroup || tGroup === activeGroup) {
        return 'rgba(255,255,255,0.4)';
    }
    return 'rgba(255,255,255,0.03)';
}


// -----------------------------------------
// Link Width
// -----------------------------------------
function getLinkWidth(link) {

    const isClusterLink = link.type === 'cluster-cluster';

    if (focusNodeId && highlightLinks.has(link)) {
        return isClusterLink ? 4.0 : 2.0;
    }
    return isClusterLink ? 1.5 : 0.3;
}


// -----------------------------------------
// Graph
// -----------------------------------------
const Graph = ForceGraph3D()(document.getElementById('3d-graph'))
    .nodeColor(getNodeColor)
    .nodeVal('val')
    .nodeLabel('name')
    .linkWidth(getLinkWidth)
    .linkColor(getLinkColor)
    .linkCurvature(link => link.type === 'cluster-cluster' ? 0.3 : 0)
    .linkCurveRotation(link => link.type === 'cluster-cluster' ? Math.PI / 2 : 0)

    .linkDirectionalParticles(link => {
        if (link.type !== 'cluster-cluster') return 0;
        if (focusNodeId && highlightLinks.has(link)) return 4;
        return 0;
    })

    .linkDirectionalParticleSpeed(0.01)
    .linkDirectionalParticleWidth(3)

    // Hover
    .onNodeHover(node => {

        // ★Shiftキーが押されている間は、ホバーイベントを無視してパネル内容を維持
        if (isShiftPressed) {
            return;
        }

        if (
            focusNodeId &&
            node &&
            !highlightNodes.has(node.id)
        ) {
            node = null;
        }

        if (
            node &&
            activeGroup !== null &&
            node.group !== activeGroup &&
            !focusNodeId
        ) {
            node = null;
        }

        if (node) {

            infoName.textContent = node.name;
            infoType.textContent = layerName[node.group] || 'Unknown';

            document.body.style.cursor = 'pointer';

            infoRels.innerHTML = '';

            // Cluster relation panel
            if (node.group === 3) {

                const relLinks = graphDataRef.links.filter(link => {
                    if (link.type !== 'cluster-cluster') return false;
                    const sId = getNodeId(link.source);
                    const tId = getNodeId(link.target);
                    return sId === node.id || tId === node.id;
                });

                if (relLinks.length > 0) {

                    const unique = new Set();
                    let html = `<div style="color:#aaa;margin-bottom:5px;">【他クラスタとの関係性】</div>`;

                    relLinks.forEach(link => {
                        const sId = getNodeId(link.source);
                        const tId = getNodeId(link.target);

                        const targetNode = sId === node.id
                            ? (typeof link.target === 'object' ? link.target : graphDataRef.nodes.find(n => n.id === tId))
                            : (typeof link.source === 'object' ? link.source : graphDataRef.nodes.find(n => n.id === sId));

                        if (!targetNode || unique.has(targetNode.id)) return;
                        unique.add(targetNode.id);

                        html += `
                            <div class="relation-item">
                                <span class="relation-target">⇔ ${targetNode.name}</span>
                                ${link.desc || '関連あり'}
                            </div>
                        `;
                    });
                    infoRels.innerHTML = html;
                }
            }
        } else {
            infoName.textContent = 'ノードにホバーしてください';
            infoType.textContent = '';
            infoRels.innerHTML = '';
            document.body.style.cursor = 'default';
        }
    });


// -----------------------------------------
// Default click zoom OFF
// -----------------------------------------
Graph.onNodeClick(null);


// -----------------------------------------
// Custom Left Click
// -----------------------------------------
Graph.onNodeClick((node, event) => {
    event.preventDefault();
    if (activeGroup !== null && node.group !== activeGroup && !focusNodeId) return;
    handleNodeClick(node);
});


// -----------------------------------------
// Right Click = Camera Focus
// -----------------------------------------
Graph.onNodeRightClick(node => {
    if (activeGroup !== null && node.group !== activeGroup && !focusNodeId) return;
    const distance = 500;
    const distRatio = 1 + distance / Math.hypot(node.x, node.y, node.z);
    Graph.cameraPosition(
        { x: node.x * distRatio, y: node.y * distRatio, z: node.z * distRatio },
        node,
        1500
    );
});


// Context Menu OFF
document
    .getElementById('3d-graph')
    .addEventListener('contextmenu', event => event.preventDefault());


// Charge Force
Graph.d3Force('charge').strength(-100);


// -----------------------------------------
// Click Logic
// -----------------------------------------
function handleNodeClick(node) {

    if (focusNodeId === node.id) {
        focusNodeId = null;
        highlightNodes.clear();
        highlightLinks.clear();
        refreshGraphStyle();
        return;
    }

    focusNodeId = node.id;
    highlightNodes.clear();
    highlightLinks.clear();
    highlightNodes.add(node.id);

    const relatedClusters = new Set();

    // 1-hop
    graphDataRef.links.forEach(link => {
        const sId = getNodeId(link.source);
        const tId = getNodeId(link.target);

        if (sId === node.id || tId === node.id) {
            highlightLinks.add(link);
            highlightNodes.add(sId);
            highlightNodes.add(tId);

            if (link.type === 'cluster-cluster') {
                relatedClusters.add(sId === node.id ? tId : sId);
            }
        }
    });

    // 2-hop
    graphDataRef.links.forEach(link => {
        const sId = getNodeId(link.source);
        const tId = getNodeId(link.target);

        if (relatedClusters.has(sId) || relatedClusters.has(tId)) {
            if (link.type !== 'cluster-cluster') {
                highlightLinks.add(link);
                highlightNodes.add(sId);
                highlightNodes.add(tId);
            }
        }
    });

    // 3-hop: Keyword -> Patent の展開
    const extraNodes = new Set();
    
    graphDataRef.links.forEach(link => {
        const sId = getNodeId(link.source);
        const tId = getNodeId(link.target);

        if (highlightNodes.has(sId) || highlightNodes.has(tId)) {
            const sGroup = getNodeGroup(sId);
            const tGroup = getNodeGroup(tId);

            if (sGroup === 1 || tGroup === 1) {
                highlightLinks.add(link);
                extraNodes.add(sId);
                extraNodes.add(tId);
            }
        }
    });

    extraNodes.forEach(id => highlightNodes.add(id));
    refreshGraphStyle();
}


// -----------------------------------------
// Custom Forces
// -----------------------------------------
let simulationNodes = [];

const forceZCustom = function(alpha) {
    simulationNodes.forEach(node => {
        const baseZ = node.group === 1 ? -zBaseDistance : (node.group === 3 ? zBaseDistance : 0);
        const targetZ = baseZ + (node.zOffset || 0);
        node.vz += (targetZ - node.z) * alpha * 0.8;
    });
};

forceZCustom.initialize = function(nodes) {
    simulationNodes = nodes;
};


const forceRadialCustom = function(alpha) {
    simulationNodes.forEach(node => {
        if (node.group === 3) {
            const ratio = (node.patent_count || 1) / Math.max(1, maxPatents);
            const targetRadius = Math.pow((1 - ratio), 2) * 1500;
            const currentRadius = Math.sqrt(node.x * node.x + node.y * node.y) || 1;
            const dr = targetRadius - currentRadius;

            node.vx += (node.x / currentRadius) * dr * alpha * 0.3;
            node.vy += (node.y / currentRadius) * dr * alpha * 0.3;
        } else {
            node.vx -= node.x * alpha * 0.01;
            node.vy -= node.y * alpha * 0.01;
        }
    });
};

forceRadialCustom.initialize = function(nodes) {
    simulationNodes = nodes;
};


// -----------------------------------------
// Load Graph
// -----------------------------------------
fetch(dataUrl)
    .then(res => res.json())
    .then(data => {

        graphDataRef = data;

        const clusterNodes = data.nodes.filter(n => n.group === 3);
        if (clusterNodes.length > 0) {
            maxPatents = Math.max(...clusterNodes.map(n => n.patent_count || 0));
        }

        data.nodes.forEach(node => {
            node.zOffset = (Math.random() - 0.5) * zThickness;
        });

        Graph.graphData(data);
        Graph.d3Force('customZ', forceZCustom);
        Graph.d3Force('customRadial', forceRadialCustom);
    });


// -----------------------------------------
// Slider
// -----------------------------------------
distSlider.addEventListener('input', e => {
    zBaseDistance = parseInt(e.target.value);
    distValLabel.textContent = zBaseDistance;
    Graph.d3ReheatSimulation();
});


// -----------------------------------------
// Legend
// -----------------------------------------
const legendItems = document.querySelectorAll('.legend-item');

legendItems.forEach(item => {
    item.addEventListener('click', () => {
        const group = parseInt(item.getAttribute('data-group'));

        if (activeGroup === group) {
            activeGroup = null;
            legendItems.forEach(el => { el.style.opacity = 1.0; });
        } else {
            activeGroup = group;
            legendItems.forEach(el => {
                if (parseInt(el.getAttribute('data-group')) === group) {
                    el.style.opacity = 1.0;
                } else {
                    el.style.opacity = 0.4;
                }
            });
        }
        refreshGraphStyle();
    });
});

// -----------------------------------------
// Reset Focus Button
// -----------------------------------------
const resetFocusBtn = document.getElementById('reset-focus-btn');
if (resetFocusBtn) {
    resetFocusBtn.addEventListener('click', () => {
        if (focusNodeId !== null) {
            focusNodeId = null;
            highlightNodes.clear();
            highlightLinks.clear();
            refreshGraphStyle();
        }
    });
}