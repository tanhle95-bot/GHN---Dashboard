let gtcChartInstance = null;

async function fetchData() {
    const refreshBtn = document.getElementById('refresh-btn');
    refreshBtn.style.opacity = '0.5';
    
    try {
        const response = await fetch('/api/data');
        if (!response.ok) throw new Error('Network response was not ok');
        const data = await response.json();
        
        // Update Time
        document.getElementById('update-time').innerText = new Date().toLocaleString('vi-VN');
        
        renderGtcChart(data.gtc_ratio);
        renderDelayedTable(data.delayed_orders);
        renderB2bTable(data.b2b_orders);
        renderInstallationStats(data.installation_orders);
        
    } catch (error) {
        console.error('Lỗi khi tải dữ liệu:', error);
        alert('Không thể tải dữ liệu mới. Hãy chạy fetch_data.py để tải lại.');
    } finally {
        refreshBtn.style.opacity = '1';
    }
}

function renderGtcChart(data) {
    const ctx = document.getElementById('gtcChart').getContext('2d');
    
    const labels = data.map(d => d.warehouse_name.replace('Kho Giao Hàng Nặng - ', '').replace(' - Hà Nội', ''));
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
        // clean warehouse name
        const shortName = row.warehouse.replace('Kho Giao Hàng Nặng - ', '');
        const badgeClass = row.status.split(' ')[0]; // Cảnh, Cần, Bình
        
        tr.innerHTML = `
            <td>${shortName}</td>
            <td>${row.total_3d}</td>
            <td><strong>${row.over_7d}</strong></td>
            <td><span class="badge ${badgeClass}">${row.status}</span></td>
        `;
        tbody.appendChild(tr);
    });
}

function renderB2bTable(data) {
    const tbody = document.querySelector('#b2b-table tbody');
    tbody.innerHTML = '';
    
    data.forEach(row => {
        const tr = document.createElement('tr');
        const shortName = row.warehouse.replace('Kho Giao Hàng Nặng - ', '');
        tr.innerHTML = `
            <td>${shortName}</td>
            <td>${row['1: trong hôm nay'] || 0}</td>
            <td>${row['2: trong ngày mai'] || 0}</td>
            <td>${row['3: trong ngày mốt'] || 0}</td>
        `;
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
        
        tr.innerHTML = `
            <td style="font-family: monospace; font-weight: 600;">${item.order_code}</td>
            <td>${shortWH}</td>
            <td>
                <div style="font-weight: 500; margin-bottom: 4px;">${item.product_type || 'N/A'}</div>
                <div style="font-size: 0.8em; color: var(--text-secondary);">${item.province || 'N/A'}</div>
            </td>
            <td><span class="badge ${badgeClass}">${item.status}</span></td>
            <td>
                <div style="margin-bottom: 4px; color: var(--text-secondary);">${item.install_type}</div>
                ${item.buyer_agreed ? `<div style="font-size: 0.8em; color: var(--accent-blue);">Thỏa thuận: ${item.buyer_agreed}</div>` : ''}
            </td>
        `;
        tbody.appendChild(tr);
    });
}

// Initial fetch
document.addEventListener('DOMContentLoaded', fetchData);
