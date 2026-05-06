// 生成されたデータの相対パス
const dataUrl = '../../output/graph_view/3d_view.json';

// ノードの基本色 (RGB表現: 透過計算用)
const layerColorRGB = {
    1: '77, 255, 77',   // #4dff4d (緑)
    2: '77, 166, 255',  // #4da6ff (青)
    3: '255, 77, 77'    // #ff4d4d (赤)
};

// 名称設定
const layerName = {
    1: '📄 Patent (明細書)',
    2: '🔑 Keyword (キーワード)',
    3: '🏷️ Cluster (クラスタ)'
};

// UI Elements & State
const infoName = document.getElementById('node-name');
const infoType = document.getElementById('node-type');
const distSlider = document.getElementById('z-distance-slider');
const distValLabel = document.getElementById('z-dist-val');

let activeGroup = null; // null: すべて表示, 1|2|3: 選択されたグループのみ強調
let zBaseDistance = parseInt(distSlider.value); // レイヤー間の基準距離
let zThickness = 120; // レイヤーの「厚み」の範囲 (乱数で散らす幅)
let maxPatents = 1; // 引力計算用の最大特許数

// -----------------------------------------
// 1. ノード・リンクの透過処理関数
// -----------------------------------------
function getNodeColor(node) {
    const rgb = layerColorRGB[node.group] || '255,255,255';
    if (activeGroup === null || activeGroup === node.group) {
        return `rgba(${rgb}, 1)`;
    }
    return `rgba(${rgb}, 0.15)`; // 見えにくくする
}

function getLinkColor(link) {
    if (activeGroup === null) return 'rgba(255,255,255,0.2)';
    
    const sGroup = typeof link.source === 'object' ? link.source.group : null;
    const tGroup = typeof link.target === 'object' ? link.target.group : null;

    if (sGroup === activeGroup || tGroup === activeGroup) {
        return 'rgba(255,255,255,0.4)';
    }
    return 'rgba(255,255,255,0.02)';
}

// -----------------------------------------
// 2. グラフの初期化
// -----------------------------------------
const Graph = ForceGraph3D()(document.getElementById('3d-graph'))
    .nodeColor(getNodeColor)
    .nodeVal('val')
    .nodeLabel('name')
    .linkWidth(0.5)
    .linkColor(getLinkColor)
    .onNodeHover(node => {
        // ★追加: レイヤー強調中は、対象外のレイヤーノードを無視する（反応させない）
        if (node && activeGroup !== null && node.group !== activeGroup) {
            node = null; // 強制的に未選択状態として扱う
        }

        if (node) {
            infoName.textContent = node.name;
            infoType.textContent = layerName[node.group] || 'Unknown';
            document.body.style.cursor = 'pointer';
        } else {
            infoName.textContent = 'ノードにホバーしてください';
            infoType.textContent = '';
            document.body.style.cursor = 'default';
        }
    })
    .onNodeClick(node => {
        // ★追加: レイヤー強調中は、対象外のレイヤーノードのクリックを無視する
        if (activeGroup !== null && node.group !== activeGroup) return;

        // カメラのズーム
        const distance = 200;
        const distRatio = 1 + distance / Math.hypot(node.x, node.y, node.z);
        Graph.cameraPosition(
            { x: node.x * distRatio, y: node.y * distRatio, z: node.z * distRatio },
            node, 2000
        );
    });

// 全体的な反発力（広がり）
Graph.d3Force('charge').strength(-100);

// -----------------------------------------
// 3. カスタムフォース (引力の物理演算)
// -----------------------------------------
let simulationNodes = [];

// 【厚みを持ったZ軸分布フォース】
const forceZCustom = function(alpha) {
    simulationNodes.forEach(node => {
        const baseZ = node.group === 1 ? -zBaseDistance : (node.group === 3 ? zBaseDistance : 0);
        const targetZ = baseZ + (node.zOffset || 0);
        node.vz += (targetZ - node.z) * alpha * 0.8;
    });
};
forceZCustom.initialize = function(nodes) { simulationNodes = nodes; };

// 【中心・外周へのXY配置フォース】
const forceRadialCustom = function(alpha) {
    simulationNodes.forEach(node => {
        if (node.group === 3) {
            // クラスタ：接続特許数が多いほど中心(半径0)に、少ないほど外側に設定
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
// 4. データ読み込みとイベントリスナ
// -----------------------------------------
fetch(dataUrl)
    .then(res => res.json())
    .then(data => {
        const clusterNodes = data.nodes.filter(n => n.group === 3);
        if (clusterNodes.length > 0) {
            maxPatents = Math.max(...clusterNodes.map(n => n.patent_count || 0));
        }

        // 各ノードに厚みとなるランダムなZ軸オフセットを付与
        data.nodes.forEach(node => {
            node.zOffset = (Math.random() - 0.5) * zThickness; 
        });
        
        Graph.graphData(data);
        
        Graph.d3Force('customZ', forceZCustom);
        Graph.d3Force('customRadial', forceRadialCustom);
    })
    .catch(err => {
        console.error("データの読み込みに失敗:", err);
        infoType.textContent = "⚠️ 読み込みエラー";
        infoType.style.color = "#ff4d4d";
        infoName.textContent = "ローカルサーバー経由で開いてください。";
    });

// レイヤー間距離スライダーのイベント
distSlider.addEventListener('input', (e) => {
    zBaseDistance = parseInt(e.target.value);
    distValLabel.textContent = zBaseDistance;
    Graph.d3ReheatSimulation();
});

// 凡例クリック（透過フィルタリング）のイベント
const legendItems = document.querySelectorAll('.legend-item');
legendItems.forEach(item => {
    item.addEventListener('click', () => {
        const group = parseInt(item.getAttribute('data-group'));
        
        if (activeGroup === group) {
            // 解除
            activeGroup = null;
            legendItems.forEach(el => el.style.opacity = 1.0);
        } else {
            // 選択
            activeGroup = group;
            legendItems.forEach(el => {
                if (parseInt(el.getAttribute('data-group')) === group) {
                    el.style.opacity = 1.0;
                } else {
                    el.style.opacity = 0.4;
                }
            });
        }
        
        // 色を再評価
        Graph.nodeColor(Graph.nodeColor())
             .linkColor(Graph.linkColor());
    });
});