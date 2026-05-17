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

let isShiftPressed = false;

// Category影響度関連の状態
let activeCategory = null;
let nodeInfluences = new Map();

// 隣接関係キャッシュ
let keywordToPatents = new Map();
let clusterToKeywords = new Map();

// -----------------------------------------
// キーボードイベント (Shift)
// -----------------------------------------
window.addEventListener('keydown', (e) => {
    if (e.key === 'Shift' && !isShiftPressed) {
        isShiftPressed = true;
        infoPanel.style.pointerEvents = 'auto';
        infoPanel.style.borderColor = '#ffeb3b';
    }
});

window.addEventListener('keyup', (e) => {
    if (e.key === 'Shift') {
        isShiftPressed = false;
        infoPanel.style.pointerEvents = 'none';
        infoPanel.style.borderColor = '#444';
    }
});

// -----------------------------------------
// Shift固定中のホイールでinfo-panelを縦スクロール
// -----------------------------------------
function normalizeWheelDelta(e) {
    let d = e.deltaY;
    if (e.deltaMode === 1) d *= 16;
    else if (e.deltaMode === 2) d *= infoPanel.clientHeight;
    return d;
}
function handleShiftWheel(e) {
    if (!isShiftPressed) return;
    const scrollable = infoPanel.scrollHeight > infoPanel.clientHeight;
    if (!scrollable) return;
    e.preventDefault();
    e.stopPropagation();
    if (typeof e.stopImmediatePropagation === 'function') e.stopImmediatePropagation();
    infoPanel.scrollTop += normalizeWheelDelta(e);
}
window.addEventListener('wheel', handleShiftWheel, { passive: false, capture: true });
infoPanel.addEventListener('wheel', handleShiftWheel, { passive: false });


// -----------------------------------------
// Utility
// -----------------------------------------
function getNodeId(nodeOrId) {
    return typeof nodeOrId === 'object' ? nodeOrId.id : nodeOrId;
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
        .linkDirectionalParticles(Graph.linkDirectionalParticles())
        .nodeThreeObject(Graph.nodeThreeObject());  // glow球再生成のため
}


// -----------------------------------------
// 影響度の計算
// -----------------------------------------
function buildAdjacency() {
    keywordToPatents.clear();
    clusterToKeywords.clear();

    graphDataRef.links.forEach(link => {
        const sId = getNodeId(link.source);
        const tId = getNodeId(link.target);

        if (link.type === 'keyword-patent') {
            const sGroup = getNodeGroup(sId);
            const kwId = sGroup === 2 ? sId : tId;
            const ptId = sGroup === 2 ? tId : sId;
            if (!keywordToPatents.has(kwId)) keywordToPatents.set(kwId, []);
            keywordToPatents.get(kwId).push(ptId);
        } else if (link.type === 'cluster-keyword') {
            const sGroup = getNodeGroup(sId);
            const clId = sGroup === 3 ? sId : tId;
            const kwId = sGroup === 3 ? tId : sId;
            if (!clusterToKeywords.has(clId)) clusterToKeywords.set(clId, []);
            clusterToKeywords.get(clId).push(kwId);
        }
    });
}

function computeInfluences(targetCategory) {
    nodeInfluences.clear();
    if (!targetCategory) return;

    // 1. Patentレイヤ
    graphDataRef.nodes.forEach(node => {
        if (node.group === 1) {
            nodeInfluences.set(node.id, node.category === targetCategory ? 100 : 0);
        }
    });

    // 2. Keywordレイヤ: 接続Patentの平均
    keywordToPatents.forEach((patentIds, kwId) => {
        if (patentIds.length === 0) { nodeInfluences.set(kwId, 0); return; }
        const sum = patentIds.reduce((acc, pid) => acc + (nodeInfluences.get(pid) || 0), 0);
        nodeInfluences.set(kwId, sum / patentIds.length);
    });

    // 3. Clusterレイヤ: 接続Keywordの平均
    clusterToKeywords.forEach((keywordIds, clId) => {
        if (keywordIds.length === 0) { nodeInfluences.set(clId, 0); return; }
        const sum = keywordIds.reduce((acc, kid) => acc + (nodeInfluences.get(kid) || 0), 0);
        nodeInfluences.set(clId, sum / keywordIds.length);
    });
}


