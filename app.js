// ============================================================
// SMARTCOAL GOVERNANCE & INTELLIGENCE PLATFORM
// Frontend Controller
// ============================================================

// ============================================================
// GLOBAL HELPERS
// ============================================================

function escapeHTML(value) {
    if (value === null || value === undefined) {
        return "";
    }

    return String(value)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}


function riskInfo(score) {

    score = Number(score || 0);

    if (score >= 75) {
        return {
            label: "HIGH",
            icon: "🔴",
            className: "high",
            color: "#b44b43"
        };
    }

    if (score >= 50) {
        return {
            label: "MEDIUM",
            icon: "🟡",
            className: "medium",
            color: "#b27a1b"
        };
    }

    return {
        label: "LOW",
        icon: "🟢",
        className: "low",
        color: "#2f7d52"
    };
}


function formatNumber(value, decimals = 1) {

    if (
        value === null ||
        value === undefined ||
        value === "" ||
        Number.isNaN(Number(value))
    ) {
        return "N/A";
    }

    return Number(value).toFixed(decimals);
}


function formatDate(value) {

    if (!value) {
        return "N/A";
    }

    try {

        const d = new Date(value);

        if (Number.isNaN(d.getTime())) {
            return value;
        }

        return d.toLocaleString();

    } catch (error) {

        return value;
    }
}


// ============================================================
// API HELPER
// ============================================================

async function apiGet(url) {

    const response = await fetch(url, {
        cache: "no-store"
    });

    if (!response.ok) {
        throw new Error(
            `Request failed: ${response.status}`
        );
    }

    return await response.json();
}


// ============================================================
// GIS MAP
// ============================================================

