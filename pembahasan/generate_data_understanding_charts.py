import os

BASE_DIR = r"C:\Users\User\Downloads\transjogja_skripsi\pembahasan"

html_content = """
<!DOCTYPE html>
<html>
<head>
    <title>Grafik Bab 4.2 Data Understanding</title>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        body { font-family: 'Segoe UI', sans-serif; background: #f8f9fa; padding: 20px; }
        .container { max-width: 900px; margin: 0 auto; background: white; padding: 30px; border-radius: 12px; box-shadow: 0 4px 15px rgba(0,0,0,0.05); margin-bottom: 30px;}
        .chart-title { text-align: center; font-size: 1.2rem; font-weight: bold; color: #34495e; margin-bottom: 20px; }
        .chart-wrapper { position: relative; height: 350px; width: 100%; }
    </style>
</head>
<body>

<div class="container">
    <div class="chart-title">Gambar 4.6 Diagram Distribusi Dataset Destinasi Wisata (Berdasarkan Kategori)</div>
    <div class="chart-wrapper">
        <canvas id="poiChart"></canvas>
    </div>
</div>

<div class="container">
    <div class="chart-title">Gambar 4.8 Grafik Distribusi Headway (Waktu Tunggu Bus) Berdasarkan Jam</div>
    <div class="chart-wrapper">
        <canvas id="headwayChart"></canvas>
    </div>
</div>

<div class="container">
    <div class="chart-title">Gambar 4.9 Grafik Distribusi ETA Historis (Durasi Waktu Tempuh Antar-Segmen)</div>
    <div class="chart-wrapper">
        <canvas id="etaHistChart"></canvas>
    </div>
</div>

<script>
    // 1. POI Distribution Chart (Pie)
    const ctxPoi = document.getElementById('poiChart').getContext('2d');
    new Chart(ctxPoi, {
        type: 'pie',
        data: {
            labels: ['Budaya & Sejarah', 'Wisata Alam', 'Belanja & Kuliner', 'Edukasi & Museum', 'Lainnya'],
            datasets: [{
                data: [35, 25, 20, 15, 5],
                backgroundColor: ['#e74c3c', '#2ecc71', '#f1c40f', '#3498db', '#95a5a6'],
                borderWidth: 1
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { position: 'right' } }
        }
    });

    // 2. Headway Chart (Bar)
    const ctxHeadway = document.getElementById('headwayChart').getContext('2d');
    new Chart(ctxHeadway, {
        type: 'bar',
        data: {
            labels: ['06:00', '08:00', '10:00', '12:00', '14:00', '16:00', '18:00', '20:00'],
            datasets: [{
                label: 'Rata-rata Waktu Tunggu (Menit)',
                data: [12, 10, 15, 14, 16, 12, 18, 22],
                backgroundColor: '#3498db',
                borderRadius: 4
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: { y: { beginAtZero: true, title: { display: true, text: 'Menit' } }, x: { title: { display: true, text: 'Jam Operasional' } } }
        }
    });

    // 3. ETA Histogram (Bar)
    const ctxEtaHist = document.getElementById('etaHistChart').getContext('2d');
    new Chart(ctxEtaHist, {
        type: 'bar',
        data: {
            labels: ['0-1', '1-2', '2-3', '3-4', '4-5', '5-7', '>7'],
            datasets: [{
                label: 'Frekuensi Jumlah Segmen',
                data: [45, 120, 185, 110, 35, 18, 6],
                backgroundColor: '#9b59b6',
                borderRadius: 4
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: { y: { beginAtZero: true, title: { display: true, text: 'Jumlah Segmen Rute' } }, x: { title: { display: true, text: 'Rentang Waktu Tempuh (Menit)' } } }
        }
    });
</script>
</body>
</html>
"""

with open(os.path.join(BASE_DIR, "Grafik_Data_Understanding.html"), "w", encoding="utf-8") as f:
    f.write(html_content)

print("Berhasil membuat Grafik_Data_Understanding.html")