// -----------------------------------------
// Node Color (本体色は維持しつつ、カテゴリ選択中は影響度0を薄くする)
// -----------------------------------------
function getNodeColor(node) {

    // ★カテゴリ選択中: ノード本体の色はそのまま、影響度0のノードのみ透明化
    if (activeCategory) {
        const inf = nodeInfluences.get(node.id) || 0;
        const rgb = layerColorRGB[node.group] || '255,255,255';

        // フォーカス機能との併用も考慮
        if (focusNodeId) {
            if (node.id === focusNodeId) return 'rgba(255, 235, 59, 1)';
            if (highlightNodes.has(node.id)) return `rgba(${rgb}, 1)`;
            // フォーカス中で関連外: 影響度があれば残す、なければ消す
            if (inf > 0.5) return `rgba(${rgb}, 0.4)`;
            return `rgba(${rgb}, 0.01)`;
        }

        // 影響度0は薄く、それ以外は本来の色を維持
        if (inf <= 0.5) {
            return `rgba(${rgb}, 0.05)`;
        }
        return `rgba(${rgb}, 1)`;
    }

    // ----- 既存ロジック -----
    if (focusNodeId) {
        if (node.id === focusNodeId) return 'rgba(255, 235, 59, 1)';
        if (highlightNodes.has(node.id)) return `rgba(${layerColorRGB[node.group]}, 1)`;
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

    if (activeCategory) {
        return isClusterLink ? 'rgba(255,255,255,0.3)' : 'rgba(255,255,255,0.05)';
    }

    if (focusNodeId) {
        if (highlightLinks.has(link)) {
            return isClusterLink ? 'rgba(255,255,255,0.95)' : 'rgba(255,255,255,0.55)';
        }
        return 'rgba(255,255,255,0)';
    }

    if (isClusterLink) return 'rgba(255,255,255,0.6)';
    if (activeGroup === null) return 'rgba(255,255,255,0.2)';

    const sGroup = getNodeGroup(getNodeId(link.source));
    const tGroup = getNodeGroup(getNodeId(link.target));
    if (sGroup === activeGroup || tGroup === activeGroup) return 'rgba(255,255,255,0.4)';
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
// ★白いGlow(後光)オブジェクトの生成
// 影響度に応じた半径・透明度の半透明白球をノード本体に重ねる
// -----------------------------------------
function buildGlowObject(node) {
    if (!activeCategory) return null;
    
    // ★修正: THREEがない環境でエラークラッシュするのを防ぐガード処理
    if (typeof THREE === 'undefined') {
        console.warn("THREE.js is not defined. Please check index.html.");
        return null; 
    }

    const inf = nodeInfluences.get(node.id) || 0;
    if (inf <= 5) return null; // 影響度が小さいときは何も追加しない

    // ノードの推定半径 (3d-force-graphのデフォルト: Math.cbrt(val) * 4)
    const nodeRadius = Math.cbrt(node.val || 1) * 4;

    // 影響度 0-100 を 0-1 に正規化
    const ratio = Math.min(1, inf / 100);

    // glow半径: 本体の 1.6 〜 3.5 倍 (影響度が高いほど大きく)
    const glowRadius = nodeRadius * (1.6 + ratio * 1.9);

    // 透明度: 0.12 〜 0.55 (影響度が高いほど濃く)
    const glowOpacity = 0.12 + ratio * 0.43;

    const glow = new THREE.Mesh(
        new THREE.SphereGeometry(glowRadius, 16, 16),
        new THREE.MeshBasicMaterial({
            color: 0xffffff,
            transparent: true,
            opacity: glowOpacity,
            depthWrite: false  // 後光が他要素を遮らないように
        })
    );

    // glowは内側に小さな2つ目の球も重ね、より「光ってる感」を出す
    const innerGlow = new THREE.Mesh(
        new THREE.SphereGeometry(nodeRadius * (1.2 + ratio * 0.6), 16, 16),
        new THREE.MeshBasicMaterial({
            color: 0xffffff,
            transparent: true,
            opacity: Math.min(0.85, 0.3 + ratio * 0.55),
            depthWrite: false
        })
    );

    const group = new THREE.Group();
    group.add(glow);
    group.add(innerGlow);
    return group;
}


// -----------------------------------------
// Graph 初期化
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
    .nodeThreeObject(node => buildGlowObject(node))
    .nodeThreeObjectExtend(true)
    .onNodeHover(node => {
        if (isShiftPressed) return;

        if (focusNodeId && node && !highlightNodes.has(node.id)) node = null;
        if (node && activeGroup !== null && node.group !== activeGroup && !focusNodeId) node = null;

        if (node) {
            infoName.textContent = node.name;
            infoType.textContent = layerName[node.group] || 'Unknown';
            document.body.style.cursor = 'pointer';
            infoRels.innerHTML = '';

            if (activeCategory) {
                const inf = nodeInfluences.get(node.id);
                if (inf !== undefined) {
                    infoRels.innerHTML = `
                        <div style="color:#ffd54f; font-weight:bold; margin-bottom:6px;">
                            🎯 「${activeCategory}」の影響度: ${inf.toFixed(1)} / 100
                        </div>
                    `;
                }
            }

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
                    infoRels.innerHTML += html;
                }
            }
        } else {
            infoName.textContent = 'ノードにホバーしてください';
            infoType.textContent = '';
            infoRels.innerHTML = '';
            document.body.style.cursor = 'default';
        }
    });

