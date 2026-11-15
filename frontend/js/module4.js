        // ======================== MODULE 4 RENDERER ========================
        function renderModule4() {
            const emptyEl = document.getElementById('m4-empty');
            const contentEl = document.getElementById('m4-content');
            if (!APP_STATE || !APP_STATE.has_data) {
                emptyEl.style.display = 'block';
                contentEl.style.display = 'none';
                return;
            }
            emptyEl.style.display = 'none';
            contentEl.style.display = 'block';

            const m4 = APP_STATE.m4_data;
            const k = m4.dashboard_kpis;

            document.getElementById('m4-kpi-cards').innerHTML = `
                <div class="kpi-box">
                    <div class="k-title">1. KPIs Toàn Hệ Thống<\/div>
                    <div class="k-val">${k.cleaned_trajectories.toLocaleString()} điểm<\/div>
                    <div class="k-sub">${k.dynamic_zones_count} Khu vực động &bull; ${k.dynamic_timeframes_count} Khung giờ động<\/div>
                <\/div>
                <div class="kpi-box teal">
                    <div class="k-title">2. Forecast Accuracy<\/div>
                    <div class="k-val">${k.forecast_accuracy_pct}%<\/div>
                    <div class="k-sub">Tốt nhất: <strong>${k.best_forecast_model}<\/strong> (RMSE=${k.best_forecast_rmse})<\/div>
                <\/div>
                <div class="kpi-box amber">
                    <div class="k-title">3. Peak Periods (Giờ Cao Điểm)<\/div>
                    <div class="k-val">${k.peak_period_label}<\/div>
                    <div class="k-sub">Mật độ đỉnh: <strong>${k.network_max_density_veh_km} xe/km<\/strong><\/div>
                <\/div>
                <div class="kpi-box red">
                    <div class="k-title">4. Congestion Level<\/div>
                    <div class="k-val">${k.dominant_congestion_level}<\/div>
                    <div class="k-sub">Vận tốc TB toàn mạng: <strong>${k.network_avg_speed_kmh} km/h<\/strong><\/div>
                <\/div>
                <div class="kpi-box purple">
                    <div class="k-title">5. Traffic Statistics<\/div>
                    <div class="k-val">${k.network_avg_flow_veh_h} xe/h<\/div>
                    <div class="k-sub">Mật độ TB toàn mạng: <strong>${k.network_avg_density_veh_km} xe/km<\/strong><\/div>
                <\/div>
            `;

            drawM4Heatmap('canvas-m4-heatmap', m4.heatmap_matrix);
            drawM4MultiLine('canvas-m4-trend', m4.time_labels, m4.zones_series, 'flow_series', 'Lưu lượng (xe/giờ)');
            drawM4MultiLine('canvas-m4-density', m4.time_labels, m4.zones_series, 'density_series', 'Mật độ (xe/km)');
            drawM4MultiLine('canvas-m4-speed', m4.time_labels, m4.zones_series, 'speed_series', 'Vận tốc (km/h)');
            drawM4Histogram('canvas-m4-dist', m4.speed_histogram);
            drawM4ForecastBars('canvas-m4-forecast', m4.forecast_overview);
        }