async function loadMap() {

    const el = document.getElementById("map");

    if (!el || typeof L === "undefined") {
        return;
    }


    if (window.smartCoalMap) {
    window.smartCoalMap.remove();
    window.smartCoalMap = null;
}

const map = L.map("map", {
    zoomControl: true,
    scrollWheelZoom: true
}).setView([22.8, 80.5], 5);

window.smartCoalMap = map;


    // ========================================================
    // MAP TILES
    // ========================================================

    L.tileLayer(
    "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
        {
            maxZoom: 19,
            attribution:
                "© OpenStreetMap contributors"
        }
    ).addTo(map);


    try {

        // ====================================================
        // LOAD MINE DATA
        // ====================================================

        const mines =
            await apiGet("/api/mines");


        const markers = [];


        // ====================================================
        // CREATE MINE MARKERS
        // ====================================================

        mines.forEach(m => {

            if (
                m.lat === null ||
                m.lon === null ||
                m.lat === undefined ||
                m.lon === undefined
            ) {
                return;
            }


            const risk =
                riskInfo(m.risk_score);


            // =================================================
            // ML ENVIRONMENTAL ANOMALY
            // =================================================

            let mlStatus =
                "BASELINE";

            let mlScore =
                "N/A";

            let mlExplanation =
                "More historical environmental observations are required for anomaly detection.";


            if (m.anomaly) {

                mlScore =
                    formatNumber(
                        m.anomaly.anomaly_score,
                        2
                    );

                mlStatus =
                    m.anomaly.anomaly_level ||
                    "NORMAL";

                mlExplanation =
                    m.anomaly.explanation ||
                    "Environmental pattern analyzed by the ML anomaly detector.";
            }


            let mlIcon =
                "🧠";


            if (mlStatus === "HIGH") {

                mlIcon =
                    "🔴";

            } else if (mlStatus === "MEDIUM") {

                mlIcon =
                    "🟡";

            } else if (mlStatus === "NORMAL") {

                mlIcon =
                    "🟢";
            }


            // =================================================
            // ML RISK PREDICTION
            // =================================================

            let mlPredictionHTML = `
                <div style="
                    margin-top:8px;
                    color:#687680;
                ">
                    ML risk prediction is being established.
                </div>
            `;


            if (m.ml_prediction) {

                const prediction =
                    riskInfo(
                        m.ml_prediction.predicted_score ||
                        m.risk_score
                    );


                mlPredictionHTML = `

                    <div style="
                        margin-top:8px;
                        padding:8px;
                        background:#ffffff;
                        border-radius:6px;
                        border:1px solid #e1e6e9;
                    ">

                        <strong>
                            🤖 ML Risk Prediction
                        </strong>

                        <br>

                        Predicted Level:
                        <strong>
                            ${escapeHTML(
                                m.ml_prediction.predicted_level ||
                                prediction.label
                            )}
                        </strong>

                        <br>

                        Confidence:
                        <strong>
                            ${formatNumber(
                                (
                                    Number(
                                        m.ml_prediction.confidence || 0
                                    ) * 100
                                ),
                                1
                            )}%
                        </strong>

                    </div>

                `;
            }


            // =================================================
            // ENVIRONMENT
            // =================================================

            let environmentHTML = `

                <div style="
                    font-size:12px;
                    color:#666;
                    margin-top:8px;
                ">

                    No environmental reading available.

                </div>

            `;


            if (m.environment) {

                const e =
                    m.environment;


                environmentHTML = `

                    <div style="
                        margin-top:10px;
                        padding:9px;
                        background:#f5f7f8;
                        border-radius:6px;
                        font-size:12px;
                    ">

                        <strong>
                            🌱 Environmental Monitoring
                        </strong>

                        <div style="
                            margin-top:6px;
                            line-height:20px;
                        ">

                            PM2.5:
                            <strong>
                                ${formatNumber(e.pm25)}
                            </strong>
                            µg/m³

                            <br>

                            PM10:
                            <strong>
                                ${formatNumber(e.pm10)}
                            </strong>
                            µg/m³

                            <br>

                            SO₂:
                            <strong>
                                ${formatNumber(e.so2)}
                            </strong>
                            µg/m³

                            <br>

                            NO₂:
                            <strong>
                                ${formatNumber(e.no2)}
                            </strong>
                            µg/m³

                            <br>

                            CO:
                            <strong>
                                ${formatNumber(e.co)}
                            </strong>
                            mg/m³

                        </div>

                        <div style="
                            margin-top:6px;
                            color:#687680;
                            font-size:10px;
                        ">

                            Source:
                            ${escapeHTML(
                                e.source ||
                                "CAAQMS / cached platform data"
                            )}

                        </div>

                    </div>

                `;
            }


            // =================================================
// MARKER
// =================================================

// Accept both coordinate naming formats
const latitude = Number(
    m.lat ?? m.latitude
);

const longitude = Number(
    m.lon ?? m.longitude
);

// Ignore only genuinely invalid coordinates
if (
    !Number.isFinite(latitude) ||
    !Number.isFinite(longitude) ||
    latitude < -90 ||
    latitude > 90 ||
    longitude < -180 ||
    longitude > 180
) {
    console.warn(
        "Skipping mine with invalid coordinates:",
        m.name,
        m.lat,
        m.lon
    );

    return;
}


// Always provide a visible risk colour
const markerColor =
    risk && risk.color
        ? risk.color
        : "#2f7d52";


const marker =
    L.circleMarker(
        [latitude, longitude],
        {
            radius: 10,
            fillColor: markerColor,
            color: "#ffffff",
            weight: 2,
            opacity: 1,
            fillOpacity: 0.95
        }
    ).addTo(map);


// Keep marker for map fitting
markers.push(marker);

            // =================================================
            // POPUP
            // =================================================

            const mineUrl = `/mine/${m.id}`;

const riskScore = Number(m.risk_score || 0);

const riskStatus =
    String(m.status || "DATA PENDING").toUpperCase();

const environment =
    m.environment || {};

const components =
    m.risk_components || {};

const anomaly =
    m.anomaly || {};

const recommendations =
    m.recommendations || [];

const environmentSource =
    environment.source ||
    "No environmental data";

const pm25 =
    environment.pm25 ?? "—";

const pm10 =
    environment.pm10 ?? "—";

const so2 =
    environment.so2 ?? "—";

const no2 =
    environment.no2 ?? "—";

const co =
    environment.co ?? "—";

let riskClass = "pending";

if (riskStatus === "HIGH") {
    riskClass = "high";
}
else if (riskStatus === "MEDIUM") {
    riskClass = "medium";
}
else if (riskStatus === "LOW") {
    riskClass = "low";
}


let anomalyHtml = `
    <div class="map-ai-row">
        <span>Environmental anomaly</span>
        <strong>Not enough data</strong>
    </div>
`;

if (anomaly && anomaly.available) {

    anomalyHtml = `
        <div class="map-ai-row">
            <span>Environmental anomaly</span>
            <strong>
                ${anomaly.is_anomaly ? "ANOMALY" : "NORMAL"}
            </strong>
        </div>

        <div class="map-ai-explanation">
            ${anomaly.explanation || ""}
        </div>
    `;
}


let recommendationHtml =
    "Continue routine monitoring.";

if (
    Array.isArray(recommendations) &&
    recommendations.length
) {

    recommendationHtml =
        recommendations[0];
}


const popupHtml = `

    <div class="mine-popup">

        <div class="mine-popup-header">

            <div>

                <div class="mine-popup-kicker">
                    SMARTCOAL GOVERNANCE
                </div>

                <h3>
                    ${m.name}
                </h3>

            </div>

            <span class="
                mine-risk-badge
                ${riskClass}
            ">
                ${riskStatus}
            </span>

        </div>


        <div class="mine-popup-location">

            ${m.subsidiary || "—"}
            ·
            ${m.state || "—"}

        </div>


        <div class="mine-popup-score">

            <div>

                <span>
                    Governance Risk
                </span>

                <strong>
                    ${riskScore}/100
                </strong>

            </div>

        </div>


        <div class="mine-popup-section">

            <div class="mine-popup-title">
                Risk Components
            </div>

            <div class="mine-popup-grid">

                <div>
                    <span>Compliance</span>
                    <strong>
                        ${components.compliance ?? "—"}
                    </strong>
                </div>

                <div>
                    <span>Inspections</span>
                    <strong>
                        ${components.inspections ?? "—"}
                    </strong>
                </div>

                <div>
                    <span>Contractors</span>
                    <strong>
                        ${components.contractors ?? "—"}
                    </strong>
                </div>

                <div>
                    <span>Environment</span>
                    <strong>
                        ${components.environment ?? "—"}
                    </strong>
                </div>

            </div>

        </div>


        <div class="mine-popup-section">

            <div class="mine-popup-title">
                Environmental Monitoring
            </div>

            <div class="mine-popup-grid">

                <div>
                    <span>PM2.5</span>
                    <strong>${pm25}</strong>
                </div>

                <div>
                    <span>PM10</span>
                    <strong>${pm10}</strong>
                </div>

                <div>
                    <span>SO₂</span>
                    <strong>${so2}</strong>
                </div>

                <div>
                    <span>NO₂</span>
                    <strong>${no2}</strong>
                </div>

                <div>
                    <span>CO</span>
                    <strong>${co}</strong>
                </div>

            </div>

            <small>
                Source:
                ${environmentSource}
            </small>

        </div>


        <div class="mine-popup-section">

            <div class="mine-popup-title">
                AI / ML Analysis
            </div>

            ${anomalyHtml}

        </div>


        <div class="mine-popup-section">

            <div class="mine-popup-title">
                Recommended Action
            </div>

            <div class="mine-popup-recommendation">

                ${recommendationHtml}

            </div>

        </div>


        <a
            href="${mineUrl}"
            class="mine-popup-button"
        >
            Open Mine Governance Profile →
        </a>

    </div>
`;


marker.bindPopup(
    popupHtml,
    {
        maxWidth: 390,
        minWidth: 320,
        className: "smartcoal-mine-popup"
    }
);
                    
                   
                    

        });


        // ====================================================
        // FIT MAP
        // ====================================================

        if (markers.length > 0) {

            const group =
                L.featureGroup(markers);


            map.fitBounds(
                group
                    .getBounds()
                    .pad(0.25)
            );
        }


        // ====================================================
        // LEGEND
        // ====================================================

        const legend =
            L.control({
                position: "bottomright"
            });


        legend.onAdd =
            function () {

                const div =
                    L.DomUtil.create(
                        "div",
                        "gis-legend"
                    );


                div.innerHTML = `

                    <div style="
                        background:white;
                        padding:12px 14px;
                        border-radius:8px;
                        box-shadow:0 2px 10px rgba(0,0,0,.18);
                        font-family:Arial,sans-serif;
                        font-size:12px;
                        line-height:22px;
                    ">

                        <strong style="
                            font-size:13px;
                        ">

                            GOVERNANCE RISK

                        </strong>


                        <div>

                            <span style="
                                color:#b44b43;
                                font-size:16px;
                            ">
                                ●
                            </span>

                            High Risk

                        </div>


                        <div>

                            <span style="
                                color:#b27a1b;
                                font-size:16px;
                            ">
                                ●
                            </span>

                            Medium Risk

                        </div>


                        <div>

                            <span style="
                                color:#2f7d52;
                                font-size:16px;
                            ">
                                ●
                            </span>

                            Low Risk

                        </div>


                        <hr style="
                            border:0;
                            border-top:1px solid #eee;
                            margin:7px 0;
                        ">


                        <div>
                            🧠 AI / ML analysis
                        </div>


                        <div style="
                            margin-top:4px;
                            color:#687680;
                            font-size:10px;
                        ">

                            Risk markers update from
                            platform governance data.

                        </div>

                    </div>

                `;


                return div;
            };


        legend.addTo(map);


    } catch (error) {

        console.error(
            "GIS Error:",
            error
        );


        el.innerHTML = `

            <div style="
                padding:30px;
                text-align:center;
                color:#777;
                font-family:Arial,sans-serif;
            ">

                Unable to load GIS mine data.

                <br>

                <button
                    onclick="loadMap()"
                    style="
                        margin-top:12px;
                        padding:8px 14px;
                        border:0;
                        border-radius:5px;
                        background:#1f5f8b;
                        color:white;
                        cursor:pointer;
                    "
                >
                    Retry
                </button>

            </div>

        `;
    }
}


