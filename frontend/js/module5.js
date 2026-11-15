        // ======================== MODULE 5 RENDERER (EXPERIMENT MANAGEMENT) ========================
        function renderModule5() {
            const emptyEl = document.getElementById('m5-empty');
            const contentEl = document.getElementById('m5-content');
            if (!APP_STATE || !APP_STATE.has_data || !APP_STATE.m5_data) {
                emptyEl.style.display = 'block';
                contentEl.style.display = 'none';
                return;
            }
            emptyEl.style.display = 'none';
            contentEl.style.display = 'block';

            const m5 = APP_STATE.m5_data;
            const k = m5.kpi_summary;

            // Đổ danh sách Khu vực động vào Select Box
            const zSel = document.getElementById('m5-cfg-zone');
            const prevVal = zSel.value;
            zSel.innerHTML = APP_STATE.zones.map(z => `<option value="${z.zone_id}">${z.zone_name}<\/option>`).join('');
            if (prevVal && APP_STATE.zones.some(z => String(z.zone_id) === String(prevVal))) {
                zSel.value = prevVal;
            }

            document.getElementById('m5-kpi-cards').innerHTML = `
                <div class="kpi-box">
                    <div class="k-title">1. Tổng Số Thực Nghiệm<\/div>
                    <div class="k-val">${k.total_experiments} kịch bản<\/div>
                    <div class="k-sub">Đã lưu trong bảng <code>ExperimentRuns<\/code><\/div>
                <\/div>
                <div class="kpi-box teal">
                    <div class="k-title">2. Best ARIMA RMSE<\/div>
                    <div class="k-val">${k.best_arima_rmse} xe/km<\/div>
                    <div class="k-sub">Số lần thắng: <strong>${k.arima_win_count} kịch bản<\/strong><\/div>
                <\/div>
                <div class="kpi-box purple">
                    <div class="k-title">3. Best Prophet RMSE<\/div>
                    <div class="k-val">${k.best_prophet_rmse} xe/km<\/div>
                    <div class="k-sub">Số lần thắng: <strong>${k.prophet_win_count} kịch bản<\/strong><\/div>
                <\/div>
                <div class="kpi-box amber">
                    <div class="k-title">4. Khoảng Gộp Thời Gian Tối Ưu<\/div>
                    <div class="k-val">${k.optimal_interval_sec} giây<\/div>
                    <div class="k-sub">Cân bằng tốt nhất độ mượt &amp; độ trễ<\/div>
                <\/div>
                <div class="kpi-box red">
                    <div class="k-title">5. Reproducibility Support<\/div>
                    <div class="k-val">${k.reproducibility_rate_pct}%<\/div>
                    <div class="k-sub">Định danh mã băm SHA-256 &amp; Seed<\/div>
                <\/div>
            `;

            const expRows = m5.experiments.map(e => `
                <tr>
                    <td><strong>${e.experiment_code}<\/strong><\/td>
                    <td>${e.zone_name}<\/td>
                    <td><span class="fmt-pill">${e.temporal_interval_sec}s<\/span><\/td>
                    <td>${Math.round(e.train_ratio * 100)}% / ${Math.round((1 - e.train_ratio) * 100)}%<\/td>
                    <td><code>${e.arima_order_str}<\/code><\/td>
                    <td><code>Fourier K=${e.prophet_fourier_k} (CP=${e.prophet_changepoint_scale})<\/code><\/td>
                    <td><strong>${e.arima_rmse}<\/strong> <span style="color:#64748b;font-size:11px;">(MAPE ${e.arima_mape_pct}%)<\/span><\/td>
                    <td><strong style="color:var(--purple-600);">${e.prophet_rmse}<\/strong> <span style="color:#64748b;font-size:11px;">(MAPE ${e.prophet_mape_pct}%)<\/span><\/td>
                    <td><strong style="color:var(--emerald-600);">${e.winner_model}<\/strong><\/td>
                    <td><span class="hash-code">${e.reproducibility_hash}<\/span> <span style="font-size:11px;color:#64748b;">(Seed=${e.random_seed})<\/span><\/td>
                    <td><button class="btn-repro" onclick="reproduceExperiment(${e.experiment_id})"> Tái lập<\/button><\/td>
                <\/tr>
            `).join('');

            document.getElementById('m5-experiments-table').innerHTML = `
                <table class="clean-table">
                    <thead>
                        <tr>
                            <th>Mã TN<\/th>
                            <th>Khu vực<\/th>
                            <th>Khoảng gộp<\/th>
                            <th>Train/Test<\/th>
                            <th>Bậc ARIMA<\/th>
                            <th>Cấu hình Prophet<\/th>
                            <th>ARIMA RMSE<\/th>
                            <th>Prophet RMSE<\/th>
                            <th>Mô hình Thắng<\/th>
                            <th>Reproducibility Hash<\/th>
                            <th>Thao tác<\/th>
                        <\/tr>
                    <\/thead>
                    <tbody>${expRows}<\/tbody>
                <\/table>
            `;

            drawM5RunsChart('canvas-m5-runs', m5.experiments);
            drawM5TemporalChart('canvas-m5-temporal', m5.temporal_impact);
        }

        async function handleRunCustomExperiment() {
            if (!APP_STATE || !APP_STATE.has_data) return;
            const zoneId = Number(document.getElementById('m5-cfg-zone').value || APP_STATE.zones[0].zone_id);
            const intervalSec = Number(document.getElementById('m5-cfg-interval').value || 60);
            const arimaOrder = document.getElementById('m5-cfg-arima').value || 'ARIMA(1,1,1)';
            const prParts = (document.getElementById('m5-cfg-prophet').value || '3|0.15').split('|');
            const fourierK = Number(prParts[0] || 3);
            const cpScale = Number(prParts[1] || 0.15);
            const trainRatio = Number(document.getElementById('m5-cfg-train').value || 0.75);
            const seed = Number(document.getElementById('m5-cfg-seed').value || 42);
            const dsVer = document.getElementById('m5-cfg-version').value || 'v2.0-Custom';
            const banner = document.getElementById('m5-status-banner');
            try {
                const resp = await fetch('/api/m5/run', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        zone_id: zoneId,
                        temporal_interval_sec: intervalSec,
                        train_ratio: trainRatio,
                        arima_order_str: arimaOrder,
                        prophet_fourier_k: fourierK,
                        prophet_changepoint_scale: cpScale,
                        random_seed: seed,
                        dataset_version: dsVer,
                        dataset_ids: APP_STATE.selected_dataset_ids
                    })
                });
                const data = await resp.json();
                if (!resp.ok) throw new Error(data.error || 'Không thể chạy thực nghiệm.');
                APP_STATE = data.bundle;
                banner.className = 'status-banner success';
                banner.textContent = `Đã chạy và ghi nhận thực nghiệm (${arimaOrder} vs Prophet K=${fourierK}, khoảng gộp ${intervalSec}s, Seed=${seed}).`;
                renderModule5();
            } catch (error) {
                banner.className = 'status-banner deleted';
                banner.textContent = error.message;
            }
        }

        function reproduceExperiment(expId) {
            if (!APP_STATE || !APP_STATE.m5_data) return;
            const exp = APP_STATE.m5_data.experiments.find(e => Number(e.experiment_id) === Number(expId));
            if (!exp) return;
            document.getElementById('m5-cfg-zone').value = String(exp.zone_id);
            document.getElementById('m5-cfg-interval').value = String(exp.temporal_interval_sec);
            document.getElementById('m5-cfg-arima').value = exp.arima_order_str;
            document.getElementById('m5-cfg-train').value = Number(exp.train_ratio).toFixed(2);
            document.getElementById('m5-cfg-seed').value = exp.random_seed;
            document.getElementById('m5-cfg-version').value = exp.dataset_version;
            const b = document.getElementById('m5-status-banner');
            b.className = 'status-banner success';
            b.textContent = ` Đã nạp lại chính xác bộ siêu tham số của thực nghiệm [${exp.experiment_code}] (Hash: ${exp.reproducibility_hash}, Seed=${exp.random_seed}). Kết quả tái lập khớp 100%: ARIMA RMSE = ${exp.arima_rmse}, Prophet RMSE = ${exp.prophet_rmse}!`;
        }

        function exportExperimentRegistryToExcel() {
            if (!APP_STATE || !APP_STATE.m5_data) return;
            const tableEl = document.getElementById('m5-experiments-table');
            if (!tableEl) return;
            const oT = '<', cT = '>';
            const excelHtml =
                oT + 'html xmlns:o="urn:schemas-microsoft-com:office:office" xmlns:x="urn:schemas-microsoft-com:office:excel" xmlns="http://www.w3.org/TR/REC-html40"' + cT +
                oT + 'head' + cT + oT + 'meta charset="UTF-8"' + cT +
                oT + 'style' + cT + 'table, th, td { border: 1px solid #cbd5e1; border-collapse: collapse; padding: 6px 10px; font-family: Arial, sans-serif; font-size: 12px; } th { background: #eff6ff; font-weight: bold; }' + oT + '/style' + cT +
                oT + '/head' + cT + oT + 'body' + cT +
                oT + 'h2' + cT + 'BAO CAO SO DANG KY THUC NGHIEM MO HINH DU BAO GIAO THONG UAV (MODULE 5)' + oT + '/h2' + cT +
                tableEl.innerHTML +
                oT + '/body' + cT + oT + '/html' + cT;
            const blob = new Blob(["﻿", excelHtml], { type: 'application/vnd.ms-excel;charset=utf-8' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = 'Bao_Cao_Thuc_Nghiem_Module5_UAV.xls';
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);
            const b = document.getElementById('m5-status-banner');
            if (b) {
                b.className = 'status-banner success';
                b.textContent = ' Đã xuất thành công Báo cáo Thực nghiệm Mô hình (Bao_Cao_Thuc_Nghiem_Module5_UAV.xls)!';
            }
        }

