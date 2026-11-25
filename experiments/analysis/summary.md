# Ket qua thuc nghiem: baseline-1kb

- May: `Windows-11-10.0.26200-SP0`
- CPU logic: 24
- Python: 3.13.1
- Payload: 1024 B, warm-up 5s, do 20s, 3 lan lap/muc
- Mo hinh Server: blocking socket + moi ket noi mot thread

## Bang 1. Tong hop theo muc Client (trung binh +/- do lech chuan)

| Client | Lan chay | Latency TB (ms) | p95 (ms) | p99 (ms) | Throughput (req/s) | CPU server (%) | Error rate |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 3 | 0.064 ± 0.004 | 0.141 ± 0.011 | 0.256 ± 0.007 | 15058 ± 945 | 53.2 ± 1.7 | 0.0000% |
| 10 | 3 | 0.279 ± 0.026 | 0.523 ± 0.065 | 0.756 ± 0.159 | 35609 ± 3239 | 161.9 ± 6.9 | 0.0000% |
| 50 | 3 | 1.540 ± 0.088 | 3.187 ± 0.238 | 4.683 ± 0.484 | 32468 ± 1922 | 162.1 ± 6.9 | 0.0000% |

> CPU (%) la % tren MOT core (cach tinh cua psutil): 200% = 2 core chay het suc. Cot cpu_norm_avg trong aggregate.csv la % so voi toan bo may.

## Bang 2. Muc tang so voi 1 Client

| Client | Latency TB | p95 | Throughput | CPU |
|---:|---:|---:|---:|---:|
| 1 | 1.00x | 1.00x | 1.00x | 1.00x |
| 10 | 4.39x | 3.70x | 2.36x | 3.05x |
| 50 | 24.20x | 22.58x | 2.16x | 3.05x |

## Bang 3. Chi tiet tung lan chay

| run_id | Client | Lan | OK | Loi | Latency TB (ms) | p95 (ms) | req/s | CPU (%) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| c1_r1 | 1 | 1 | 280735 | 0 | 0.068 | 0.151 | 14037 | 51.3 |
| c1_r2 | 1 | 2 | 304721 | 0 | 0.063 | 0.142 | 15236 | 54.5 |
| c1_r3 | 1 | 3 | 318032 | 0 | 0.060 | 0.130 | 15902 | 53.7 |
| c10_r1 | 10 | 1 | 642112 | 0 | 0.308 | 0.595 | 32106 | 155.9 |
| c10_r2 | 10 | 2 | 724533 | 0 | 0.273 | 0.506 | 36227 | 169.5 |
| c10_r3 | 10 | 3 | 769912 | 0 | 0.257 | 0.468 | 38496 | 160.4 |
| c50_r1 | 50 | 1 | 633223 | 0 | 1.576 | 3.311 | 31661 | 158.6 |
| c50_r2 | 50 | 2 | 621619 | 0 | 1.605 | 3.338 | 31081 | 157.7 |
| c50_r3 | 50 | 3 | 693228 | 0 | 1.439 | 2.912 | 34661 | 170.1 |
