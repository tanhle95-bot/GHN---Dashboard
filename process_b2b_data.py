import csv
import json
import os
from collections import defaultdict

input_csv = '/Users/lenhutanh/.gemini/antigravity/scratch/filtered_b2b_orders.csv'
output_js = '/Users/lenhutanh/.gemini/antigravity/scratch/ghn-dashboard/b2b_data.js'

data = {
    'total': 0,
    'by_client': defaultdict(int),
    'by_warehouse': defaultdict(int),
    'orders': []
}

with open(input_csv, mode='r', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    for row in reader:
        data['total'] += 1
        
        # Normalize client names
        client = row['Khách'].strip()
        if 'aqua' in client.lower():
            client = 'Aqua B2C'
        elif 'anta' in client.lower():
            client = 'ANTA'
        elif 'con cưng' in client.lower():
            client = 'Con Cưng'
            
        data['by_client'][client] += 1
        
        warehouse = row['Kho hiện tại'].replace('Kho Giao Hàng Nặng - ', '').replace(' - Hà Nội', '')
        data['by_warehouse'][warehouse] += 1
        
        data['orders'].append({
            'priority': row['Mức độ ưu tiên'],
            'warehouse': warehouse,
            'pic': row['PIC'],
            'order_code': row['Order code'],
            'action': row['Cần làm gì'],
            'client': client,
            'address': row['Địa chỉ giao'],
            'inbound_date': row['Ngày nhập kho'],
            'storage_days': row['Đã lưu kho (ngày)'],
            'appointment_flag': row['flag_hẹn_giờ_giao']
        })

# Sort warehouse counts
sorted_warehouse = [{'warehouse': k, 'count': v} for k, v in sorted(data['by_warehouse'].items(), key=lambda item: item[1], reverse=True)]
data['by_warehouse'] = sorted_warehouse

# Sort orders by storage days descending (assuming int, handle empty)
data['orders'].sort(key=lambda x: int(x['storage_days']) if x['storage_days'].isdigit() else 0, reverse=True)

with open(output_js, mode='w', encoding='utf-8') as f:
    f.write(f"const b2bData = {json.dumps(data, ensure_ascii=False, indent=2)};\n")

print(f"Processed {data['total']} orders. Output saved to {output_js}")
