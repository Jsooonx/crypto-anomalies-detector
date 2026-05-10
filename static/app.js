/**
 * Crypto Anomaly Detector — Kinetic Brutalism Client
 */

const REFRESH_INTERVAL_MS = 60_000;
let isInitialLoad = true;
let previousData = {};

// DOM Helpers

function $(selector) { return document.querySelector(selector); }

function formatPrice(price) {
    if (price >= 1) return price.toFixed(2);
    if (price >= 0.01) return price.toFixed(4);
    return price.toFixed(6);
}

function formatTimestamp(ts) {
    const d = new Date(ts);
    return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

function formatPercent(value) {
    return (value * 100).toFixed(1) + "%";
}

// Data Fetching

async function fetchAnomalies() {
    try {
        const res = await fetch("/api/anomalies");
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return await res.json();
    } catch (err) {
        return null;
    }
}

async function fetchMetrics() {
    try {
        const res = await fetch("/api/metrics");
        if (!res.ok) return null;
        return await res.json();
    } catch {
        return null;
    }
}

// Rendering

function renderMetricsSidebar(data) {
    const container = $("#metrics-container");
    if (!data) return;

    const pairs = Object.values(data);
    const totalPairs = pairs.length;
    const anomalyCount = pairs.filter(p => p.anomaly_flag).length;
    const normalCount = totalPairs - anomalyCount;
    const avgVotes = pairs.reduce((sum, p) => sum + (p.anomaly_votes || 0), 0) / totalPairs;

    const html = `
        <div class="metric-item ${isInitialLoad ? 'stagger-enter' : ''}" style="animation-delay: 0.1s">
            <span class="metric-label">[COINS_TRACKED]</span>
            <span class="metric-value">${totalPairs}</span>
        </div>
        <div class="metric-item ${isInitialLoad ? 'stagger-enter' : ''}" style="animation-delay: 0.2s">
            <span class="metric-label">[ALERTS_FOUND]</span>
            <span class="metric-value ${anomalyCount > 0 ? 'warn' : 'safe'}">${anomalyCount}</span>
        </div>
        <div class="metric-item ${isInitialLoad ? 'stagger-enter' : ''}" style="animation-delay: 0.3s">
            <span class="metric-label">[NORMAL_COINS]</span>
            <span class="metric-value safe">${normalCount}</span>
        </div>
        <div class="metric-item ${isInitialLoad ? 'stagger-enter' : ''}" style="animation-delay: 0.4s">
            <span class="metric-label">[SYS_CONFIDENCE]</span>
            <span class="metric-value">${avgVotes.toFixed(2)}</span>
        </div>
    `;
    
    // Only replace innerHTML if we need to animate or values changed to prevent DOM thrashing
    // For simplicity in this demo, we replace on initial load, then target specific spans later
    if (isInitialLoad) {
        container.innerHTML = html;
    } else {
        const values = container.querySelectorAll('.metric-value');
        if(values.length === 4) {
            values[0].textContent = totalPairs;
            values[1].textContent = anomalyCount;
            values[2].textContent = normalCount;
            values[3].textContent = avgVotes.toFixed(2);
        } else {
            container.innerHTML = html;
        }
    }
}

function renderPairCard(pair, result, index) {
    const isAnomaly = result.anomaly_flag;
    const cardClass = isAnomaly ? "anomaly" : "normal";
    const badgeClass = isAnomaly ? "alert" : "";
    const badgeText = isAnomaly ? "ALERT_ACTIVE" : "STATUS_CLEAR";
    
    // Check if this pair changed status compared to previous fetch
    const prev = previousData[pair];
    let flashClass = "";
    if (!isInitialLoad && prev && prev.close !== result.close) {
        flashClass = isAnomaly ? "flash-warn" : "flash-safe";
    }
    
    // Stagger animation on first load
    const animClass = isInitialLoad ? "stagger-enter" : "";
    const delay = isInitialLoad ? `animation-delay: ${index * 0.05}s;` : "";

    let scoreRows = "";
    if (result.scores) {
        for (const [model, data] of Object.entries(result.scores)) {
            let modelLabel = model.toUpperCase();
            if (model === "isolation_forest") modelLabel = "PATTERN_SCAN";
            else if (model === "lof") modelLabel = "VOLUME_SCAN";
            else if (model === "ensemble") modelLabel = "COMBINED_AI";
            
            const scoreClass = data.is_anomaly ? "negative" : "positive";
            scoreRows += `
                <div class="detail-row">
                    <span class="detail-label">${modelLabel}</span>
                    <span class="detail-value ${scoreClass}">${data.score.toFixed(3)}</span>
                </div>
            `;
        }
    }

    let historySvg = "";
    if (result.history && result.history.length > 0) {
        const prices = result.history;
        const minP = Math.min(...prices);
        const maxP = Math.max(...prices);
        const range = maxP - minP || 1;
        
        const pts = prices.map((p, i) => {
            const x = (i / (prices.length - 1)) * 100;
            const y = 30 - ((p - minP) / range) * 30;
            return `${x},${y}`;
        }).join(" L ");
        
        const pathClass = isAnomaly ? "sparkline-warn" : "sparkline-safe";
        historySvg = `
            <div class="sparkline-container">
                <svg viewBox="0 -5 100 40" preserveAspectRatio="none" class="sparkline">
                    <path d="M ${pts}" class="${pathClass}" />
                </svg>
            </div>
        `;
    }

    return `
        <div class="pair-card ${cardClass} ${animClass} ${flashClass}" style="${delay}" id="pair-${pair.replace('/', '-')}">
            <div class="pair-header">
                <div style="display: flex; align-items: center; gap: 8px;">
                    <img src="https://cdn.jsdelivr.net/gh/atomiclabs/cryptocurrency-icons@1a63530be6e374711a8554f31b17e4cb92c25fa5/svg/color/${pair.split('/')[0].toLowerCase()}.svg" width="20" height="20" onerror="this.style.display='none'" alt="${pair.split('/')[0]} logo" style="border-radius: 50%; background: #fff;" />
                    <span class="pair-name glitch-text-small" data-text="${pair}">${pair}</span>
                </div>
                <span class="pair-badge ${badgeClass}">${badgeText}</span>
            </div>
            <div class="pair-price">$${formatPrice(result.close)}</div>
            ${historySvg}
            <div class="pair-details">
                <div class="detail-row">
                    <span class="detail-label">TRIGGERS</span>
                    <span class="detail-value">${result.anomaly_votes}/2</span>
                </div>
                <div class="detail-row">
                    <span class="detail-label">VOL</span>
                    <span class="detail-value">${Number(result.volume).toLocaleString()}</span>
                </div>
                ${scoreRows}
                <div class="detail-row">
                    <span class="detail-label">LAST_UPDATE</span>
                    <span class="detail-value">${formatTimestamp(result.timestamp)}</span>
                </div>
            </div>
        </div>
    `;
}

function renderPairsGrid(data) {
    const grid = $("#pairs-grid");
    if (!data) {
        grid.innerHTML = '<div class="loading-text" style="color:var(--accent-warn)">ERR: NO_DATA_STREAM</div>';
        return;
    }

    let html = "";
    let i = 0;
    for (const [pair, result] of Object.entries(data)) {
        if (result.status === "error") {
            const animClass = isInitialLoad ? "stagger-enter" : "";
            const delay = isInitialLoad ? `animation-delay: ${i * 0.05}s;` : "";
            html += `
                <div class="pair-card anomaly ${animClass}" style="${delay}">
                    <div class="pair-header">
                        <span class="pair-name">${pair}</span>
                        <span class="pair-badge alert">ERR_SYSTEM</span>
                    </div>
                    <div style="color:var(--accent-warn); font-size:11px; margin-top:10px;">
                        ${result.error || "UNKNOWN_ERR"}
                    </div>
                </div>
            `;
        } else {
            html += renderPairCard(pair, result, i);
        }
        i++;
    }

    grid.innerHTML = html;
    previousData = data;
}

function renderModelMetrics(metrics) {
    const container = $("#model-grid");
    if (!metrics) {
        container.innerHTML = '<div class="loading-text" style="color:var(--accent-warn)">ERR: NO_METRICS</div>';
        return;
    }

    let html = "";
    let i = 0;
    for (const [model, stats] of Object.entries(metrics)) {
        let modelLabel = model.toUpperCase();
        if (model === "isolation_forest") modelLabel = "PATTERN_SCAN";
        else if (model === "lof") modelLabel = "VOLUME_SCAN";
        else if (model === "ensemble") modelLabel = "COMBINED_AI";
        
        let statsHtml = "";

        for (const [key, value] of Object.entries(stats)) {
            let label = key.toUpperCase();
            const labelMap = {
                "ANOMALIES_DETECTED": "ALERTS_FOUND",
                "ANOMALY_RATE": "ALERT_RATE",
                "AVG_PRICE_MOVE_ANOMALY": "MOVE_ON_ALERT",
                "AVG_PRICE_MOVE_NORMAL": "NORMAL_MOVE",
                "MODEL_AGREEMENT": "AI_AGREEMENT",
                "MOVE_RATIO": "IMPACT_RATIO"
            };
            if (labelMap[label]) label = labelMap[label];

            const formatted = typeof value === "number"
                ? (value < 1 && value > 0 ? formatPercent(value) : value.toFixed(2))
                : value;

            statsHtml += `
                <div class="model-stat">
                    <span class="model-stat-label">${label}</span>
                    <span class="model-stat-value">${formatted}</span>
                </div>
            `;
        }

        const animClass = isInitialLoad ? "stagger-enter" : "";
        const delay = isInitialLoad ? `animation-delay: ${(i * 0.1) + 0.5}s;` : "";

        html += `
            <div class="model-card ${animClass}" style="${delay}">
                <div class="model-name">> ${modelLabel}_DATA</div>
                ${statsHtml}
            </div>
        `;
        i++;
    }

    // Only update inner HTML if it's initial load or we really need to, to avoid losing state
    if (isInitialLoad || container.innerHTML.includes('LOADING')) {
        container.innerHTML = html;
    }
}

function updateStatus(isLive) {
    const badge = $("#status-box");
    const updateTime = $("#last-update");

    if (isLive) {
        badge.classList.add("live");
        badge.textContent = "SYSTEM_ONLINE";
    } else {
        badge.classList.remove("live");
        badge.textContent = "CONN_LOST";
    }

    updateTime.textContent = new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

// Main Update Loop

async function updateDashboard() {
    const [anomalies, metrics] = await Promise.all([
        fetchAnomalies(),
        fetchMetrics(),
    ]);

    if (anomalies && !anomalies.error) {
        renderMetricsSidebar(anomalies);
        renderPairsGrid(anomalies);
        updateStatus(true);
    } else {
        updateStatus(false);
    }

    if (metrics) {
        renderModelMetrics(metrics);
    }
    
    isInitialLoad = false;
}

// Initialization

document.addEventListener("DOMContentLoaded", () => {
    updateDashboard();
    setInterval(updateDashboard, REFRESH_INTERVAL_MS);
    
    // Initialize new features
    initCLI();
    initModal();
    initMouseTracking();
});

// Feature Implementations

function initCLI() {
    const cliInput = $("#cli-input");
    const cliOutput = $("#cli-output");
    if (!cliInput) return;
    
    cliInput.addEventListener("keydown", (e) => {
        if (e.key === "Enter") {
            const val = cliInput.value.trim();
            if (!val) return;
            
            // Add user command
            const line = document.createElement("div");
            line.className = "cli-line";
            line.textContent = `> ${val}`;
            cliOutput.appendChild(line);
            
            // Process command
            const response = document.createElement("div");
            response.className = "cli-line";
            
            const cmd = val.toLowerCase();
            if (cmd === "help") {
                response.textContent = "COMMANDS: help, clear, scan [pair], reboot";
            } else if (cmd === "clear") {
                cliOutput.innerHTML = "";
                cliInput.value = "";
                return;
            } else if (cmd === "reboot") {
                response.textContent = "REBOOTING SYSTEM...";
                setTimeout(() => location.reload(), 1000);
            } else if (cmd.startsWith("scan ")) {
                const target = val.split(" ")[1].toUpperCase();
                response.textContent = `SCANNING ${target}: Running diagnostics... No active alerts detected.`;
            } else {
                response.textContent = `ERR: Unknown command '${val}'`;
                response.style.color = "var(--accent-warn)";
            }
            
            cliOutput.appendChild(response);
            cliOutput.scrollTop = cliOutput.scrollHeight;
            cliInput.value = "";
        }
    });
}

function initModal() {
    const modal = $("#anomaly-modal");
    const closeBtn = $("#modal-close");
    const grid = $("#pairs-grid");
    if (!modal) return;
    
    grid.addEventListener("click", (e) => {
        const card = e.target.closest(".pair-card");
        if (!card) return;
        
        const pairName = card.querySelector(".pair-name").textContent;
        openModal(pairName, card);
    });
    
    closeBtn.addEventListener("click", () => {
        // Anime.js close animation
        if (typeof anime !== 'undefined') {
            anime({
                targets: '.modal-content',
                scale: [1, 0.95],
                opacity: [1, 0],
                duration: 200,
                easing: 'easeInQuad',
                complete: () => modal.classList.add("hidden")
            });
        } else {
            modal.classList.add("hidden");
        }
    });
}

function openModal(pairName, cardEl) {
    const modal = $("#anomaly-modal");
    const title = $("#modal-title");
    const details = $("#modal-details");
    const svg = $(".chart-svg");
    const crosshair = $(".anomaly-crosshair");
    
    title.textContent = `ANALYSIS // ${pairName}`;
    title.dataset.text = `ANALYSIS // ${pairName}`;
    
    // Copy details from card to modal
    const cardDetails = cardEl.querySelector(".pair-details").innerHTML;
    details.innerHTML = `
        <div style="margin-bottom: 20px;">
            <h3 style="color: var(--accent-safe); margin-bottom: 10px;">[LIVE_DATA]</h3>
            ${cardDetails}
        </div>
        <div style="border-top: 1px dotted var(--border); padding-top: 20px; color: var(--fg-muted); font-size: 11px;">
            <p>> PATTERN_SCANNER:<br>Looks for unusual price movements over time.</p>
            <br>
            <p>> VOLUME_SCANNER:<br>Detects sudden spikes or drops in volume.</p>
            <br>
            <p style="color: var(--accent-warn);">> STATUS: Review recommended.</p>
        </div>
    `;
    
    modal.classList.remove("hidden");
    crosshair.classList.add("hidden");
    if (svg) svg.innerHTML = "";
    
    // Anime.js open animation
    if (typeof anime !== 'undefined') {
        anime({
            targets: '.modal-content',
            scale: [0.95, 1],
            opacity: [0, 1],
            duration: 400,
            easing: 'easeOutExpo'
        });
        
        if (svg) drawFakeChart(svg, crosshair);
    }
}

function drawFakeChart(svg, crosshair) {
    const points = [];
    const numPoints = 50;
    // We must wait a tick for the modal to be visible to get clientWidth
    setTimeout(() => {
        const width = svg.clientWidth || 600;
        const height = svg.clientHeight || 400;
        
        let y = height / 2;
        for(let i=0; i<numPoints; i++) {
            const x = (i / (numPoints - 1)) * width;
            y += (Math.random() - 0.5) * 40; // Random walk
            y = Math.max(40, Math.min(height - 40, y));
            
            // Spike anomaly at ~80%
            if (i === Math.floor(numPoints * 0.8)) {
                y = 20; // massive spike up
            }
            points.push({x, y});
        }
        
        const pathStr = `M ${points.map(p => `${p.x},${p.y}`).join(" L ")}`;
        
        const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
        path.setAttribute("d", pathStr);
        path.setAttribute("class", "chart-line-path");
        
        // Anomaly circle
        const anomalyPoint = points[Math.floor(numPoints * 0.8)];
        const circle = document.createElementNS("http://www.w3.org/2000/svg", "circle");
        circle.setAttribute("cx", anomalyPoint.x);
        circle.setAttribute("cy", anomalyPoint.y);
        circle.setAttribute("r", "0");
        circle.setAttribute("class", "chart-anomaly-point");
        
        svg.appendChild(path);
        svg.appendChild(circle);
        
        const length = path.getTotalLength();
        path.setAttribute("stroke-dasharray", length);
        path.setAttribute("stroke-dashoffset", length);
        
        anime.timeline({ easing: 'easeInOutSine' })
        .add({
            targets: path,
            strokeDashoffset: [length, 0],
            duration: 1000
        })
        .add({
            targets: circle,
            r: [0, 8],
            duration: 400,
            easing: 'easeOutElastic(1, .8)',
            complete: () => {
                crosshair.style.left = `${anomalyPoint.x}px`;
                crosshair.classList.remove("hidden");
            }
        });
    }, 50);
}

function initMouseTracking() {
    const scanlines = $(".scanlines");
    if (!scanlines) return;
    document.addEventListener("mousemove", (e) => {
        const x = (e.clientX / window.innerWidth - 0.5) * 15;
        const y = (e.clientY / window.innerHeight - 0.5) * 15;
        scanlines.style.transform = `translate(${x}px, ${y}px)`;
    });
}
