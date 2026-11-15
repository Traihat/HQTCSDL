        // ======================== MODULE 2 RENDERER ========================
        function renderModule2() {
            const emptyEl = document.getElementById('m2-empty');
            const contentEl = document.getElementById('m2-content');
            if (!APP_STATE || !APP_STATE.has_data) {
                emptyEl.style.display = 'block';
                contentEl.style.display = 'none';
                return;
            }
            emptyEl.style.display = 'none';
            contentEl.style.display = 'block';

            const imp = APP_STATE.import_info;
            document.getElementById('m2-dataset-badge').textContent =
                `Nguồn dữ liệu: ${imp.file_name} (${formatFileSize(Number(imp.file_size_kb || 250))}) • Tự động chia ${APP_STATE.zones.length} Khu vực & ${APP_STATE.timeframes.length} Khung giờ`;

            const zWrap = document.getElementById('m2-zone-buttons');
            let zHtml = `<button class="pill-btn ${M2_SELECTED_ZONE === 'ALL' ? 'active' : ''}" onclick="selectM2Zone('ALL')"> Tất cả khu vực (${APP_STATE.zones.length})<\/button>`;
            APP_STATE.zones.forEach(z => {
                const active = String(M2_SELECTED_ZONE) === String(z.zone_id) ? 'active' : '';
                zHtml += `<button class="pill-btn ${active}" onclick="selectM2Zone('${z.zone_id}')"> ${z.zone_name} (${z.road_length_km} km)<\/button>`;
            });
            zWrap.innerHTML = zHtml;

            const tfWrap = document.getElementById('m2-tf-buttons');
            let tfHtml = `<button class="pill-btn tf-pill ${M2_SELECTED_TF === 'ALL' ? 'active' : ''}" onclick="selectM2Timeframe('ALL')"> Tất cả khung giờ (${APP_STATE.timeframes.length})<\/button>`;
            APP_STATE.timeframes.forEach(tf => {
                const active = String(M2_SELECTED_TF) === String(tf.timeframe_id) ? 'active' : '';
                tfHtml += `<button class="pill-btn tf-pill ${active}" onclick="selectM2Timeframe('${tf.timeframe_id}')"> ${tf.timeframe_label}<\/button>`;
            });
            tfWrap.innerHTML = tfHtml;

            const key = `${M2_SELECTED_ZONE}__${M2_SELECTED_TF}`;
            const sub = APP_STATE.m2_combinations[key] || APP_STATE.m2_combinations["ALL__ALL"];
            const k = sub.kpis;
            const pk = sub.peak_hour_detection;
            const hs = sub.hotspot_identification;

            document.getElementById('m2-kpi-cards').innerHTML = `
                <div class="kpi-box">
                    <div class="k-title">1. Vehicle Count (Tổng Xe)<\/div>
                    <div class="k-val">${k.total_vehicles.toLocaleString()} xe<\/div>
                    <div class="k-sub"> Ô tô: ${k.car_count.toLocaleString()} &bull;  Xe máy: ${k.motorbike_count.toLocaleString()} &bull;  Bus/Tải: ${k.bus_truck_count.toLocaleString()}<\/div>
                <\/div>
                <div class="kpi-box teal">
                    <div class="k-title">2. Average Speed (Vận Tốc TB)<\/div>
                    <div class="k-val">${k.avg_speed_kmh} km/h<\/div>
                    <div class="k-sub">Trạng thái: ${renderCongestionBadge(k.dominant_congestion)}<\/div>
                <\/div>
                <div class="kpi-box amber">
                    <div class="k-title">3. Traffic Density &amp; Flow<\/div>
                    <div class="k-val">${k.avg_density_veh_km} xe/km<\/div>
                    <div class="k-sub">Đỉnh: <strong>${k.max_density_veh_km}<\/strong> xe/km &bull; Lưu lượng: <strong>${k.avg_flow_veh_h}<\/strong> xe/h<\/div>
                <\/div>
                <div class="kpi-box red">
                    <div class="k-title">4. Peak-Hour Detection<\/div>
                    <div class="k-val">Lúc ${pk.window_time_label}<\/div>
                    <div class="k-sub">${pk.zone_name}: <strong>${pk.peak_density_veh_km} xe/km<\/strong> (${pk.peak_vehicles} xe)<\/div>
                <\/div>
                <div class="kpi-box purple">
                    <div class="k-title">5. Congestion Hotspot<\/div>
                    <div class="k-val">Score: ${hs.top_score}<\/div>
                    <div class="k-sub">${hs.top_location}<\/div>
                <\/div>
            `;

            const zRows = sub.zone_breakdown.map(r => `
                <tr>
                    <td><strong>${r.zone_name}<\/strong><\/td>
                    <td>${r.road_length_km} km<\/td>
                    <td><strong>${r.total_vehicles.toLocaleString()}<\/strong><\/td>
                    <td>${r.avg_speed_kmh} km/h<\/td>
                    <td><strong style="color:var(--blue-600);">${r.avg_density_veh_km}<\/strong> <span style="color:var(--slate-500);">(Max: ${r.max_density_veh_km})<\/span><\/td>
                    <td>${r.avg_flow_veh_h} xe/h<\/td>
                <\/tr>
            `).join('');
            document.getElementById('m2-zone-table').innerHTML = `<table class="clean-table">
                <thead><tr><th>Khu vực động<\/th><th>Chiều dài<\/th><th>Tổng xe<\/th><th>Vận tốc TB<\/th><th>Mật độ (xe/km)<\/th><th>Lưu lượng<\/th><\/tr><\/thead>
                <tbody>${zRows}<\/tbody>
            <\/table>`;

            const hsRows = hs.hotspots_list.map(r => `
                <tr>
                    <td><strong>${r.zone_name}<\/strong><\/td>
                    <td><span style="font-weight:700;color:var(--blue-700);">${r.window_time_label}<\/span><\/td>
                    <td>${r.hotspot_location}<\/td>
                    <td>${r.avg_speed_kmh} km/h<\/td>
                    <td><strong style="color:var(--red-600);">${r.hotspot_score}<\/strong><\/td>
                    <td>${renderCongestionBadge(r.congestion_level)}<\/td>
                <\/tr>
            `).join('');
            document.getElementById('m2-hotspot-table').innerHTML = `<table class="clean-table">
                <thead><tr><th>Khu vực<\/th><th>Mốc giờ<\/th><th>Tọa độ Điểm nóng<\/th><th>Vận tốc<\/th><th>Hotspot Score<\/th><th>Mức độ<\/th><\/tr><\/thead>
                <tbody>${hsRows}<\/tbody>
            <\/table>`;

            drawM2TimelineChart(sub.timeline_series);
            drawM2SpatialChart(sub.spatial_points);
        }

        function selectM2Zone(zid) { M2_SELECTED_ZONE = zid; renderModule2(); }
        function selectM2Timeframe(tfid) { M2_SELECTED_TF = tfid; renderModule2(); }

