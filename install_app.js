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
    // Fetch data from authenticated API instead of static file
    fetch('/api/data')
        .then(function(r) {
            if (r.status === 401) {
                window.location.href = '/login.html';
                throw new Error('Not authenticated');
            }
            if (!r.ok) throw new Error('Network error');
            return r.json();
        })
        .then(function(dashboardData) {
            if (!dashboardData.installation_orders) {
                console.error("Installation data not found!");
                return;
            }
            renderInstallDashboard(dashboardData.installation_orders);
        })
        .catch(function(err) {
            if (err.message !== 'Not authenticated') {
                console.error("Lỗi tải dữ liệu:", err);
            }
        });
});

function renderInstallDashboard(data) {
    var successCount = data.success.length;
    var pendingCount = data.pending.length;
    var errorCount = data.discrepancy.length;
    var total = successCount + pendingCount + errorCount;

    document.getElementById('kpi-total').innerText = total;
    document.getElementById('kpi-success').innerText = successCount;
    document.getElementById('kpi-pending').innerText = pendingCount;
    document.getElementById('kpi-error').innerText = errorCount;

    var ctx = document.getElementById('statusChart').getContext('2d');
    new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: ['Đã hoàn tất', 'Cần xử lý', 'Sai lệch'],
            datasets: [{
                data: [successCount, pendingCount, errorCount],
                backgroundColor: [
                    'rgba(16, 185, 129, 0.8)',
                    'rgba(245, 158, 11, 0.8)',
                    'rgba(239, 68, 68, 0.8)'
                ],
                borderWidth: 0
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { position: 'bottom', labels: { color: '#94a3b8' } } },
            cutout: '70%'
        }
    });

    var tbody = document.querySelector('#installTable tbody');
    var allOrders = [].concat(
        data.success.map(function(o) { return Object.assign({}, o, {type: 'success'}); }),
        data.pending.map(function(o) { return Object.assign({}, o, {type: 'pending'}); }),
        data.discrepancy.map(function(o) { return Object.assign({}, o, {type: 'error'}); })
    );

    allOrders.forEach(function(order) {
        var tr = document.createElement('tr');
        var badgeClass = order.type === 'success' ? 'badge-success'
                       : order.type === 'pending' ? 'badge-warning'
                       : 'badge-error';

        // Safe DOM construction — no innerHTML with user data
        var td1 = document.createElement('td');
        td1.style.fontFamily = 'monospace';
        td1.style.fontWeight = '600';
        td1.textContent = order.order_code;

        var td2 = document.createElement('td');
        td2.textContent = order.warehouse.replace('Kho Giao Hàng Nặng - ', '').replace(' - Hà Nội', '');

        var td3 = document.createElement('td');
        var badge = document.createElement('span');
        badge.className = 'badge ' + badgeClass;
        badge.textContent = order.status;
        td3.appendChild(badge);

        var td4 = document.createElement('td');
        td4.style.color = 'var(--text-secondary)';
        td4.textContent = order.install_type;

        tr.append(td1, td2, td3, td4);
        tbody.appendChild(tr);
    });
}
