// === Security Helper ===
function escapeHTML(str) {
    if (str == null) return '';
    return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}

document.addEventListener("DOMContentLoaded", function() {
    // Fetch B2B data from authenticated API instead of static file
    authFetch('/api/b2b-data')
        .then(function(r) {
            if (r.status === 401) {
                window.location.href = '/login.html';
                throw new Error('Not authenticated');
            }
            if (!r.ok) throw new Error('Network error');
            return r.json();
        })
        .then(function(b2bData) {
            renderB2BDashboard(b2bData);
        })
        .catch(function(err) {
            if (err.message !== 'Not authenticated') {
                console.error("Lỗi tải dữ liệu B2B:", err);
            }
        });
});

function renderB2BDashboard(b2bData) {
    // 1. Populate KPIs (safe — using textContent via innerText)
    document.getElementById('kpi-total').innerText = b2bData.total;
    document.getElementById('kpi-concung').innerText = b2bData.by_client['Con Cưng'] || 0;
    document.getElementById('kpi-anta').innerText = b2bData.by_client['ANTA'] || 0;
    document.getElementById('kpi-aqua').innerText = b2bData.by_client['Aqua B2C'] || 0;

    // 2. Client Chart (Doughnut)
    var ctxClient = document.getElementById('clientChart').getContext('2d');
    new Chart(ctxClient, {
        type: 'doughnut',
        data: {
            labels: ['Con Cưng', 'ANTA', 'Aqua B2C'],
            datasets: [{
                data: [
                    b2bData.by_client['Con Cưng'] || 0,
                    b2bData.by_client['ANTA'] || 0,
                    b2bData.by_client['Aqua B2C'] || 0
                ],
                backgroundColor: [
                    'rgba(236, 72, 153, 0.8)',
                    'rgba(16, 185, 129, 0.8)',
                    'rgba(6, 182, 212, 0.8)'
                ],
                borderWidth: 0,
                hoverOffset: 4
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { position: 'bottom', labels: { color: '#94a3b8' } }
            },
            cutout: '70%'
        }
    });

    // 3. Warehouse Chart (Bar)
    var topWarehouses = b2bData.by_warehouse.slice(0, 10);
    var ctxWH = document.getElementById('warehouseChart').getContext('2d');
    new Chart(ctxWH, {
        type: 'bar',
        data: {
            labels: topWarehouses.map(function(w) { return w.warehouse; }),
            datasets: [{
                label: 'Số đơn',
                data: topWarehouses.map(function(w) { return w.count; }),
                backgroundColor: 'rgba(139, 92, 246, 0.7)',
                borderRadius: 6,
                borderWidth: 0
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { display: false } },
            scales: {
                x: { ticks: { color: '#94a3b8', font: { size: 10 } }, grid: { display: false } },
                y: { ticks: { color: '#94a3b8' }, grid: { color: 'rgba(255,255,255,0.05)' } }
            }
        }
    });

    // 4. Populate Table — Safe DOM construction (no innerHTML with user data)
    var tbody = document.querySelector('#ordersTable tbody');
    b2bData.orders.forEach(function(order) {
        var tr = document.createElement('tr');

        var brandClass = '';
        if (order.client.includes('Con')) brandClass = 'brand-Con';
        else if (order.client.includes('ANTA')) brandClass = 'brand-ANTA';
        else if (order.client.includes('Aqua')) brandClass = 'brand-Aqua';

        var td1 = document.createElement('td');
        td1.style.fontFamily = 'monospace';
        td1.style.fontWeight = '600';
        td1.textContent = order.order_code;

        var td2 = document.createElement('td');
        var badge = document.createElement('span');
        badge.className = 'badge ' + escapeHTML(brandClass);
        badge.textContent = order.client;
        td2.appendChild(badge);

        var td3 = document.createElement('td');
        td3.textContent = order.warehouse;

        var td4 = document.createElement('td');
        td4.textContent = order.pic;

        var td5 = document.createElement('td');
        td5.style.color = 'var(--warning)';
        td5.textContent = order.priority.split(':')[0] || order.priority;

        var td6 = document.createElement('td');
        var strongDays = document.createElement('strong');
        strongDays.textContent = order.storage_days;
        td6.appendChild(strongDays);
        td6.appendChild(document.createTextNode(' ngày'));

        tr.append(td1, td2, td3, td4, td5, td6);
        tbody.appendChild(tr);
    });
}
