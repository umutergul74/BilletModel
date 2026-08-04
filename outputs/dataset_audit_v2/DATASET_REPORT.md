# Güncel veri seti raporu — v2

Aktif veri sürümü: `steel_billet_local_2026-07-31_v2`  
Aktif annotation sürümü: `cvat_task_2_2026-07-31_owner_accepted`  
Rastgelelik tohumu: `20260731`

## Güncel durum

- Çalışma klasöründe 662 görüntü var; tamamı başarıyla okunuyor.
- 623 görüntü 3000×4000, 21 görüntü 3060×4080, 12 görüntü 6120×8160; altı görüntü farklı/kırpılmış boyutlarda.
- SHA-256 ile birebir aynı görüntü bulunmadı.
- Algısal hash eşiği 6 ile 281 çok benzer görüntü çifti tespit edildi.
- Zaman dizisi ve görsel benzerlik birlikte kullanılarak 41 sahne/çekim grubu oluşturuldu.
- 70 CVAT görüntüsünün tamamı etiketli ve toplam 976 kabul edilmiş polygon içeriyor.
- Yerelde mevcut 65 etiketli görüntüde 912 eğitimde kullanılabilir instance var.
- Yerelde bulunmayan 5 etiketli görüntü eğitim manifestosuna alınmadı.

## Sahne güvenli split

| Split | Görüntü | Instance | Sahne grubu |
|---|---:|---:|---:|
| Train | 45 | 628 | 15 |
| Validation | 10 | 148 | 2 |
| Test | 10 | 136 | 3 |

Aynı sahne grubu birden fazla splite girmiyor. Test görüntüleri model veya eşik seçimi için kullanılmamalıdır.

## Eksik yerel görüntüler

Bu görüntüler yeni CVAT exportunda etiketli fakat çalışma klasöründe yoktur ve şimdilik eğitim dışıdır:

- `20260729_100242.jpg`
- `20260729_102325.jpg`
- `20260729_102810(0).jpg`
- `20260729_102848.jpg`
- `20260729_103914(0).jpg`

## Sonraki önerilen annotation paketi

Mevcut 65 yerel etiketli görüntü 20 sahne grubunu kapsıyor. Geriye yalnızca etiketsiz görüntüler içeren 21 sahne grubu kalıyor. Başlangıç veri setini yaklaşık 95 görüntüye çıkarmak için her etiketsiz gruptan en az bir örnek ve büyük gruplardan çeşitlilik sağlayan ek örneklerle 30 görüntülük `next_annotation_batch.csv` oluşturuldu.

## Üretilen dosyalar

- `image_inventory.csv`: tüm görüntülerin boyut, hash ve kalite ölçümleri.
- `near_duplicate_pairs.csv`: algısal olarak çok benzer çiftler.
- `scene_groups.csv`: her görüntünün sahne grubu ve durumu.
- `split_manifest.csv`: mevcut etiketli görüntüler için eğitim/doğrulama/test ayrımı.
- `dataset_summary.json`: makine tarafından okunabilir özet.
- `next_annotation_batch.csv`: önerilen 30 yeni annotation görüntüsü.

