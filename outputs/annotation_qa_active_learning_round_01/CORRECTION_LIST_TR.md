# Aktif Öğrenme 1. Tur — Ayrıntılı Etiket Denetimi

## Sonuç

Etiketlerin genel görünür-ön-yüz yaklaşımı doğru. Üçgen, beşgen, altıgen, yedi köşeli veya içbükey maskeler sırf bu topolojiye sahip oldukları için hatalı değildir. Perspektif, örtülme ve görüntü sınırı fiziksel şekli değiştirebilir; bu maskeler dörtgene zorlanmamalıdır.

Bu dışa aktarım eğitim verisine eklenmeden önce aşağıdaki beş görüntüdeki eksik görünen kısmi ön yüzler CVAT'ta kontrol edilip eklenmelidir.

## CVAT'ta yapılması gerekenler

| Görüntü | Kontrol/düzeltme |
|---|---|
| `20260729_092402.jpg` | Görüntünün en sağ kenarında, QR etiketli ve kadraj tarafından kesilen ön yüz etiketsiz kalmış. Görünen kısmı polygon olarak ekleyin. |
| `20260729_092508.jpg` | Büyük paslı ön yüzün arkasında, sağ üstte bulunan QR etiketli ön yüz etiketsiz kalmış. Polygon ekleyin. |
| `20260729_092532.jpg` | Sol alt görüntü kenarında QR etiketli, kadraj tarafından kesilen ön yüz etiketsiz kalmış. Görünen kısmı ekleyin. |
| `20260729_095337(0).jpg` | Sağ üst kenardaki kısmi ön yüz ile sol alt kenardaki kısmi ön yüz etiketsiz kalmış. İkisini de yalnızca görünen pikselleriyle ekleyin. |
| `20260729_102304.jpg` | En sol görüntü kenarında kısmen görünen sıcak billet ön yüzü etiketsiz kalmış. Görünen kısmı ekleyin. |

## Mekanik olarak düzeltilebilecek iki nokta

Bu iki polygon görsel olarak makul; yalnızca aynı köşe art arda iki kez kaydedilmiş. Yeni CVAT dışa aktarımından sonra geometrinin şeklini değiştirmeden otomatik temizlenebilir:

- `20260729_092409.jpg`, dışa aktarım instance `11`: `(2467.47, 3002.08)` noktası iki kez art arda bulunuyor.
- `20260729_092532.jpg`, dışa aktarım instance `2`: `(1187.25, 5564.43)` noktası iki kez art arda bulunuyor.

## Yapısal denetim özeti

- CVAT biçimi: `CVAT for images 1.1`
- Değişmez kaynak ZIP SHA-256: `39E27F74699287DC9F62B3FEA7D2DF68120560ED1BB6009F04F9FFA03819E685`
- CVAT görev kimliği/adı: `4 / newKutuk`
- Görüntü: `34/34` mevcut ve etiketli
- Toplam polygon instance: `530`
- Köşe dağılımı: 3 köşe `1`, 4 köşe `446`, 5 köşe `51`, 6 köşe `24`, 7 köşe `8`
- Çok köşeli maske: `83` — otomatik hata değil
- İçbükey maske: `48` — otomatik hata değil
- Görüntü sınırına temas eden maske: `45` — kısmi görünür yüzlerde beklenebilir
- Çok küçük maske: `30` — tam çözünürlük incelemesinde çoğu uzak ama gerçek ön yüz; silinmemeli
- Beklenmeyen sınıf, görüntü dışı nokta, yüksek örtüşmeli mükerrer instance veya eksik kaynak görüntü bulunmadı
- İki `SELF_INTERSECTION` sinyali gerçek çaprazlama değil; yukarıdaki yinelenen köşelerden kaynaklanıyor

## Veri durumu

`REVIEW_REQUIRED`: Beş görüntüdeki eksik kısmi yüzler düzeltilip yeni, sürümlenmiş bir CVAT dışa aktarımı alınmadan eğitim verisine eklenmemelidir.