// ============================================================
// GPS LOCATION
// ============================================================

function captureLocation() {

    if (!navigator.geolocation) {

        alert(
            "Geolocation is not supported by this browser."
        );

        return;
    }


    navigator.geolocation.getCurrentPosition(

        position => {

            const latitude =
                document.getElementById(
                    "latitude"
                );


            const longitude =
                document.getElementById(
                    "longitude"
                );


            if (
                latitude &&
                longitude
            ) {

                latitude.value =
                    position.coords.latitude.toFixed(6);


                longitude.value =
                    position.coords.longitude.toFixed(6);


                alert(
                    "GPS location captured."
                );
            }

        },


        error => {

            console.warn(
                "GPS Error:",
                error
            );


            alert(
                "Could not capture location. " +
                "You can still submit the inspection."
            );

        },


        {
            enableHighAccuracy: true,
            timeout: 10000,
            maximumAge: 0
        }

    );
}


// ============================================================
// REFRESH PLATFORM DATA
// ============================================================

async function refreshPlatformData(
    showMessage = false
) {

    try {

        const response =
            await fetch(
                "/api/refresh-data",
                {
                    method: "POST",
                    cache: "no-store"
                }
            );


        if (!response.ok) {
            throw new Error(
                "Refresh request failed"
            );
        }


        const data =
            await response.json();


        console.log(
            "SmartCoal data refresh:",
            data
        );


        // -----------------------------------------------
        // Refresh the visible platform data
        // -----------------------------------------------

        await loadPlatformStatus();

        await loadAlerts();


        // Rebuild the GIS data using the refreshed
        // environmental/risk information.
        await loadMap();


        if (showMessage) {

            if (data.live_data) {

                alert(
                    "SmartCoal data refreshed successfully from the official CAAQMS source."
                );

            } else {

                alert(
                    "Official source was unavailable. SmartCoal is using the last successful cached data."
                );
            }
        }


        return data;


    } catch (error) {

        console.error(
            "Data refresh error:",
            error
        );


        if (showMessage) {

            alert(
                "Data refresh could not be completed. Existing cached data remains available."
            );
        }


        return null;
    }
}


