
        const PRESET_BUNDLES = window.PRESET_BUNDLES;
        PRESET_BUNDLES["UAV_Giao_Thong_Ca_Sang.xlsx"] = PRESET_BUNDLES["DEFAULT_BUNDLE"];
        PRESET_BUNDLES["UAV_Toa_Do_Tu_Dong_Chia_Vung.xlsx"] = PRESET_BUNDLES["DEFAULT_BUNDLE"];
        let APP_STATE = { has_data: false };
        let CURRENT_MODULE = 1;
        let M2_SELECTED_ZONE = "ALL";
        let M2_SELECTED_TF = "ALL";
        let M3_SELECTED_ZONE_ID = null;
        let M3_SELECTED_HORIZON = "DAY_0";
        let M3_SELECTED_TF_ID = "ALL";
        let MODULE_DATASETS = [];
        let SELECTED_ANALYSIS_DATASET_ID = null;
        const SELECTED_DATASET_IDS = new Set();
        let DATASET_PAGE = 1;
        let DATASET_PAGE_ROWS = [];

        // Chặn tuyệt đối hành vi mặc định của trình duyệt (tải ngược hoặc mở file) khi kéo thả file vào bất kỳ vị trí nào trên trang
        ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(evtName => {
            window.addEventListener(evtName, function(e) {
                e.preventDefault();
                e.stopPropagation();
                if (evtName === 'drop' && e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files.length > 0) {
                    const dropArea = document.getElementById('drop-area');
                    if (dropArea) dropArea.classList.remove('dragover');
                    if (CURRENT_MODULE !== 1) switchModule(1);
                    handleFileSelected(e.dataTransfer.files);
                }
            }, false);
        });

        function switchModule(modIndex) {
            CURRENT_MODULE = modIndex;
            for (let i = 1; i <= 6; i++) {
                const b = document.getElementById('btn-tab-' + i);
                const v = document.getElementById('view-module-' + i);
                if (b) {
                    b.classList.toggle('active', i === modIndex);
                    if (i === modIndex) b.setAttribute('aria-current', 'page');
                    else b.removeAttribute('aria-current');
                }
                if (v) v.classList.toggle('active', i === modIndex);
            }
            if (modIndex === 1) {
                updateHeaderAndM1Table();
                loadDatasetLibrary(DATASET_PAGE);
            }
            if (modIndex === 2) renderModule2();
            if (modIndex === 3) renderModule3();
            if (modIndex === 4) renderModule4();
            if (modIndex === 5) renderModule5();
            if (modIndex === 6) renderModule6();
        }

        function showBanner(msg, typeClass) {
            const b = document.getElementById('m1-status-banner');
            b.className = 'status-banner ' + typeClass;
            b.textContent = msg;
        }

        function setStreamingProgress(visible, text, pct) {
            const wrap = document.getElementById('m1-progress-wrap');
            if (!visible) {
                wrap.style.display = 'none';
                return;
            }
            wrap.style.display = 'block';
            document.getElementById('m1-progress-text').textContent = text;
            document.getElementById('m1-progress-pct').textContent = pct + '%';
            document.getElementById('m1-progress-fill').style.width = pct + '%';
        }

        // Chuyển đổi ArrayBuffer sang Base64 theo từng khối 8KB để KHÔNG BAO GIỜ tràn ngăn xếp (Maximum call stack size exceeded)
        function arrayBufferToBase64Chunked(buffer) {
            const bytes = new Uint8Array(buffer);
            const chunkSize = 8192;
            let binary = '';
            for (let i = 0; i < bytes.length; i += chunkSize) {
                const sub = bytes.subarray(i, Math.min(i + chunkSize, bytes.length));
                binary += String.fromCharCode.apply(null, sub);
            }
            return btoa(binary);
        }

        function formatFileSize(sizeKb) {
            if (sizeKb >= 1024 * 1024) return (sizeKb / (1024 * 1024)).toFixed(2) + ' GB';
            if (sizeKb >= 1024) return (sizeKb / 1024).toFixed(2) + ' MB';
            return sizeKb.toFixed(1) + ' KB';
        }

        function updateHeaderAndM1Table() {
            const badge = document.getElementById('header-db-status');
            const pulse = document.getElementById('header-pulse');
            const tag = document.getElementById('m1-active-file-tag');
            const wrap = document.getElementById('m1-db-table-wrap');
            const pipeWrap = document.getElementById('m1-pipeline-cards');
            const metaPanel = document.getElementById('m1-meta-preview-panel');
            const metaWrap = document.getElementById('m1-metadata-wrap');
            const prevWrap = document.getElementById('m1-preview-wrap');

            if (!APP_STATE || !APP_STATE.has_data) {
                pulse.className = 'pulse-dot empty';
                badge.textContent = "Database: Đang trống (0 bản ghi)";
                tag.textContent = "Chưa có file dữ liệu nào trong Database";
                pipeWrap.innerHTML = '';
                if (metaPanel) metaPanel.style.display = 'none';
                wrap.innerHTML = `<table class="clean-table">
                    <thead><tr><th>STT<\/th><th>Tên Bảng (TableName)<\/th><th>Số bản ghi (TotalRows)<\/th><th>Vai trò trong 6 Module<\/th><\/tr><\/thead>
                    <tbody>
                        <tr><td>1<\/td><td><strong>DatasetImports<\/strong><\/td><td>0<\/td><td>Module 1: Quản lý file .xlsx / .xls / .csv (<= 3 GB) nạp vào<\/td><\/tr>
                        <tr><td>2<\/td><td><strong>DynamicZones<\/strong><\/td><td>0<\/td><td>Module 1 &amp; 2: Danh mục Khu vực chia tự động từ dữ liệu<\/td><\/tr>
                        <tr><td>3<\/td><td><strong>DynamicTimeFrames<\/strong><\/td><td>0<\/td><td>Module 1, 2 &amp; 3: Danh mục Khung giờ chia tự động từ dữ liệu<\/td><\/tr>
                        <tr><td>4<\/td><td><strong>CleanedTrajectories<\/strong><\/td><td>0<\/td><td>Module 1, 2 &amp; 4: Quỹ đạo phương tiện UAV sau tiền xử lý<\/td><\/tr>
                        <tr><td>5<\/td><td><strong>TrafficPatternMetrics<\/strong><\/td><td>0<\/td><td>Module 2, 3, 4 &amp; 6: Chỉ số giao thông theo Khu vực &amp; Khung giờ<\/td><\/tr>
                        <tr><td>6<\/td><td><strong>ForecastComparisons<\/strong><\/td><td>0<\/td><td>Module 3, 4 &amp; 6: Đánh giá &amp; Nhận xét so sánh ARIMA vs Prophet<\/td><\/tr>
                        <tr><td>7<\/td><td><strong>ForecastPoints<\/strong><\/td><td>0<\/td><td>Module 3, 4 &amp; 6: Điểm dự báo ARIMA &amp; Prophet (Ngày 0, Ngày +1, Ngày +2)<\/td><\/tr>
                        <tr><td>8<\/td><td><strong>ExperimentRuns<\/strong><\/td><td>0<\/td><td>Module 5: Cấu hình thực nghiệm, siêu tham số &amp; tái lập nghiên cứu<\/td><\/tr>
                        <tr><td>9<\/td><td><strong>GeneratedReports<\/strong><\/td><td>0<\/td><td>Module 6: Quản lý báo cáo phân tích/dự báo &amp; xuất file PDF / Excel<\/td><\/tr>
                        <tr><td>10<\/td><td><strong>AnalysisRuns<\/strong><\/td><td>0<\/td><td>Lịch sử tổng hợp chuỗi thời gian đa Dataset<\/td><\/tr>
                        <tr><td>11<\/td><td><strong>AnalysisRunDatasets<\/strong><\/td><td>0<\/td><td>Liên kết lần phân tích với Dataset được chọn<\/td><\/tr>
                        <tr><td>12<\/td><td><strong>ForecastRuns<\/strong><\/td><td>0<\/td><td>Lịch sử dự báo ARIMA/Prophet đa Dataset<\/td><\/tr>
                        <tr><td>13<\/td><td><strong>ForecastRunDatasets<\/strong><\/td><td>0<\/td><td>Liên kết Forecast Run với Dataset được chọn<\/td><\/tr>
                        <tr><td>14<\/td><td><strong>ForecastResults<\/strong><\/td><td>0<\/td><td>Kết quả holdout và điểm dự báo tương lai<\/td><\/tr>
                    <\/tbody>
                <\/table>`;
                return;
            }

            if (metaPanel) metaPanel.style.display = 'block';
            pulse.className = 'pulse-dot';
            const imp = APP_STATE.import_info;
            const sizeStr = formatFileSize(Number(imp.file_size_kb || 250));
            badge.textContent = `DB Active: ${imp.file_name} (${sizeStr} | ${imp.cleaned_row_count.toLocaleString()} điểm sạch | ${imp.dynamic_zone_count} Khu vực | ${imp.dynamic_timeframe_count} Khung giờ)`;
            tag.textContent = `Đang nạp: ${imp.file_name} (${sizeStr}) • Khoảng thời gian: ${imp.time_range_start} → ${imp.time_range_end}`;

            const removedTotal = (imp.removed_missing_dup || 0) + (imp.removed_stationary || 0) + (imp.removed_outliers || 0);
            const qualityPct = imp.raw_row_count > 0 ? ((imp.cleaned_row_count / imp.raw_row_count) * 100).toFixed(1) : '100.0';
            pipeWrap.innerHTML = `
                <div class="pipe-card">
                    <div class="p-step">Bước 1 • File Đầu Vào<\/div>
                    <div class="p-val">${imp.raw_row_count.toLocaleString()} dòng<\/div>
                    <div class="p-desc">${imp.file_name} (${sizeStr})<\/div>
                <\/div>
                <div class="pipe-card" style="border-left-color:var(--amber-600);">
                    <div class="p-step">Bước 2 • Lọc Nhiễu &amp; Xe Đỗ Tĩnh<\/div>
                    <div class="p-val">-${removedTotal.toLocaleString()} dòng<\/div>
                    <div class="p-desc">Trùng/Thiếu: ${imp.removed_missing_dup} | Đỗ tĩnh: ${imp.removed_stationary} | Ngoại lai: ${imp.removed_outliers}<\/div>
                <\/div>
                <div class="pipe-card" style="border-left-color:var(--teal-600);">
                    <div class="p-step">Bước 3 • Dữ Liệu Sạch Nạp DB<\/div>
                    <div class="p-val">${imp.cleaned_row_count.toLocaleString()} điểm<\/div>
                    <div class="p-desc">Đã chuẩn hóa tọa độ (X, Y) &amp; vận tốc km/h<\/div>
                <\/div>
                <div class="pipe-card" style="border-left-color:var(--purple-600);">
                    <div class="p-step">Bước 4 • Chia Vùng, Dự Báo 2 Ngày &amp; Thực Nghiệm<\/div>
                    <div class="p-val">${imp.dynamic_zone_count} Vùng × ${imp.dynamic_timeframe_count} Giờ<\/div>
                    <div class="p-desc">9 bảng cốt lõi + 5 bảng lịch sử, dự báo +2 ngày &amp; thực nghiệm<\/div>
                <\/div>
            `;

            if (metaWrap) {
                const pMethod = (APP_STATE.zones && APP_STATE.zones[0]) ? APP_STATE.zones[0].partition_method : 'Dynamic_Spatial_Partition';
                metaWrap.innerHTML = `
                    <table class="clean-table">
                        <thead><tr><th>Hạng Mục Kiểm Định &amp; Metadata<\/th><th>Giá Trị / Kết Quả Kiểm Tra<\/th><th>Trạng Thái<\/th><\/tr><\/thead>
                        <tbody>
                            <tr><td><strong>Phiên bản Tập dữ liệu (Dataset Version)<\/strong><\/td><td><code>v2.0-${imp.file_name.slice(0, 18)}<\/code> (Import ID #${imp.import_id || 1})<\/td><td><span class="cong-pill cong-Free">Active<\/span><\/td><\/tr>
                            <tr><td><strong>Kiểm tra Cấu trúc Cột (Schema Validation)<\/strong><\/td><td>Chuẩn hóa tự động <code>vehicle_id, time, x_coord_m, y_coord_m, speed_kmh, accel_ms2<\/code><\/td><td><span class="cong-pill cong-Free">Hợp lệ 100%<\/span><\/td><\/tr>
                            <tr><td><strong>Kiểm tra Giá trị thiếu &amp; Bản ghi trùng<\/strong><\/td><td>Đã phát hiện và loại bỏ <strong>${imp.removed_missing_dup}<\/strong> bản ghi thiếu/trùng lặp<\/td><td><span class="cong-pill cong-Free">Đã làm sạch<\/span><\/td><\/tr>
                            <tr><td><strong>Kiểm định Vận tốc &amp; Gia tốc (Outlier Filter)<\/strong><\/td><td>Lọc bỏ <strong>${imp.removed_stationary}<\/strong> xe đỗ tĩnh (&le;0.5 km/h) &amp; <strong>${imp.removed_outliers}<\/strong> ngoại lai (&gt;120 km/h)<\/td><td><span class="cong-pill cong-Free">Đạt chuẩn<\/span><\/td><\/tr>
                            <tr><td><strong>Kiểm định Mốc thời gian &amp; Tọa độ (X, Y)<\/strong><\/td><td><code>${imp.time_range_start} &rarr; ${imp.time_range_end}<\/code> (${pMethod})<\/td><td><span class="cong-pill cong-Free">Quality ${qualityPct}%<\/span><\/td><\/tr>
                        <\/tbody>
                    <\/table>
                `;
            }

            if (prevWrap) {
                const pRows = (APP_STATE.preview_rows && APP_STATE.preview_rows.length) ? APP_STATE.preview_rows : [];
                const prevHtml = pRows.slice(0, 6).map(r => `
                    <tr>
                        <td><strong>${r.vehicle_id}<\/strong><\/td>
                        <td>${r.vehicle_type}<\/td>
                        <td>${String(r.recorded_time_str || '').slice(-8)}<\/td>
                        <td>${r.zone_name}<\/td>
                        <td>(${r.x_coord_m}m, ${r.y_coord_m}m)<\/td>
                        <td><strong style="color:var(--blue-600);">${r.speed_kmh} km/h<\/strong><\/td>
                    <\/tr>
                `).join('');
                prevWrap.innerHTML = `
                    <table class="clean-table">
                        <thead><tr><th>Mã Xe<\/th><th>Loại Xe<\/th><th>Giờ Ghi<\/th><th>Khu Vực Động<\/th><th>Tọa Độ (X, Y)<\/th><th>Vận Tốc<\/th><\/tr><\/thead>
                        <tbody>${prevHtml}<\/tbody>
                    <\/table>
                `;
            }

            let rowsHtml = APP_STATE.db_tables.map(r => `
                <tr>
                    <td>${r.STT}<\/td>
                    <td><strong>${r.TableName}<\/strong><\/td>
                    <td><strong style="color:var(--blue-600);font-size:14px;">${r.TotalRows.toLocaleString()}<\/strong><\/td>
                    <td>${r.Chuc_Nang}<\/td>
                <\/tr>
            `).join('');
            wrap.innerHTML = `<table class="clean-table">
                <thead><tr><th>STT<\/th><th>Tên Bảng (TableName)<\/th><th>Số bản ghi (TotalRows)<\/th><th>Vai trò trong 6 Module<\/th><\/tr><\/thead>
                <tbody>${rowsHtml}<\/tbody>
            <\/table>`;
        }