Graph.onNodeClick(null);

Graph.onNodeClick((node, event) => {
    event.preventDefault();
    if (activeGroup !== null && node.group !== activeGroup && !focusNodeId) return;
    handleNodeClick(node);
});

Graph.onNodeRightClick(node => {
    if (activeGroup !== null && node.group !== activeGroup && !focusNodeId) return;
    const distance = 500;
    const distRatio = 1 + distance / Math.hypot(node.x, node.y, node.z);
    Graph.cameraPosition(
        { x: node.x * distRatio, y: node.y * distRatio, z: node.z * distRatio },
        node, 1500
    );
});

document.getElementById('3d-graph').addEventListener('contextmenu', e => e.preventDefault());
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
forceZCustom.initialize = function(nodes) { simulationNodes = nodes; };

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
forceRadialCustom.initialize = function(nodes) { simulationNodes = nodes; };


// -----------------------------------------
// Categoryリストの生成
// -----------------------------------------
function buildCategoryUI() {
    const counts = new Map();
    graphDataRef.nodes.forEach(node => {
        if (node.group === 1 && node.category) {
            counts.set(node.category, (counts.get(node.category) || 0) + 1);
        }
    });

    const sorted = Array.from(counts.entries()).sort((a, b) => b[1] - a[1]);
    const listEl = document.getElementById('category-list');
    listEl.innerHTML = '';

    sorted.forEach(([cat, count]) => {
        const btn = document.createElement('button');
        btn.className = 'category-btn';
        btn.dataset.category = cat;
        btn.innerHTML = `${cat}<span class="category-count">${count}</span>`;
        btn.addEventListener('click', () => {
            selectCategory(cat === activeCategory ? null : cat);
        });
        listEl.appendChild(btn);
    });
}

function selectCategory(cat) {
    activeCategory = cat;
    document.querySelectorAll('.category-btn').forEach(b => {
        b.classList.toggle('active', b.dataset.category === cat);
    });
    document.getElementById('clear-category-btn').disabled = !cat;
    computeInfluences(cat);
    refreshGraphStyle();
}


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

        buildAdjacency();
        buildCategoryUI();
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
                el.style.opacity = parseInt(el.getAttribute('data-group')) === group ? 1.0 : 0.4;
            });
        }
        refreshGraphStyle();
    });
});

const legendEl = document.getElementById('legend');
const legendToggleBtn = document.getElementById('legend-toggle-btn');
if (legendToggleBtn && legendEl) {
    legendToggleBtn.addEventListener('click', () => {
        const minimized = legendEl.classList.toggle('minimized');
        legendToggleBtn.textContent = minimized ? '＋' : '−';
        legendToggleBtn.title = minimized ? '展開' : '最小化';
    });
}

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

document.getElementById('clear-category-btn').addEventListener('click', () => {
    selectCategory(null);
});