// ============================================================
// PLATFORM STATUS
// ============================================================

async function loadPlatformStatus() {

    try {

        const status =
            await apiGet(
                "/api/status"
            );


        console.log(
            "SmartCoal Platform Status:",
            status
        );


        // -----------------------------------------------
        // Optional status elements
        // -----------------------------------------------

        const statusElement =
            document.getElementById(
                "data-status"
            );


        if (statusElement) {

            const live =
                status.caaqms_live === true;


            statusElement.textContent =
                live
                    ? "CAAQMS Live"
                    : "CAAQMS Cached";


            statusElement.style.color =
                live
                    ? "#2f7d52"
                    : "#b27a1b";
        }


        const syncElement =
            document.getElementById(
                "last-sync"
            );


        if (
            syncElement &&
            status.last_successful_sync
        ) {

            syncElement.textContent =
                "Last sync: " +
                formatDate(
                    status.last_successful_sync
                );
        }


        return status;


    } catch (error) {

        console.warn(
            "Could not load platform status:",
            error
        );


        return null;
    }
}


// ============================================================
// AI ANALYSIS PANEL
// ============================================================

async function loadAIAnalysis(mineId) {

    if (!mineId) {
        return null;
    }


    try {

        const analysis =
            await apiGet(
                `/api/ai-analysis/${mineId}`
            );


        console.log(
            "AI Analysis:",
            analysis
        );


        const container =
            document.getElementById(
                "ai-analysis"
            );


        if (!container) {
            return analysis;
        }


        const predicted =
            analysis.ml_prediction;


        const risk =
            riskInfo(
                analysis.risk_score
            );


        let factorsHTML =
            "";


        if (
            analysis.factors &&
            Array.isArray(
                analysis.factors
            )
        ) {

            factorsHTML =
                analysis.factors
                    .map(
                        factor => `
                            <div style="
                                padding:5px 0;
                                border-bottom:1px solid #eee;
                            ">
                                ${escapeHTML(factor)}
                            </div>
                        `
                    )
                    .join("");
        }


        container.innerHTML = `

            <div style="
                padding:14px;
                border-radius:8px;
                background:#f6f8fa;
                border:1px solid #e1e6e9;
            ">

                <div style="
                    font-size:16px;
                    font-weight:700;
                    margin-bottom:8px;
                ">

                    🤖 AI Governance Risk Analysis

                </div>


                <div style="
                    margin-bottom:10px;
                ">

                    Current risk:

                    <strong>
                        ${risk.icon}
                        ${risk.label}
                        (${formatNumber(
                            analysis.risk_score,
                            0
                        )}/100)
                    </strong>

                </div>


                ${
                    predicted
                        ? `
                            <div style="
                                margin-bottom:10px;
                            ">

                                ML prediction:

                                <strong>
                                    ${escapeHTML(
                                        predicted.predicted_level ||
                                        "N/A"
                                    )}
                                </strong>

                                ·

                                ${formatNumber(
                                    Number(
                                        predicted.confidence || 0
                                    ) * 100,
                                    1
                                )}% confidence

                            </div>
                        `
                        : ""
                }


                <div style="
                    font-size:12px;
                    margin-top:8px;
                ">

                    <strong>
                        Key risk factors
                    </strong>

                    <div style="
                        margin-top:5px;
                    ">

                        ${factorsHTML ||
                        "No major risk factors identified."}

                    </div>

                </div>


                ${
                    analysis.recommendation
                        ? `
                            <div style="
                                margin-top:12px;
                                padding:10px;
                                background:white;
                                border-radius:6px;
                            ">

                                <strong>
                                    Recommended action
                                </strong>

                                <br>

                                <span style="
                                    font-size:12px;
                                    color:#58656d;
                                ">

                                    ${escapeHTML(
                                        analysis.recommendation
                                    )}

                                </span>

                            </div>
                        `
                        : ""
                }

            </div>

        `;


        return analysis;


    } catch (error) {

        console.warn(
            "AI analysis unavailable:",
            error
        );


        return null;
    }
}


