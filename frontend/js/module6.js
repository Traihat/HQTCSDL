        // ======================== MODULE 6 RENDERER (REPORTING & PDF / EXCEL EXPORT) ========================
        function renderModule6() {
            const emptyEl = document.getElementById('m6-empty');
            const contentEl = document.getElementById('m6-content');
            if (!APP_STATE || !APP_STATE.has_data || !APP_STATE.m6_data) {
                emptyEl.style.display = 'block';
                contentEl.style.display = 'none';
                return;
            }
            emptyEl.style.display = 'none';
            contentEl.style.display = 'block';

            const m6 = APP_STATE.m6_data;
            const info = m6.dataset_info;

            const zScopeSel = document.getElementById('m6-zone-scope');
            const prevScope = zScopeSel.value;
            let scopeHtml = `<option value="ALL">Tất cả ${APP_STATE.zones.length} Khu vực động<\/option>`;
            APP_STATE.zones.forEach(z => {
                scopeHtml += `<option value="${z.zone_name}">${z.zone_name}<\/option>`;
            });
            zScopeSel.innerHTML = scopeHtml;
            if (prevScope && (prevScope === 'ALL' || APP_STATE.zones.some(z => z.zone_name === prevScope))) {
                zScopeSel.value = prevScope;
            } else {
                zScopeSel.value = 'ALL';
            }
            const selectedScope = zScopeSel.value || 'ALL';
            const scopeLabel = selectedScope === 'ALL' ? `Tất cả ${APP_STATE.zones.length} Khu vực động` : selectedScope;

            document.getElementById('m6-dataset-tag').textContent =
                `Nguồn: ${info.file_name} (${info.cleaned_rows.toLocaleString()} điểm sạch) • Phạm vi đang lọc: ${scopeLabel}`;

            const rType = document.getElementById('m6-report-type').value || 'Comprehensive_Full';
            document.getElementById('m6-sec-traffic').style.display = (rType === 'Comprehensive_Full' || rType === 'Traffic_Analysis') ? 'block' : 'none';
            document.getElementById('m6-sec-forecast').style.display = (rType === 'Comprehensive_Full' || rType === 'Forecast_2Days') ? 'block' : 'none';
            document.getElementById('m6-sec-performance').style.display = (rType === 'Comprehensive_Full' || rType === 'Performance_Experiment') ? 'block' : 'none';

            // 1. Traffic Analysis Table (Lọc theo Phạm vi Khu vực đang chọn)
            const filteredTraffic = (m6.traffic_analysis_table || []).filter(r =>
                selectedScope === 'ALL' || r.Ten_Khu_Vuc === selectedScope
            );
            const trRows = filteredTraffic.map(r => `
                <tr>
                    <td><code>${r.Ma_Khu_Vuc}<\/code><\/td>
                    <td><strong>${r.Ten_Khu_Vuc}<\/strong><\/td>
                    <td>${r.Chieu_Dai_Km} km<\/td>
                    <td><strong>${Number(r.Tong_Luot_Xe).toLocaleString()}<\/strong><\/td>
                    <td>${r.Van_Toc_TB_Kmh} km/h<\/td>
                    <td><strong style="color:var(--blue-600);">${r.Mat_Do_TB_Xe_Km}<\/strong> (Đỉnh: ${r.Mat_Do_Dinh_Xe_Km})<\/td>
                    <td>${r.Luu_Luong_TB_Xe_Gio} xe/h<\/td>
                    <td>${r.So_Cua_So_Cao_Diem}<\/td>
                    <td><strong style="color:var(--red-600);">${r.So_Diem_Nong_Un_Tac}<\/strong><\/td>
                <\/tr>
            `).join('');
            document.getElementById('m6-traffic-table').innerHTML = `
                <table class="clean-table">
                    <thead>
                        <tr>
                            <th>Mã Vùng<\/th><th>Tên Khu Vực Động<\/th><th>Chiều Dài<\/th><th>Tổng Lượt Xe<\/th>
                            <th>Vận Tốc TB<\/th><th>Mật Độ TB (Đỉnh)<\/th><th>Lưu Lượng TB<\/th><th>Cửa Sổ Cao Điểm<\/th><th>Điểm Nóng Ùn Tắc<\/th>
                        <\/tr>
                    <\/thead>
                    <tbody>${trRows}<\/tbody>
                <\/table>
            `;

            // 2A. Forecast Comparison Table (Lọc theo Phạm vi Khu vực đang chọn)
            const filteredForecast = (m6.forecast_comparison_table || []).filter(r =>
                selectedScope === 'ALL' || r.Khu_Vuc === selectedScope
            );
            const fcRows = filteredForecast.map(r => `
                <tr>
                    <td><strong>${r.Khu_Vuc}<\/strong><\/td>
                    <td><code>${r.Cau_Hinh_ARIMA}<\/code><\/td>
                    <td>${r.ARIMA_RMSE} xe/km (${r.ARIMA_MAPE_Pct}%)<\/td>
                    <td>${r.Prophet_RMSE} xe/km (${r.Prophet_MAPE_Pct}%)<\/td>
                    <td><strong style="color:var(--emerald-600);">${r.Mo_Hinh_Toi_Uu} (+${r.Cai_Thien_RMSE_Pct}%)<\/strong><\/td>
                <\/tr>
            `).join('');
            document.getElementById('m6-forecast-table').innerHTML = `
                <table class="clean-table">
                    <thead>
                        <tr><th>Khu Vực<\/th><th>Mô Hình ARIMA<\/th><th>ARIMA RMSE (MAPE)<\/th><th>Prophet RMSE (MAPE)<\/th><th>Mô Hình Tối Ưu<\/th><\/tr>
                    <\/thead>
                    <tbody>${fcRows}<\/tbody>
                <\/table>
            `;

            // 2B. Multi-Day (+2 Days) Forecast Table (Lọc theo Phạm vi Khu vực đang chọn)
            const filteredMultiday = (m6.multiday_forecast_table || []).filter(r =>
                selectedScope === 'ALL' || r.Khu_Vuc === selectedScope
            );
            const mdRows = filteredMultiday.map(r => `
                <tr>
                    <td><strong>${r.Khu_Vuc}<\/strong><\/td>
                    <td><span class="fmt-pill">${r.Tam_Nhin_Du_Bao}<\/span><\/td>
                    <td>${r.Mat_Do_Tham_Chieu_TB} xe/km<\/td>
                    <td><strong>${r.ARIMA_Du_Bao_TB}<\/strong> (Đỉnh: ${r.ARIMA_Du_Bao_Dinh})<\/td>
                    <td><strong style="color:var(--purple-600);">${r.Prophet_Du_Bao_TB}<\/strong> (Đỉnh: ${r.Prophet_Du_Bao_Dinh})<\/td>
                <\/tr>
            `).join('');
            document.getElementById('m6-multiday-table').innerHTML = `
                <table class="clean-table">
                    <thead>
                        <tr><th>Khu Vực<\/th><th>Tầm Nhìn Ngày Dự Báo<\/th><th>Mật Độ Tham Chiếu<\/th><th>Dự Báo ARIMA (TB / Đỉnh)<\/th><th>Dự Báo Prophet (TB / Đỉnh)<\/th><\/tr>
                    <\/thead>
                    <tbody>${mdRows}<\/tbody>
                <\/table>
            `;

            // 3A. Experiment Table (Lọc theo Phạm vi Khu vực đang chọn)
            const filteredExps = (m6.performance_experiment_table || []).filter(r =>
                selectedScope === 'ALL' || r.Khu_Vuc === selectedScope
            );
            const exRows = filteredExps.map(r => `
                <tr>
                    <td><strong>${r.Ma_Thuc_Nghiem}<\/strong><\/td>
                    <td>${r.Khu_Vuc}<\/td>
                    <td>${r.Khoang_Gop_Giay}s<\/td>
                    <td>${r.ARIMA_RMSE}<\/td>
                    <td>${r.Prophet_RMSE}<\/td>
                    <td><strong style="color:var(--emerald-600);">${r.Mo_Hinh_Thang}<\/strong><\/td>
                    <td><span class="hash-code">${r.Ma_Bam_Tai_Lap}<\/span><\/td>
                <\/tr>
            `).join('');
            document.getElementById('m6-experiment-table').innerHTML = `
                <table class="clean-table">
                    <thead>
                        <tr><th>Mã TN<\/th><th>Khu Vực<\/th><th>Khoảng Gộp<\/th><th>ARIMA RMSE<\/th><th>Prophet RMSE<\/th><th>Thắng<\/th><th>Mã Băm Tái Lập<\/th><\/tr>
                    <\/thead>
                    <tbody>${exRows}<\/tbody>
                <\/table>
            `;

            // 3B. GeneratedReports Audit Log Table (Lọc theo Phạm vi Khu vực đang chọn)
            const filteredHist = (m6.reports_history || []).filter(r =>
                selectedScope === 'ALL' || !r.zone_scope || r.zone_scope.includes('Tất cả') || r.zone_scope === selectedScope
            );
            const histRows = filteredHist.map(r => `
                <tr>
                    <td><strong>${r.report_code}<\/strong><\/td>
                    <td>${r.report_type}<\/td>
                    <td><span class="fmt-pill">${r.export_format}<\/span><\/td>
                    <td>${r.zone_scope}<\/td>
                    <td>${r.generated_at}<\/td>
                <\/tr>
            `).join('');
            document.getElementById('m6-history-table').innerHTML = `
                <table class="clean-table">
                    <thead>
                        <tr><th>Mã Báo Cáo<\/th><th>Loại Báo Cáo<\/th><th>Định Dạng<\/th><th>Phạm Vi Khu Vực<\/th><th>Thời Gian Xuất<\/th><\/tr>
                    <\/thead>
                    <tbody>${histRows}<\/tbody>
                <\/table>
            `;
        }

        async function handleExportReport(fmt) {
            if (!APP_STATE || !APP_STATE.has_data || !APP_STATE.m6_data) return;
            const rType = document.getElementById('m6-report-type').value || 'Comprehensive_Full';
            const zScopeVal = document.getElementById('m6-zone-scope').value || 'ALL';
            const zScopeText = zScopeVal === 'ALL' ? `Tất cả ${APP_STATE.zones.length} Khu vực động` : zScopeVal;
            const horizonScope = 'Ngày gốc (Day 0) + Dự báo 2 Ngày sau đó (+24h / +48h)';

            try {
                const resp = await fetch('/api/m6/export', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        report_type: rType,
                        export_format: fmt,
                        zone_scope: zScopeText,
                        horizon_scope: horizonScope,
                        dataset_ids: APP_STATE.selected_dataset_ids
                    })
                });
                const data = await resp.json();
                if (!resp.ok) throw new Error(data.error || 'Không thể lưu nhật ký báo cáo.');
                APP_STATE = data.bundle;
            } catch (error) {
                const banner = document.getElementById('m6-export-banner');
                banner.className = 'status-banner deleted';
                banner.textContent = error.message;
                return;
            }

            renderModule6();
            const b = document.getElementById('m6-export-banner');
            b.className = 'status-banner success';

            if (fmt === 'EXCEL') {
                // Tạo file Excel (.xls chuẩn Spreadsheet HTML Table đa bảng) tải trực tiếp về máy
                // Lưu ý: ghép thẻ bằng oT/cT để các công cụ Live Server không bao giờ chèn nhầm script vào chuỗi này
                const m6 = APP_STATE.m6_data;
                const oT = '<', cT = '>';
                const excelHtml = [
                    oT + 'html xmlns:o="urn:schemas-microsoft-com:office:office" xmlns:x="urn:schemas-microsoft-com:office:excel" xmlns="http://www.w3.org/TR/REC-html40"' + cT,
                    oT + 'head' + cT + oT + 'meta charset="UTF-8"' + cT + oT + '/head' + cT,
                    oT + 'body' + cT,
                    oT + 'h2' + cT + 'BÁO CÁO HỆ THỐNG PHÂN TÍCH & DỰ BÁO GIAO THÔNG ĐÔ THỊ TỪ UAV (' + rType + ')' + oT + '/h2' + cT,
                    oT + 'p' + cT + oT + 'b' + cT + 'Nguồn dữ liệu:' + oT + '/b' + cT + ' ' + m6.dataset_info.file_name + ' | ' + oT + 'b' + cT + 'Phạm vi:' + oT + '/b' + cT + ' ' + zScopeText + ' | ' + oT + 'b' + cT + 'Tầm nhìn:' + oT + '/b' + cT + ' ' + horizonScope + oT + '/p' + cT,
                    oT + 'h3' + cT + '1. BẢNG PHÂN TÍCH MẪU HÌNH GIAO THÔNG THEO KHU VỰC ĐỘNG' + oT + '/h3' + cT,
                    document.getElementById('m6-traffic-table').innerHTML,
                    oT + 'h3' + cT + '2. BẢNG ĐỐI CHIẾU ĐỘ CHÍNH XÁC DỰ BÁO ARIMA VS PROPHET' + oT + '/h3' + cT,
                    document.getElementById('m6-forecast-table').innerHTML,
                    oT + 'h3' + cT + '3. BẢNG DỰ BÁO ĐA NGÀY (NGÀY GỐC DAY 0, NGÀY +1 VÀ NGÀY +2)' + oT + '/h3' + cT,
                    document.getElementById('m6-multiday-table').innerHTML,
                    oT + 'h3' + cT + '4. BẢNG KẾT QUẢ THỰC NGHIỆM & MÃ BĂM TÁI LẬP (EXPERIMENT RUNS)' + oT + '/h3' + cT,
                    document.getElementById('m6-experiment-table').innerHTML,
                    oT + '/body' + cT + oT + '/html' + cT
                ].join('\n');
                const blob = new Blob(['\ufeff', excelHtml], { type: 'application/vnd.ms-excel;charset=utf-8' });
                const url = URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = `Bao_Cao_Giao_Thong_UAV_${rType}.xls`;
                document.body.appendChild(a);
                a.click();
                document.body.removeChild(a);
                URL.revokeObjectURL(url);
                b.textContent = ` Đã kết xuất thành công Báo cáo Excel (Bao_Cao_Giao_Thong_UAV_${rType}.xls) và lưu nhật ký vào bảng GeneratedReports!`;
            } else {
                b.textContent = ` Đã ghi nhận Báo cáo PDF vào bảng GeneratedReports và mở hộp thoại In / Lưu PDF!`;
                setTimeout(() => window.print(), 250);
            }
        }

        function drawM5RunsChart(canvasId, exps) {
            const { ctx, w, h } = _prepCanvas(canvasId);
            if (!exps || !exps.length) return;
            const list = exps.slice(0, 6).reverse();
            const padL = 46, padR = 18, padT = 30, padB = 42;
            const pw = w - padL - padR, ph = h - padT - padB;
            const maxR = Math.max(...list.map(e => Math.max(e.arima_rmse, e.prophet_rmse)), 1) * 1.22;
            const grpW = pw / list.length;

            ctx.strokeStyle = '#f1f5f9';
            for (let i = 0; i <= 4; i++) {
                const y = padT + (ph * i) / 4;
                ctx.beginPath(); ctx.moveTo(padL, y); ctx.lineTo(w - padR, y); ctx.stroke();
                ctx.fillStyle = '#64748b'; ctx.font = '600 10.5px Inter, sans-serif';
                ctx.fillText(((maxR * (4 - i)) / 4).toFixed(1), 10, y + 4);
            }

            list.forEach((e, i) => {
                const x0 = padL + i * grpW + 12;
                const bw = Math.min(26, (grpW - 24) / 2);
                const hA = (e.arima_rmse / maxR) * ph;
                const hP = (e.prophet_rmse / maxR) * ph;

                ctx.fillStyle = '#2563eb';
                ctx.fillRect(x0, padT + ph - hA, bw, hA);
                ctx.fillStyle = '#7c3aed';
                ctx.fillRect(x0 + bw + 4, padT + ph - hP, bw, hP);

                ctx.fillStyle = '#0f172a'; ctx.font = '700 10px Inter, sans-serif';
                ctx.fillText(e.arima_rmse.toFixed(2), x0 - 2, padT + ph - hA - 5);
                ctx.fillStyle = '#5b21b6';
                ctx.fillText(e.prophet_rmse.toFixed(2), x0 + bw + 3, padT + ph - hP - 5);

                ctx.fillStyle = '#334155'; ctx.font = '700 10.5px Inter, sans-serif';
                ctx.fillText(`${e.experiment_code} (${e.temporal_interval_sec}s)`, x0 - 4, h - 14);
            });
            ctx.fillStyle = '#2563eb'; ctx.font = '700 11.5px Inter, sans-serif';
            ctx.fillText(' ARIMA RMSE (xe/km)', padL, 18);
            ctx.fillStyle = '#7c3aed';
            ctx.fillText(' Prophet RMSE (xe/km)', padL + 165, 18);
        }

        function drawM5TemporalChart(canvasId, tList) {
            const { ctx, w, h } = _prepCanvas(canvasId);
            if (!tList || !tList.length) return;
            const padL = 48, padR = 24, padT = 32, padB = 40;
            const pw = w - padL - padR, ph = h - padT - padB;
            const maxY = Math.max(...tList.map(t => Math.max(t.avg_arima_rmse, t.avg_prophet_rmse)), 1) * 1.22;

            ctx.strokeStyle = '#f1f5f9';
            for (let i = 0; i <= 4; i++) {
                const y = padT + (ph * i) / 4;
                ctx.beginPath(); ctx.moveTo(padL, y); ctx.lineTo(w - padR, y); ctx.stroke();
                ctx.fillStyle = '#64748b'; ctx.font = '600 10.5px Inter, sans-serif';
                ctx.fillText(((maxY * (4 - i)) / 4).toFixed(1), 10, y + 4);
            }

            const drawLine = (field, color) => {
                ctx.strokeStyle = color; ctx.lineWidth = 2.8;
                ctx.beginPath();
                tList.forEach((t, i) => {
                    const x = padL + (pw * i) / Math.max(tList.length - 1, 1);
                    const y = padT + ph - (t[field] / maxY) * ph;
                    if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
                });
                ctx.stroke();
                tList.forEach((t, i) => {
                    const x = padL + (pw * i) / Math.max(tList.length - 1, 1);
                    const y = padT + ph - (t[field] / maxY) * ph;
                    ctx.fillStyle = color;
                    ctx.beginPath(); ctx.arc(x, y, 4.5, 0, Math.PI * 2); ctx.fill();
                    ctx.fillText(t[field].toFixed(2), x - 10, y - 9);
                    ctx.fillStyle = '#334155'; ctx.font = '700 11px Inter, sans-serif';
                    ctx.fillText(`Gộp ${t.temporal_interval_sec}s`, x - 22, h - 12);
                });
            };

            drawLine('avg_arima_rmse', '#2563eb');
            drawLine('avg_prophet_rmse', '#7c3aed');

            ctx.fillStyle = '#2563eb'; ctx.font = '700 11.5px Inter, sans-serif';
            ctx.fillText(' ARIMA RMSE theo Khoảng gộp', padL, 18);
            ctx.fillStyle = '#7c3aed';
            ctx.fillText(' Prophet RMSE theo Khoảng gộp', padL + 210, 18);
        }

