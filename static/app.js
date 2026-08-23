async function loadMap() {
    const el = document.getElementById("map");
    if (!el || typeof L === "undefined") return;

    // Create India-centered map
    const map = L.map("map", {
        zoomControl: true,
        scrollWheelZoom: true
    }).setView([22.8, 80.5], 5);

    // OpenStreetMap base layer
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        maxZoom: 19,
        attribution: "© OpenStreetMap contributors"
    }).addTo(map);

    // Fetch mine data from Flask API
    try {
        const res = await fetch("/api/mines");

        if (!res.ok) {
            throw new Error("Could not load mine data");
        }

        const mines = await res.json();
        const markers = [];

        mines.forEach(m => {

            // Determine risk level
            let color;
            let riskLabel;
            let riskIcon;

            if (m.risk_score >= 80) {
                color = "#b44b43";
                riskLabel = "HIGH";
                riskIcon = "🔴";
            } else if (m.risk_score >= 50) {
                color = "#b27a1b";
                riskLabel = "MEDIUM";
                riskIcon = "🟡";
            } else {
                color = "#2f7d52";
                riskLabel = "LOW";
                riskIcon = "🟢";
            }

            // Create mine marker
            const marker = L.circleMarker(
                [m.lat, m.lon],
                {
                    radius: 10,
                    fillColor: color,
                    color: "#ffffff",
                    weight: 2,
                    fillOpacity: 0.9
                }
            ).addTo(map);

            markers.push(marker);

            // Governance popup
            marker.bindPopup(`
                <div style="min-width:220px; font-family:Arial,sans-serif;">

                    <div style="
                        font-size:16px;
                        font-weight:700;
                        margin-bottom:5px;
                    ">
                        ${m.name}
                    </div>

                    <div style="
                        font-size:12px;
                        color:#666;
                        margin-bottom:10px;
                    ">
                        ${m.subsidiary} · ${m.state}
                    </div>

                    <div style="
                        padding:8px;
                        border-radius:6px;
                        background:${color}18;
                        border-left:4px solid ${color};
                        margin-bottom:10px;
                    ">
                        <strong>${riskIcon} ${riskLabel} RISK</strong>
                        <br>
                        Risk Score:
                        <strong>${m.risk_score}/100</strong>
                    </div>

                    <div style="font-size:13px; margin-bottom:5px;">
                        <strong>Compliance:</strong> ${m.compliance}%
                    </div>

                    <div style="font-size:13px; margin-bottom:10px;">
                        <strong>Status:</strong> ${m.status}
                    </div>

                    <a
                        href="/mine/${m.id}"
                        style="
                            display:block;
                            text-align:center;
                            padding:8px;
                            background:#1f2937;
                            color:white;
                            text-decoration:none;
                            border-radius:5px;
                            font-size:12px;
                            font-weight:600;
                        "
                    >
                        Open Mine Profile →
                    </a>

                </div>
            `);
        });

        // Automatically fit map around all monitored mines
        if (markers.length > 0) {
            const group = L.featureGroup(markers);
            map.fitBounds(group.getBounds().pad(0.25));
        }

        // Add risk legend
        const legend = L.control({ position: "bottomright" });

        legend.onAdd = function () {
            const div = L.DomUtil.create("div", "gis-legend");

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
                    <strong style="font-size:13px;">
                        RISK LEVEL
                    </strong>

                    <div>
                        <span style="color:#b44b43;font-size:16px;">●</span>
                        High Risk
                    </div>

                    <div>
                        <span style="color:#b27a1b;font-size:16px;">●</span>
                        Medium Risk
                    </div>

                    <div>
                        <span style="color:#2f7d52;font-size:16px;">●</span>
                        Low Risk
                    </div>
                </div>
            `;

            return div;
        };

        legend.addTo(map);

    } catch (error) {
        console.error("GIS Error:", error);

        document.getElementById("map").innerHTML = `
            <div style="
                padding:30px;
                text-align:center;
                color:#777;
                font-family:Arial,sans-serif;
            ">
                Unable to load GIS mine data.
            </div>
        `;
    }
}


// Capture GPS location for field inspection
function captureLocation() {

    if (!navigator.geolocation) {
        alert("Geolocation is not supported by this browser.");
        return;
    }

    navigator.geolocation.getCurrentPosition(
        p => {

            const latitude =
                document.getElementById("latitude");

            const longitude =
                document.getElementById("longitude");

            if (latitude && longitude) {

                latitude.value =
                    p.coords.latitude.toFixed(6);

                longitude.value =
                    p.coords.longitude.toFixed(6);

                alert("GPS location captured.");
            }
        },

        () => {
            alert(
                "Could not capture location. " +
                "For the prototype, you can still submit the inspection."
            );
        }
    );
}


// Start GIS when page loads
document.addEventListener(
    "DOMContentLoaded",
    loadMap
);