// ============================================================
// ALERTS
// ============================================================

async function loadAlerts() {

    try {

        const alerts =
            await apiGet(
                "/api/alerts"
            );


        console.log(
            "SmartCoal alerts:",
            alerts
        );


        const container =
            document.getElementById(
                "alerts-container"
            );


        if (!container) {
            return alerts;
        }


        if (
            !Array.isArray(alerts) ||
            alerts.length === 0
        ) {

            container.innerHTML = `

                <div style="
                    padding:12px;
                    color:#687680;
                ">

                    No active governance alerts.

                </div>

            `;


            return alerts;
        }


        container.innerHTML =
            alerts
                .slice(0, 10)
                .map(alert => {

                    let icon =
                        "⚠️";


                    if (
                        alert.severity ===
                        "CRITICAL"
                    ) {

                        icon =
                            "🔴";

                    } else if (
                        alert.severity ===
                        "HIGH"
                    ) {

                        icon =
                            "🟠";
                    }


                    return `

                        <div style="
                            padding:10px;
                            margin-bottom:7px;
                            border-left:4px solid #b44b43;
                            background:#f8f9fa;
                            border-radius:5px;
                        ">

                            <strong>

                                ${icon}
                                ${escapeHTML(
                                    alert.title ||
                                    alert.alert_type ||
                                    "Governance Alert"
                                )}

                            </strong>

                            <div style="
                                margin-top:4px;
                                font-size:12px;
                                color:#687680;
                            ">

                                ${escapeHTML(
                                    alert.message ||
                                    ""
                                )}

                            </div>

                        </div>

                    `;

                })
                .join("");


        return alerts;


    } catch (error) {

        console.warn(
            "Could not load alerts:",
            error
        );


        return null;
    }
}


