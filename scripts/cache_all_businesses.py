import sys
import io
import os
import time
from datamate.data.loader import BusinessDataLoader

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

data_dir = "data/public_test/data"
businesses = sorted([d for d in os.listdir(data_dir) if os.path.isdir(os.path.join(data_dir, d)) and not d.startswith(".")])

print(f"Pre-caching {len(businesses)} businesses in {data_dir}...")
t_total = time.time()

for idx, biz_id in enumerate(businesses, start=1):
    t0 = time.time()
    biz_path = os.path.join(data_dir, biz_id)
    loader = BusinessDataLoader(biz_path).load()
    elapsed = time.time() - t0
    print(f"[{idx}/{len(businesses)}] {biz_id}: {len(loader.table_names)} tables cached in {elapsed:.2f}s", flush=True)

print(f"All {len(businesses)} businesses successfully pre-cached in {time.time() - t_total:.2f}s!")
