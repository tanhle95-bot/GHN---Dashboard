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

let gtcChartInstance = null;

async function fetchData() {
    const refreshBtn = document.getElementById('refresh-btn');
    refreshBtn.style.opacity = '0.5';
    
    try {
        const response = await fetch('/api/data', { credentials: 'include' });
        if (response.status === 401) {
            window.location.href = '/login.html';
            return;
        }
        if (!response.ok) throw new Error('Network response was not ok');
        const data = await response.json();
        
        // Update Time
        document.getElementById('update-time').innerText = new Date().toLocaleString('vi-VN');
        
        // Update KPI Cards
        if (document.getElementById('overall-gtc-ratio')) {
            document.getElementById('overall-gtc-ratio').innerText = data.overall_gtc.toFixed(2) + '%';
        }
        
        if (document.getElementById('overall-gtc-total')) {
            let totalAssigned = 0;
            let totalSuccess = 0;
            data.gtc_ratio.forEach(d => {
                totalAssigned += d.total_assigned;
                totalSuccess += d.total_success;
            });
            document.getElementById('overall-gtc-total').innerText = totalAssigned.toLocaleString('vi-VN');
            document.getElementById('overall-gtc-success').innerText = totalSuccess.toLocaleString('vi-VN');
        }
        
        renderGtcChart(data.gtc_ratio);
        renderDelayedTable(data.delayed_orders);
        renderB2bTable(data.b2b_orders);
        renderInstallationStats(data.installation_orders);
        
    } catch (error) {
        console.error('Lỗi khi tải dữ liệu:', error);
        alert('Không thể tải dữ liệu mới. Vui lòng thử lại sau.');
    } finally {
        refreshBtn.style.opacity = '1';
    }
}

function renderGtcChart(data) {
    const ctx = document.getElementById('gtcChart').getContext('2d');
    
    const labels = data.map(d => d.warehouse_name
        .replace('Kho Giao Hàng Nặng - ', '')
        .replace('Kho Chuyển Tiếp ', 'CT ')
        .replace(' - Hà Nội', '')
        .replace('-Hà Nội', '')
    );
    const values = data.map(d => d.gtc_ratio.toFixed(2));
    
    if (gtcChartInstance) {
        gtcChartInstance.destroy();
    }
    
    gtcChartInstance = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [{
                label: 'Tỷ lệ GTC (%)',
                data: values,
                backgroundColor: 'rgba(59, 130, 246, 0.7)',
                borderColor: 'rgba(59, 130, 246, 1)',
                borderWidth: 1,
                borderRadius: 4
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                y: {
                    beginAtZero: true,
                    grid: { color: 'rgba(255, 255, 255, 0.05)' },
                    ticks: { color: '#94a3b8' }
                },
                x: {
                    grid: { display: false },
                    ticks: { color: '#94a3b8' }
                }
            },
            plugins: {
                legend: { display: false }
            }
        }
    });
}

function renderDelayedTable(data) {
    const tbody = document.querySelector('#delayed-table tbody');
    tbody.innerHTML = '';
    
    data.forEach(row => {
        const tr = document.createElement('tr');
        const shortName = row.warehouse.replace('Kho Giao Hàng Nặng - ', '');
        const badgeClass = row.status.split(' ')[0];
        
        // Safe DOM construction — no innerHTML with user data
        const td1 = document.createElement('td');
        td1.textContent = shortName;
        
        const td2 = document.createElement('td');
        td2.textContent = row.total_3d;
        
        const td3 = document.createElement('td');
        const strong = document.createElement('strong');
        strong.textContent = row.over_7d;
        td3.appendChild(strong);
        
        const td4 = document.createElement('td');
        const badge = document.createElement('span');
        badge.className = 'badge ' + escapeHTML(badgeClass);
        badge.textContent = row.status;
        td4.appendChild(badge);
        
        tr.append(td1, td2, td3, td4);
        tbody.appendChild(tr);
    });
}