// ============================================================
// INCIDENT STATUS
// ============================================================

async function updateIncident(
    incidentId,
    data
) {

    if (!incidentId) {
        return null;
    }


    try {

        const response =
            await fetch(
                `/api/incidents/${incidentId}`,
                {
                    method: "POST",
                    headers: {
                        "Content-Type":
                            "application/json"
                    },
                    body:
                        JSON.stringify(data)
                }
            );


        if (!response.ok) {

            throw new Error(
                "Incident update failed"
            );
        }


        const result =
            await response.json();


        console.log(
            "Incident updated:",
            result
        );


        return result;


    } catch (error) {

        console.error(
            "Incident update error:",
            error
        );


        return null;
    }
}


// ============================================================
// INCIDENT RECOVERY HELPERS
// ============================================================

async function closeIncident(
    incidentId
) {

    const result =
        await updateIncident(
            incidentId,
            {
                closure_status:
                    "CLOSED",
                emergency_status:
                    "RESOLVED",
                evacuation_status:
                    "COMPLETED",
                rescue_status:
                    "COMPLETED",
                investigation_status:
                    "COMPLETED"
            }
        );


    if (result) {

        alert(
            "Incident marked as recovered and closed."
        );


        window.location.reload();
    }
}


// ============================================================
// REFRESH BUTTON
// ============================================================

function setupRefreshButton() {

    const button =
        document.getElementById(
            "refresh-data"
        );


    if (!button) {
        return;
    }


    button.addEventListener(
        "click",
        async () => {

            button.disabled =
                true;


            const oldText =
                button.textContent;


            button.textContent =
                "Refreshing...";


            await refreshPlatformData(
                true
            );


            button.textContent =
                oldText;


            button.disabled =
                false;


            window.location.reload();

        }
    );
}


// ============================================================
// AUTOMATIC DATA REFRESH
// ============================================================

function startAutomaticRefresh() {

    // Refresh every 5 minutes.
    // The backend uses cached data if the official
    // source cannot be reached.

    setInterval(
        async () => {

            console.log(
                "Automatic SmartCoal refresh..."
            );


            await refreshPlatformData(
                false
            );


            await loadPlatformStatus();

        },
        5 * 60 * 1000
    );
}


// ============================================================
// PAGE INITIALIZATION
// ============================================================

document.addEventListener(
    "DOMContentLoaded",
    async function () {

        // GIS
        await loadMap();


        // Platform status
        await loadPlatformStatus();


        // Alerts
        await loadAlerts();


        // Refresh button
        setupRefreshButton();


        // Automatic refresh
        startAutomaticRefresh();


        // Optional AI panel.
        //
        // If a page contains:
        // <div id="ai-analysis" data-mine-id="1"></div>
        //
        // the AI analysis will load automatically.

        const aiContainer =
            document.getElementById(
                "ai-analysis"
            );


        if (aiContainer) {

            const mineId =
                aiContainer.dataset.mineId;


            if (mineId) {

                await loadAIAnalysis(
                    mineId
                );
            }
        }

    }
);