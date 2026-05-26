import pandas as pd
import urllib.request
import io
import json

URL = "https://docs.google.com/spreadsheets/d/1Kjqwt6MIghCzfCSifVrpIpVHbC0o77lxMVVFlCZ26xY/export?format=xlsx"
req = urllib.request.Request(URL, headers={"User-Agent": "Mozilla/5.0"})
response = urllib.request.urlopen(req)
excel_data = io.BytesIO(response.read())

df_install = pd.read_excel(excel_data, sheet_name="5. DS đơn Lắp đặt")
print(list(df_install.columns))