function renderB2bTable(data) {
    const tbody = document.querySelector('#b2b-table tbody');
    tbody.innerHTML = '';
    
    data.forEach(row => {
        const tr = document.createElement('tr');
        const shortName = row.warehouse.replace('Kho Giao Hàng Nặng - ', '');
        
        // Safe DOM construction
        const td1 = document.createElement('td');
        td1.textContent = shortName;
        
        const td2 = document.createElement('td');
        td2.textContent = row['1: trong hôm nay'] || 0;
        
        const td3 = document.createElement('td');
        td3.textContent = row['2: trong ngày mai'] || 0;
        
        const td4 = document.createElement('td');
        td4.textContent = row['3: trong ngày mốt'] || 0;
        
        tr.append(td1, td2, td3, td4);
        tbody.appendChild(tr);
    });
}

function renderInstallationStats(data) {
    const successCount = data.success.length;
    const pendingCount = data.pending.length;
    const discrepancyCount = data.discrepancy.length;
    const total = successCount + pendingCount + discrepancyCount;

    const elTotal = document.getElementById('install-total');
    if(elTotal) elTotal.innerText = total;
    
    document.getElementById('install-success').innerText = successCount;
    document.getElementById('install-pending').innerText = pendingCount;
    document.getElementById('install-discrepancy').innerText = discrepancyCount;
    
    const tbody = document.querySelector('#install-full-table tbody');
    if (!tbody) return;
    tbody.innerHTML = '';
    
    const allOrders = [
        ...data.success.map(o => ({...o, type: 'success'})),
        ...data.pending.map(o => ({...o, type: 'pending'})),
        ...data.discrepancy.map(o => ({...o, type: 'error'}))
    ];

    allOrders.forEach(item => {
        const tr = document.createElement('tr');
        const badgeClass = item.type === 'success' ? 'success' : item.type === 'pending' ? 'warning' : 'error';
        const shortWH = item.warehouse.replace('Kho Giao Hàng Nặng - ', '').replace(' - Hà Nội', '');
        
        // Safe DOM construction
        const td1 = document.createElement('td');
        td1.style.fontFamily = 'monospace';
        td1.style.fontWeight = '600';
        td1.textContent = item.order_code;
        
        const td2 = document.createElement('td');
        td2.textContent = shortWH;
        
        const td3 = document.createElement('td');
        const div3a = document.createElement('div');
        div3a.style.fontWeight = '500';
        div3a.style.marginBottom = '4px';
        div3a.textContent = item.product_type || 'N/A';
        const div3b = document.createElement('div');
        div3b.style.fontSize = '0.8em';
        div3b.style.color = 'var(--text-secondary)';
        div3b.textContent = item.province || 'N/A';
        td3.append(div3a, div3b);
        
        const td4 = document.createElement('td');
        const badge = document.createElement('span');
        badge.className = 'badge ' + badgeClass;
        badge.textContent = item.status;
        td4.appendChild(badge);
        
        const td5 = document.createElement('td');
        const div5a = document.createElement('div');
        div5a.style.marginBottom = '4px';
        div5a.style.color = 'var(--text-secondary)';
        div5a.textContent = item.install_type;
        td5.appendChild(div5a);
        if (item.buyer_agreed) {
            const div5b = document.createElement('div');
            div5b.style.fontSize = '0.8em';
            div5b.style.color = 'var(--accent-blue)';
            div5b.textContent = 'Thỏa thuận: ' + item.buyer_agreed;
            td5.appendChild(div5b);
        }
        
        tr.append(td1, td2, td3, td4, td5);
        tbody.appendChild(tr);
    });
}

// Initial fetch — use addEventListener instead of inline onclick
document.addEventListener('DOMContentLoaded', function() {
    document.getElementById('refresh-btn').addEventListener('click', fetchData);
    fetchData();
});
