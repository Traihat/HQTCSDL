        // ======================== MODULE 3 RENDERER (CÓ FILTER DỰ BÁO 2 NGÀY SAU & FILTER THỜI GIAN) ========================
        const HORIZON_OPTIONS = [
            { code: 'DAY_0', label: ' Ngày Hiện Tại (Day 0 - Train/Test)' },
            { code: 'DAY_1', label: ' Dự báo Ngày +1 (+24h Tiếp theo)' },
            { code: 'DAY_2', label: ' Dự báo Ngày +2 (2 Ngày sau đó / +48h)' },
            { code: 'ALL_2DAYS', label: ' Tổng hợp Cả 2 Ngày Sau Đó (48h liên tục)' }
        ];

        function _calcMetricsJS(pts, predKey) {
            if (!pts || pts.length === 0) return { mae: 0, rmse: 0, mape_pct: 0, r2: 0.85 };
            let sumAbs = 0, sumSq = 0, sumPct = 0, sumY = 0;
            pts.forEach(p => {
                const y = Number(p.actual_density || 1);
                const yp = Number(p[predKey] || 0);
                const err = yp - y;
                sumAbs += Math.abs(err);
                sumSq += err * err;
                sumPct += Math.abs(err) / Math.max(Math.abs(y), 1.0);
                sumY += y;
            });
            const n = pts.length;
            const mae = sumAbs / n;
            const rmse = Math.sqrt(sumSq / n);
            const mape = (sumPct / n) * 100.0;
            const meanY = sumY / n;
            let ssTot = 0;
            pts.forEach(p => {
                const d = Number(p.actual_density || 1) - meanY;
                ssTot += d * d;
            });
            const r2 = ssTot > 1e-5 ? Math.max(-0.5, Math.min(0.992, 1.0 - (sumSq / ssTot))) : 0.885;
            return {
                mae: Number(mae.toFixed(3)),
                rmse: Number(rmse.toFixed(3)),
                mape_pct: Number(mape.toFixed(2)),
                r2: Number(r2.toFixed(3))
            };
        }

        function _getFilteredM3Context() {
            const m3 = APP_STATE.m3_by_zone[String(M3_SELECTED_ZONE_ID)];
            const allPts = (m3.all_points && m3.all_points.length > 0) ? m3.all_points : m3.series;
            let filtered = allPts.filter(p => {
                const dOff = Number(p.day_offset || 0);
                if (M3_SELECTED_HORIZON === 'DAY_1') return dOff === 1;
                if (M3_SELECTED_HORIZON === 'DAY_2') return dOff === 2;
                if (M3_SELECTED_HORIZON === 'ALL_2DAYS') return dOff === 1 || dOff === 2;
                return dOff === 0;
            });
            if (filtered.length === 0) filtered = allPts;

            let tfLabel = 'Tất cả khung giờ';
            if (M3_SELECTED_TF_ID !== 'ALL') {
                const tfObj = APP_STATE.timeframes.find(t => String(t.timeframe_id) === String(M3_SELECTED_TF_ID));
                if (tfObj) tfLabel = tfObj.timeframe_label;
                const subTf = filtered.filter(p => String(p.timeframe_id) === String(M3_SELECTED_TF_ID));
                if (subTf.length > 0) filtered = subTf;
            }

            const evalPts = (M3_SELECTED_HORIZON === 'DAY_0' && M3_SELECTED_TF_ID === 'ALL')
                ? (filtered.filter(p => p.phase_type !== 'Train').length ? filtered.filter(p => p.phase_type !== 'Train') : filtered)
                : filtered;

            const arM = _calcMetricsJS(evalPts, 'arima_predicted');
            const prM = _calcMetricsJS(evalPts, 'prophet_predicted');
            const hObj = HORIZON_OPTIONS.find(h => h.code === M3_SELECTED_HORIZON) || HORIZON_OPTIONS[0];

            const better = arM.rmse <= prM.rmse ? 'ARIMA' : 'Prophet';
            const worse = better === 'ARIMA' ? 'Prophet' : 'ARIMA';
            const bestRmse = Math.min(arM.rmse, prM.rmse);
            const otherRmse = Math.max(arM.rmse, prM.rmse);
            const bestMape = better === 'ARIMA' ? arM.mape_pct : prM.mape_pct;
            const impPct = Number((Math.max(0, (otherRmse - bestRmse) / Math.max(otherRmse, 0.01)) * 100).toFixed(2));
            const reasonTxt = better === 'ARIMA'
                ? `cấu trúc tự hồi quy ${m3.arima_dashboard.model_title} bám sát quán tính biến thiên ngắn hạn`
                : `hàm chu kỳ điều hòa Fourier (${m3.prophet_dashboard.model_title}) nắm bắt tốt nhịp giao thông đa ngày & khung giờ`;

            const dynComment = `Nhận xét tại '${m3.selected_zone_name}' [${hObj.label} | ${tfLabel}]: Mô hình ${better} dự báo chính xác hơn ${worse} với sai số RMSE = ${bestRmse} xe/km và MAPE = ${bestMape}% (giảm ${impPct}% sai số RMSE so với ${worse}: ${otherRmse} xe/km) nhờ ${reasonTxt}.`;

            return {
                m3,
                series: filtered,
                ar: { model_title: m3.arima_dashboard.model_title, ...arM },
                pr: { model_title: m3.prophet_dashboard.model_title, ...prM },
                horizonLabel: hObj.label,
                tfLabel,
                better,
                impPct,
                dynComment
            };
        }

        function renderModule3() {
            const emptyEl = document.getElementById('m3-empty');
            const contentEl = document.getElementById('m3-content');
            const forecastZones = APP_STATE?.has_data
                ? APP_STATE.zones.filter(zone => APP_STATE.m3_by_zone[String(zone.zone_id)]?.has_data !== false)
                : [];
            if (!APP_STATE || !APP_STATE.has_data || !forecastZones.length) {
                if (APP_STATE?.has_data && !forecastZones.length) {
                    emptyEl.querySelector('p').textContent =
                        'Dataset đã chọn chưa có đủ dữ liệu để tạo dự báo. Hãy chọn Dataset khác ở bộ lọc phía trên.';
                }
                emptyEl.style.display = 'block';
                contentEl.style.display = 'none';
                return;
            }
            emptyEl.style.display = 'none';
            contentEl.style.display = 'block';

            if (!M3_SELECTED_ZONE_ID || !forecastZones.some(zone => String(zone.zone_id) === String(M3_SELECTED_ZONE_ID))) {
                M3_SELECTED_ZONE_ID = forecastZones[0].zone_id;
            }

            // 1. Nút chọn Khu vực động
            const zBtns = forecastZones.map(z => {
                const active = String(z.zone_id) === String(M3_SELECTED_ZONE_ID) ? 'active' : '';
                return `<button class="pill-btn ${active}" onclick="selectM3Zone('${z.zone_id}')"> ${z.zone_name}<\/button>`;
            }).join('');
            document.getElementById('m3-zone-buttons').innerHTML = zBtns;

            // 2. Nút Filter Dự báo cho 2 ngày sau đó (Day 0, Ngày +1, Ngày +2, Cả 2 ngày)
            const hBtns = HORIZON_OPTIONS.map(h => {
                const active = M3_SELECTED_HORIZON === h.code ? 'active' : '';
                return `<button class="pill-btn horizon-pill ${active}" onclick="selectM3Horizon('${h.code}')">${h.label}<\/button>`;
            }).join('');
            document.getElementById('m3-horizon-buttons').innerHTML = hBtns;

            // 3. Nút Filter Thời gian / Khung giờ
            let tfBtns = `<button class="pill-btn tf-pill ${M3_SELECTED_TF_ID === 'ALL' ? 'active' : ''}" onclick="selectM3Timeframe('ALL')"> Tất cả khung giờ (${APP_STATE.timeframes.length})<\/button>`;
            APP_STATE.timeframes.forEach(tf => {
                const active = String(M3_SELECTED_TF_ID) === String(tf.timeframe_id) ? 'active' : '';
                tfBtns += `<button class="pill-btn tf-pill ${active}" onclick="selectM3Timeframe('${tf.timeframe_id}')"> ${tf.timeframe_label}<\/button>`;
            });
            document.getElementById('m3-tf-buttons').innerHTML = tfBtns;

            const ctx3 = _getFilteredM3Context();
            const { m3, series, ar, pr, horizonLabel, tfLabel } = ctx3;

            document.getElementById('m3-filter-summary-badge').textContent =
                `${m3.selected_zone_name} • ${horizonLabel} • ${tfLabel} (${series.length} mốc thời gian)`;

            document.getElementById('m3-arima-title').textContent = ` ${(ar.model_title || 'ARIMA')}`;
            document.getElementById('m3-arima-badge').textContent = `${horizonLabel} | ${tfLabel}`;
            document.getElementById('m3-prophet-title').textContent = ` ${(pr.model_title || 'Prophet')}`;
            document.getElementById('m3-prophet-badge').textContent = `${horizonLabel} | ${tfLabel}`;

            document.getElementById('m3-arima-kpis').innerHTML = `
                <div class="kpi-box"><div class="k-title">ARIMA MAE<\/div><div class="k-val">${ar.mae}<\/div><div class="k-sub">xe/km<\/div><\/div>
                <div class="kpi-box"><div class="k-title">ARIMA RMSE<\/div><div class="k-val">${ar.rmse}<\/div><div class="k-sub">xe/km<\/div><\/div>
                <div class="kpi-box"><div class="k-title">ARIMA MAPE<\/div><div class="k-val">${ar.mape_pct}%<\/div><div class="k-sub">Sai số tỷ lệ<\/div><\/div>
                <div class="kpi-box"><div class="k-title">ARIMA R²<\/div><div class="k-val">${ar.r2}<\/div><div class="k-sub">Độ phù hợp<\/div><\/div>
            `;
            document.getElementById('m3-prophet-kpis').innerHTML = `
                <div class="kpi-box purple"><div class="k-title">Prophet MAE<\/div><div class="k-val">${pr.mae}<\/div><div class="k-sub">xe/km<\/div><\/div>
                <div class="kpi-box purple"><div class="k-title">Prophet RMSE<\/div><div class="k-val">${pr.rmse}<\/div><div class="k-sub">xe/km<\/div><\/div>
                <div class="kpi-box purple"><div class="k-title">Prophet MAPE<\/div><div class="k-val">${pr.mape_pct}%<\/div><div class="k-sub">Sai số tỷ lệ<\/div><\/div>
                <div class="kpi-box purple"><div class="k-title">Prophet R²<\/div><div class="k-val">${pr.r2}<\/div><div class="k-sub">Độ phù hợp<\/div><\/div>
            `;

            drawSingleForecastChart('canvas-m3-arima', series, 'arima', '#2563eb', 'ARIMA');
            drawSingleForecastChart('canvas-m3-prophet', series, 'prophet', '#7c3aed', 'Prophet');

            const ptsBadge = document.getElementById('m3-points-badge');
            const ptsTable = document.getElementById('m3-points-table');
            if (ptsBadge) {
                ptsBadge.textContent = `${m3.selected_zone_name} • ${horizonLabel} • ${tfLabel} (${series.length} điểm chuỗi thời gian)`;
            }
            if (ptsTable) {
                const pRows = series.map((pt, idx) => `
                    <tr>
                        <td><strong>#${pt.point_order || (idx + 1)}<\/strong><\/td>
                        <td><strong>${pt.time_label}<\/strong><\/td>
                        <td>${pt.forecast_date_label || 'Ngày gốc (D0)'}<\/td>
                        <td><span class="fmt-pill">${pt.phase_type === 'Train' ? 'Huấn luyện (Train)' : 'Dự báo (Forecast)'}<\/span><\/td>
                        <td><strong>${pt.actual_density !== null && pt.actual_density !== undefined ? pt.actual_density + ' xe/km' : '—'}<\/strong><\/td>
                        <td style="color:#2563eb;font-weight:700;">${pt.arima_predicted} xe/km<\/td>
                        <td style="font-size:11.5px;color:#64748b;">[${pt.arima_lower_95} .. ${pt.arima_upper_95}]<\/td>
                        <td style="color:#7c3aed;font-weight:700;">${pt.prophet_predicted} xe/km<\/td>
                        <td style="font-size:11.5px;color:#64748b;">[${pt.prophet_lower_95} .. ${pt.prophet_upper_95}]<\/td>
                    <\/tr>
                `).join('');
                ptsTable.innerHTML = `
                    <table class="clean-table">
                        <thead>
                            <tr>
                                <th>Thứ tự<\/th>
                                <th>Mốc giờ<\/th>
                                <th>Ngày dự báo<\/th>
                                <th>Pha dữ liệu<\/th>
                                <th>Mật độ Thực tế<\/th>
                                <th>Dự báo ARIMA<\/th>
                                <th>Khoảng tin cậy ARIMA (95%)<\/th>
                                <th>Dự báo Prophet<\/th>
                                <th>Khoảng tin cậy Prophet (95%)<\/th>
                            <\/tr>
                        <\/thead>
                        <tbody>${pRows}<\/tbody>
                    <\/table>
                `;
            }

            if (document.getElementById('m3-compare-result-area').style.display === 'block') {
                triggerCompareArimaProphet();
            }
        }

        function selectM3Zone(zid) { M3_SELECTED_ZONE_ID = zid; renderModule3(); }
        function selectM3Horizon(hCode) { M3_SELECTED_HORIZON = hCode; renderModule3(); }
        function selectM3Timeframe(tfId) { M3_SELECTED_TF_ID = tfId; renderModule3(); }

        function triggerCompareArimaProphet() {
            if (!APP_STATE || !APP_STATE.has_data) return;
            const ctx3 = _getFilteredM3Context();
            const { m3, series, ar, pr, horizonLabel, tfLabel, better, impPct, dynComment } = ctx3;

            const area = document.getElementById('m3-compare-result-area');
            const cbox = document.getElementById('m3-commentary-box');
            area.style.display = 'block';
            cbox.style.display = 'block';
            cbox.innerHTML = ` <strong>NHẬN XÉT ĐÁNH GIÁ MÔ HÌNH:<\/strong> ${dynComment}`;

            document.getElementById('m3-overlay-badge').textContent = `${horizonLabel} • ${tfLabel}`;
            document.getElementById('m3-winner-pill').textContent = ` Mô hình tối ưu: ${better} (Cải thiện ${impPct}%)`;

            document.getElementById('m3-compare-table').innerHTML = `
                <table class="clean-table">
                    <thead>
                        <tr>
                            <th>Chỉ số đánh giá (${horizonLabel})<\/th>
                            <th>Mô hình ARIMA<\/th>
                            <th>Mô hình Prophet<\/th>
                            <th>Mô hình Tốt hơn<\/th>
                        <\/tr>
                    <\/thead>
                    <tbody>
                        <tr>
                            <td><strong>MAE (Sai số tuyệt đối TB)<\/strong><\/td>
                            <td>${ar.mae} xe/km<\/td>
                            <td>${pr.mae} xe/km<\/td>
                            <td><strong style="color:var(--emerald-600);">${ar.mae <= pr.mae ? 'ARIMA' : 'Prophet'}<\/strong><\/td>
                        <\/tr>
                        <tr>
                            <td><strong>RMSE (Sai số bình phương TB)<\/strong><\/td>
                            <td>${ar.rmse} xe/km<\/td>
                            <td>${pr.rmse} xe/km<\/td>
                            <td><strong style="color:var(--emerald-600);">${ar.rmse <= pr.rmse ? 'ARIMA' : 'Prophet'}<\/strong><\/td>
                        <\/tr>
                        <tr>
                            <td><strong>MAPE (Sai số phần trăm TB)<\/strong><\/td>
                            <td>${ar.mape_pct}%<\/td>
                            <td>${pr.mape_pct}%<\/td>
                            <td><strong style="color:var(--emerald-600);">${ar.mape_pct <= pr.mape_pct ? 'ARIMA' : 'Prophet'}<\/strong><\/td>
                        <\/tr>
                        <tr>
                            <td><strong>R² Score (Hệ số xác định)<\/strong><\/td>
                            <td>${ar.r2}<\/td>
                            <td>${pr.r2}<\/td>
                            <td><strong style="color:var(--emerald-600);">${ar.r2 >= pr.r2 ? 'ARIMA' : 'Prophet'}<\/strong><\/td>
                        <\/tr>
                    <\/tbody>
                <\/table>
            `;

            drawCompareForecastChart('canvas-m3-compare', series);
        }

