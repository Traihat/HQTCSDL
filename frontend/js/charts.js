        // ======================== HIGH-DPI RETINA CANVAS ENGINE ========================
        const PALETTE = ['#2563eb', '#0d9488', '#d97706', '#dc2626', '#7c3aed', '#0284c7'];

        function _prepCanvas(canvasId) {
            const c = document.getElementById(canvasId);
            const dpr = window.devicePixelRatio || 1;
            const rectW = c.clientWidth || Number(c.getAttribute('width')) || 660;
            const rectH = c.clientHeight || Number(c.getAttribute('height')) || 285;
            c.width = rectW * dpr;
            c.height = rectH * dpr;
            const ctx = c.getContext('2d');
            ctx.scale(dpr, dpr);
            ctx.clearRect(0, 0, rectW, rectH);
            return { c, ctx, w: rectW, h: rectH };
        }

        function shortTimeLabel(value) {
            const match = String(value || '').match(/\b\d{1,2}:\d{2}\b/);
            return match ? match[0] : String(value || '');
        }

        function drawM2TimelineChart(series) {
            const { ctx, w, h } = _prepCanvas('canvas-m2-timeline');
            if (!series || series.length === 0) return;
            const padL = 52, padR = 48, padT = 32, padB = 40;
            const pw = w - padL - padR, ph = h - padT - padB;

            const dens = series.map(s => s.traffic_density_veh_km);
            const spds = series.map(s => s.avg_speed_kmh);
            const maxD = Math.max(...dens, 10) * 1.15;
            const maxS = Math.max(...spds, 10) * 1.15;

            ctx.strokeStyle = '#f1f5f9';
            ctx.lineWidth = 1;
            for (let i = 0; i <= 4; i++) {
                const y = padT + (ph * i) / 4;
                ctx.beginPath(); ctx.moveTo(padL, y); ctx.lineTo(w - padR, y); ctx.stroke();
                ctx.fillStyle = '#475569'; ctx.font = '600 11px Inter, sans-serif';
                ctx.fillText(((maxD * (4 - i)) / 4).toFixed(0), 12, y + 4);
                ctx.fillStyle = '#d97706';
                ctx.fillText(((maxS * (4 - i)) / 4).toFixed(0), w - padR + 8, y + 4);
            }

            // Vùng gradient dưới đường mật độ
            const grad = ctx.createLinearGradient(0, padT, 0, padT + ph);
            grad.addColorStop(0, 'rgba(37, 99, 235, 0.24)');
            grad.addColorStop(1, 'rgba(37, 99, 235, 0.01)');
            ctx.fillStyle = grad;
            ctx.beginPath();
            series.forEach((s, i) => {
                const x = padL + (pw * i) / Math.max(series.length - 1, 1);
                const y = padT + ph - (s.traffic_density_veh_km / maxD) * ph;
                if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
            });
            ctx.lineTo(padL + pw, padT + ph);
            ctx.lineTo(padL, padT + ph);
            ctx.closePath();
            ctx.fill();

            // Đường mật độ
            ctx.strokeStyle = '#2563eb'; ctx.lineWidth = 2.8;
            ctx.beginPath();
            series.forEach((s, i) => {
                const x = padL + (pw * i) / Math.max(series.length - 1, 1);
                const y = padT + ph - (s.traffic_density_veh_km / maxD) * ph;
                if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
            });
            ctx.stroke();

            // Chấm đỏ giờ cao điểm
            series.forEach((s, i) => {
                const x = padL + (pw * i) / Math.max(series.length - 1, 1);
                const y = padT + ph - (s.traffic_density_veh_km / maxD) * ph;
                if (s.is_peak_hour) {
                    ctx.fillStyle = 'rgba(220, 38, 38, 0.22)';
                    ctx.beginPath(); ctx.arc(x, y, 9, 0, Math.PI * 2); ctx.fill();
                }
                ctx.fillStyle = s.is_peak_hour ? '#dc2626' : '#2563eb';
                ctx.beginPath(); ctx.arc(x, y, s.is_peak_hour ? 5 : 3, 0, Math.PI * 2); ctx.fill();
            });

            // Đường vận tốc
            ctx.strokeStyle = '#d97706'; ctx.lineWidth = 2.2; ctx.setLineDash([5, 4]);
            ctx.beginPath();
            series.forEach((s, i) => {
                const x = padL + (pw * i) / Math.max(series.length - 1, 1);
                const y = padT + ph - (s.avg_speed_kmh / maxS) * ph;
                if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
            });
            ctx.stroke();
            ctx.setLineDash([]);

            ctx.fillStyle = '#475569'; ctx.font = '600 10px Inter, sans-serif';
            ctx.textAlign = 'center';
            const labelCount = Math.min(series.length, Math.max(2, Math.floor(pw / 76)));
            for (let tick = 0; tick < labelCount; tick++) {
                const index = labelCount === 1
                    ? 0
                    : Math.round((tick * (series.length - 1)) / (labelCount - 1));
                const x = padL + (pw * index) / Math.max(series.length - 1, 1);
                ctx.fillText(shortTimeLabel(series[index].window_time_label), x, h - 12);
            }
            ctx.textAlign = 'left';

            ctx.fillStyle = '#2563eb'; ctx.font = '700 11.5px Inter, sans-serif';
            ctx.fillText(' Mật độ (xe/km) [Chấm đỏ = Giờ cao điểm]', padL, 18);
            ctx.fillStyle = '#d97706';
            ctx.fillText('--- Vận tốc TB (km/h)', padL + 265, 18);
        }

        function drawM2SpatialChart(pts) {
            const { ctx, w, h } = _prepCanvas('canvas-m2-spatial');
            if (!pts || pts.length === 0) return;
            const padL = 48, padR = 24, padT = 32, padB = 36;
            const pw = w - padL - padR, ph = h - padT - padB;

            const xs = pts.map(p => p.x_coord_m);
            const ys = pts.map(p => p.y_coord_m);
            const minX = Math.min(...xs), maxX = Math.max(...xs, minX + 10);
            const minY = Math.min(...ys), maxY = Math.max(...ys, minY + 10);

            // Lưới Radar tối
            ctx.strokeStyle = 'rgba(148, 163, 184, 0.14)';
            ctx.lineWidth = 1;
            for (let i = 0; i <= 4; i++) {
                const gx = padL + (pw * i) / 4;
                const gy = padT + (ph * i) / 4;
                ctx.beginPath(); ctx.moveTo(gx, padT); ctx.lineTo(gx, padT + ph); ctx.stroke();
                ctx.beginPath(); ctx.moveTo(padL, gy); ctx.lineTo(padL + pw, gy); ctx.stroke();
            }

            pts.forEach(p => {
                const x = padL + ((p.x_coord_m - minX) / (maxX - minX)) * pw;
                const y = padT + ph - ((p.y_coord_m - minY) / (maxY - minY)) * ph;
                if (p.speed_kmh < 14) ctx.fillStyle = 'rgba(248, 113, 113, 0.88)';
                else if (p.speed_kmh < 22) ctx.fillStyle = 'rgba(251, 191, 36, 0.85)';
                else ctx.fillStyle = 'rgba(52, 211, 153, 0.85)';
                ctx.beginPath(); ctx.arc(x, y, 3.6, 0, Math.PI * 2); ctx.fill();
            });

            ctx.fillStyle = '#e2e8f0'; ctx.font = '700 11px Inter, sans-serif';
            ctx.fillText(' Đỏ (<14 km/h: Ùn tắc)    Vàng (14-22 km/h: Đông)    Xanh (>22 km/h: Thông thoáng)', padL, 18);
            ctx.fillStyle = '#94a3b8'; ctx.font = '600 10.5px Inter, sans-serif';
            ctx.fillText(`Không gian UAV: X [${minX.toFixed(0)}m → ${maxX.toFixed(0)}m] × Y [${minY.toFixed(0)}m → ${maxY.toFixed(0)}m]`, padL, h - 10);
        }

        function drawSingleForecastChart(canvasId, series, prefix, colorHex, labelName) {
            const { ctx, w, h } = _prepCanvas(canvasId);
            if (!series || series.length === 0) return;
            const padL = 48, padR = 20, padT = 30, padB = 36;
            const pw = w - padL - padR, ph = h - padT - padB;

            const allVals = [];
            series.forEach(s => {
                allVals.push(s.actual_density, s[prefix + '_predicted'], s[prefix + '_upper_95']);
            });
            const maxY = Math.max(...allVals, 10) * 1.14;

            ctx.strokeStyle = '#f1f5f9';
            for (let i = 0; i <= 4; i++) {
                const y = padT + (ph * i) / 4;
                ctx.beginPath(); ctx.moveTo(padL, y); ctx.lineTo(w - padR, y); ctx.stroke();
                ctx.fillStyle = '#64748b'; ctx.font = '600 11px Inter, sans-serif';
                ctx.fillText(((maxY * (4 - i)) / 4).toFixed(0), 10, y + 4);
            }

            const ciIndices = [];
            series.forEach((s, i) => { if (s.phase_type !== 'Train') ciIndices.push(i); });
            if (ciIndices.length > 0) {
                if (ciIndices[0] > 0) {
                    const splitX = padL + (pw * ciIndices[0]) / Math.max(series.length - 1, 1);
                    ctx.strokeStyle = '#94a3b8'; ctx.setLineDash([4, 4]);
                    ctx.beginPath(); ctx.moveTo(splitX, padT); ctx.lineTo(splitX, padT + ph); ctx.stroke();
                    ctx.setLineDash([]);
                }

                ctx.fillStyle = prefix === 'arima' ? 'rgba(37, 99, 235, 0.16)' : 'rgba(124, 58, 237, 0.16)';
                ctx.beginPath();
                ciIndices.forEach((idx, k) => {
                    const x = padL + (pw * idx) / Math.max(series.length - 1, 1);
                    const y = padT + ph - (series[idx][prefix + '_upper_95'] / maxY) * ph;
                    if (k === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
                });
                for (let k = ciIndices.length - 1; k >= 0; k--) {
                    const idx = ciIndices[k];
                    const x = padL + (pw * idx) / Math.max(series.length - 1, 1);
                    const y = padT + ph - (series[idx][prefix + '_lower_95'] / maxY) * ph;
                    ctx.lineTo(x, y);
                }
                ctx.closePath(); ctx.fill();
            }

            // Đường thực tế / tham chiếu
            ctx.strokeStyle = '#0f172a'; ctx.lineWidth = 2.3;
            ctx.beginPath();
            series.forEach((s, i) => {
                const x = padL + (pw * i) / Math.max(series.length - 1, 1);
                const y = padT + ph - (s.actual_density / maxY) * ph;
                if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
            });
            ctx.stroke();

            // Đường dự báo
            ctx.strokeStyle = colorHex; ctx.lineWidth = 2.6;
            ctx.beginPath();
            series.forEach((s, i) => {
                const x = padL + (pw * i) / Math.max(series.length - 1, 1);
                const y = padT + ph - (s[prefix + '_predicted'] / maxY) * ph;
                if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
            });
            ctx.stroke();

            // Nhãn thời gian trục X
            ctx.fillStyle = '#64748b'; ctx.font = '600 10px Inter, sans-serif';
            const step = Math.max(1, Math.floor(series.length / 5));
            series.forEach((s, i) => {
                if (i % step === 0 || i === series.length - 1) {
                    const x = padL + (pw * i) / Math.max(series.length - 1, 1);
                    ctx.fillText(s.time_label.slice(-11), x - 18, h - 10);
                }
            });

            ctx.fillStyle = '#0f172a'; ctx.font = '700 11.5px Inter, sans-serif';
            ctx.fillText(' Thực tế / Tham chiếu', padL, 18);
            ctx.fillStyle = colorHex;
            ctx.fillText(` Dự báo ${labelName} (Kèm dải CI 95%)`, padL + 165, 18);
        }

        function drawCompareForecastChart(canvasId, series) {
            const { ctx, w, h } = _prepCanvas(canvasId);
            const padL = 50, padR = 24, padT = 30, padB = 36;
            const pw = w - padL - padR, ph = h - padT - padB;
            const maxY = Math.max(...series.map(s => Math.max(s.actual_density, s.arima_predicted, s.prophet_predicted)), 10) * 1.14;

            ctx.strokeStyle = '#f1f5f9';
            for (let i = 0; i <= 4; i++) {
                const y = padT + (ph * i) / 4;
                ctx.beginPath(); ctx.moveTo(padL, y); ctx.lineTo(w - padR, y); ctx.stroke();
                ctx.fillStyle = '#475569'; ctx.font = '600 11px Inter, sans-serif';
                ctx.fillText(((maxY * (4 - i)) / 4).toFixed(0), 10, y + 4);
            }

            const drawCurve = (key, color, dash) => {
                ctx.strokeStyle = color; ctx.lineWidth = 2.6; ctx.setLineDash(dash);
                ctx.beginPath();
                series.forEach((s, i) => {
                    const x = padL + (pw * i) / Math.max(series.length - 1, 1);
                    const y = padT + ph - (s[key] / maxY) * ph;
                    if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
                });
                ctx.stroke();
                ctx.setLineDash([]);
            };

            drawCurve('actual_density', '#0f172a', []);
            drawCurve('arima_predicted', '#2563eb', [6, 3]);
            drawCurve('prophet_predicted', '#7c3aed', [3, 3]);

            ctx.font = '700 11.5px Inter, sans-serif';
            ctx.fillStyle = '#0f172a'; ctx.fillText(' Thực tế / Tham chiếu', padL, 18);
            ctx.fillStyle = '#2563eb'; ctx.fillText('--- Dự báo ARIMA', padL + 160, 18);
            ctx.fillStyle = '#7c3aed'; ctx.fillText('⋯⋯ Dự báo Prophet', padL + 295, 18);
        }

        function drawM4Heatmap(canvasId, hm) {
            const { ctx, w, h } = _prepCanvas(canvasId);
            if (!hm || !hm.zones || hm.zones.length === 0) return;
            const padL = 165, padR = 16, padT = 24, padB = 46;
            const pw = w - padL - padR, ph = h - padT - padB;
            const nZ = hm.zones.length, nT = hm.timeframes.length;
            const cellW = pw / Math.max(nT, 1), cellH = ph / Math.max(nZ, 1);

            const flat = hm.values.flat();
            const maxV = Math.max(...flat, 1);

            for (let r = 0; r < nZ; r++) {
                ctx.textAlign = 'left';
                ctx.fillStyle = '#1e293b'; ctx.font = '700 11px Inter, sans-serif';
                ctx.fillText(hm.zones[r].slice(0, 23), 6, padT + r * cellH + cellH / 2 + 4);
                for (let c = 0; c < nT; c++) {
                    const val = hm.values[r][c];
                    const ratio = Math.min(1, val / maxV);
                    const red = Math.round(239 + ratio * 16);
                    const green = Math.round(246 - ratio * 185);
                    const blue = Math.round(255 - ratio * 210);
                    ctx.fillStyle = `rgb(${red},${green},${blue})`;
                    ctx.fillRect(padL + c * cellW + 2, padT + r * cellH + 2, cellW - 4, cellH - 4);
                    ctx.fillStyle = ratio > 0.62 ? '#ffffff' : '#0f172a';
                    ctx.font = `800 ${Math.min(11, Math.max(8, cellW * 0.36))}px Inter, sans-serif`;
                    ctx.textAlign = 'center';
                    ctx.fillText(
                        cellW < 36 ? val.toFixed(0) : val.toFixed(1),
                        padL + c * cellW + cellW / 2,
                        padT + r * cellH + cellH / 2 + 4
                    );
                }
            }
            ctx.fillStyle = '#475569'; ctx.font = '600 10px Inter, sans-serif';
            ctx.textAlign = 'center';
            const labelStep = Math.max(1, Math.ceil(40 / cellW));
            for (let c = 0; c < nT; c += labelStep) {
                ctx.fillText(shortTimeLabel(hm.timeframes[c]), padL + c * cellW + cellW / 2, h - 14);
            }
            ctx.textAlign = 'left';
        }

        function drawM4MultiLine(canvasId, labels, zonesSeries, fieldName, unitLabel) {
            const { ctx, w, h } = _prepCanvas(canvasId);
            if (!zonesSeries || zonesSeries.length === 0) return;
            const padL = 50, padR = 18, padT = 32, padB = 34;
            const pw = w - padL - padR, ph = h - padT - padB;

            let maxY = 10;
            zonesSeries.forEach(zs => {
                zs[fieldName].forEach(v => { if (v > maxY) maxY = v; });
            });
            maxY *= 1.14;

            ctx.strokeStyle = '#f1f5f9';
            for (let i = 0; i <= 4; i++) {
                const y = padT + (ph * i) / 4;
                ctx.beginPath(); ctx.moveTo(padL, y); ctx.lineTo(w - padR, y); ctx.stroke();
                ctx.fillStyle = '#64748b'; ctx.font = '600 10.5px Inter, sans-serif';
                ctx.fillText(((maxY * (4 - i)) / 4).toFixed(0), 8, y + 4);
            }

            zonesSeries.forEach((zs, zIdx) => {
                const color = PALETTE[zIdx % PALETTE.length];
                ctx.strokeStyle = color; ctx.lineWidth = 2.3;
                ctx.beginPath();
                zs[fieldName].forEach((val, i) => {
                    const x = padL + (pw * i) / Math.max(labels.length - 1, 1);
                    const y = padT + ph - (val / maxY) * ph;
                    if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
                });
                ctx.stroke();

                ctx.fillStyle = color; ctx.font = '700 10.5px Inter, sans-serif';
                ctx.fillText(' ' + zs.zone_name.slice(0, 15), padL + zIdx * 116, 17);
            });
        }

        function drawM4Histogram(canvasId, hist) {
            const { ctx, w, h } = _prepCanvas(canvasId);
            if (!hist || !hist.counts) return;
            const padL = 46, padR = 18, padT = 26, padB = 40;
            const pw = w - padL - padR, ph = h - padT - padB;
            const maxC = Math.max(...hist.counts, 1) * 1.15;
            const barW = pw / hist.counts.length;

            hist.counts.forEach((cnt, i) => {
                const bh = (cnt / maxC) * ph;
                const x = padL + i * barW + 5;
                const y = padT + ph - bh;
                const grad = ctx.createLinearGradient(0, y, 0, padT + ph);
                grad.addColorStop(0, '#0d9488');
                grad.addColorStop(1, '#14b8a6');
                ctx.fillStyle = grad;
                ctx.fillRect(x, y, barW - 10, bh);
                ctx.fillStyle = '#0f172a'; ctx.font = '700 10px Inter, sans-serif';
                ctx.fillText(cnt, x + 4, y - 5);
                ctx.fillStyle = '#475569'; ctx.font = '600 10px Inter, sans-serif';
                ctx.fillText(hist.bin_labels[i].replace(' km/h', ''), x + 2, h - 14);
            });
        }

        function drawM4ForecastBars(canvasId, fcList) {
            const { ctx, w, h } = _prepCanvas(canvasId);
            if (!fcList || !fcList.length) return;
            const padL = 46, padR = 18, padT = 30, padB = 40;
            const pw = w - padL - padR, ph = h - padT - padB;
            const maxR = Math.max(...fcList.map(f => Math.max(f.arima_rmse, f.prophet_rmse)), 1) * 1.2;
            const grpW = pw / fcList.length;

            fcList.forEach((f, i) => {
                const x0 = padL + i * grpW + 10;
                const bw = Math.min(28, (grpW - 24) / 2);
                const hA = (f.arima_rmse / maxR) * ph;
                const hP = (f.prophet_rmse / maxR) * ph;

                ctx.fillStyle = '#2563eb';
                ctx.fillRect(x0, padT + ph - hA, bw, hA);
                ctx.fillStyle = '#7c3aed';
                ctx.fillRect(x0 + bw + 4, padT + ph - hP, bw, hP);

                ctx.fillStyle = '#1e293b'; ctx.font = '600 10px Inter, sans-serif';
                ctx.fillText(f.zone_name.slice(0, 14), x0 - 2, h - 14);
            });
            ctx.fillStyle = '#2563eb'; ctx.font = '700 11.5px Inter, sans-serif';
            ctx.fillText(' ARIMA RMSE (xe/km)', padL, 18);
            ctx.fillStyle = '#7c3aed';
            ctx.fillText(' Prophet RMSE (xe/km)', padL + 165, 18);
        }

        window.addEventListener('resize', () => {
            if (CURRENT_MODULE === 2) renderModule2();
            if (CURRENT_MODULE === 3) renderModule3();
            if (CURRENT_MODULE === 4) renderModule4();
            if (CURRENT_MODULE === 5) renderModule5();
        });

        // Khởi tạo từ dữ liệu bền vững; không gửi lệnh xóa Database khi mở trang.
        APP_STATE = { has_data: false };
        updateHeaderAndM1Table();
        fetch('/api/state')
            .then(response => response.json())
            .then(async bundle => {
                APP_STATE = bundle;
                updateHeaderAndM1Table();
                await loadModuleDatasetOptions();
                loadDatasetLibrary(1);
            })
            .catch(error => {
                showBanner(`Không tải được trạng thái Database: ${error.message}`, 'deleted');
            });
    