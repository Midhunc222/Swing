import pandas as pd
import urllib.request
import json

url = "https://archives.nseindia.com/content/indices/ind_nifty500list.csv"
req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
try:
    with urllib.request.urlopen(req) as response:
        df = pd.read_csv(response)
        symbols = df['Symbol'].tolist()
        ns_symbols = [f"{sym}.NS" for sym in symbols]
        
        with open('tickers.py', 'w') as f:
            f.write("NIFTY_500_TICKERS = [\n")
            # Write in chunks of 5 for readability
            for i in range(0, len(ns_symbols), 5):
                chunk = ns_symbols[i:i+5]
                line = "    " + ", ".join([f'"{s}"' for s in chunk]) + ",\n"
                f.write(line)
            f.write("]\n")
        print("Success! Downloaded Nifty 500.")
except Exception as e:
    print("Error:", e)
