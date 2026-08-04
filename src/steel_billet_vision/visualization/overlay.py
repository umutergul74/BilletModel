from __future__ import annotations

from pathlib import Path
from typing import Any
import colorsys
import html
import json

import cv2
import numpy as np


SIGNAL_LABELS = {
    "UNVERIFIED_HUMAN_ANNOTATION": "Henüz insan tarafından doğrulanmadı",
    "MISSING_SOURCE_IMAGE": "Kaynak görüntü eksik",
    "MULTISIDED_VISIBLE_REGION_REVIEW": "Dörtten fazla köşeli görünür bölge; fiziksel sınırı kontrol et",
    "CONCAVE_VISIBLE_REGION_REVIEW": "İçbükey görünür bölge; örtüşme sınırını kontrol et",
    "FRAME_BOUNDARY_TRUNCATION_REVIEW": "Görüntü sınırında kesilen maske",
    "SELF_INTERSECTION": "Polygon kendi kendini kesiyor olabilir",
    "DUPLICATE_VERTEX": "Tekrarlanan polygon noktası",
    "TRIANGULAR_VISIBLE_REGION_REVIEW": "Üçgen görünür bölge; geçerli bir örtüşme olabilir",
    "VERY_SMALL_MASK_REVIEW": "Alışılmadık derecede küçük maske",
    "OUT_OF_BOUNDS_VERTEX": "Görüntü sınırı dışında polygon noktası",
    "UNEXPECTED_CLASS": "Beklenmeyen sınıf etiketi",
}


def _signal_label(signal: str) -> str:
    code, _, related_instance = signal.partition(":")
    if code == "LIKELY_DUPLICATE_INSTANCE":
        return f"#{related_instance} ile muhtemel mükerrer instance"
    if code == "POLYGON_OVERLAP_REVIEW":
        return f"#{related_instance} ile önemli polygon çakışması"
    return SIGNAL_LABELS.get(code, signal)


def _read_image(path: Path) -> np.ndarray:
    data = np.fromfile(path, dtype=np.uint8)
    image = cv2.imdecode(data, cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError(f"Unreadable image: {path}")
    return image


def _write_image(path: Path, image: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    ok, encoded = cv2.imencode(path.suffix, image)
    if not ok:
        raise ValueError(f"Could not encode overlay: {path}")
    encoded.tofile(path)


def _color(index: int) -> tuple[int, int, int]:
    r, g, b = colorsys.hsv_to_rgb((index * 0.61803398875) % 1.0, 0.82, 1.0)
    return int(b * 255), int(g * 255), int(r * 255)


def render_overlay(image_path: Path, instances: list[dict[str, Any]], output_path: Path, max_dimension: int) -> None:
    source = _read_image(image_path)
    height, width = source.shape[:2]
    scale = min(1.0, max_dimension / max(width, height))
    if scale < 1.0:
        source = cv2.resize(source, (round(width * scale), round(height * scale)), interpolation=cv2.INTER_AREA)
    overlay = source.copy()
    for instance in instances:
        pts = np.round(np.asarray(instance["points"], dtype=np.float32) * scale).astype(np.int32)
        cv2.fillPoly(overlay, [pts], _color(int(instance["instance_index"])))
    canvas = cv2.addWeighted(overlay, 0.30, source, 0.70, 0)
    for instance in instances:
        pts = np.round(np.asarray(instance["points"], dtype=np.float32) * scale).astype(np.int32)
        color = _color(int(instance["instance_index"]))
        cv2.polylines(canvas, [pts], True, color, max(2, round(4 * scale)), cv2.LINE_AA)
        for point in pts:
            cv2.circle(canvas, tuple(point), max(2, round(5 * scale)), (255, 255, 255), -1, cv2.LINE_AA)
            cv2.circle(canvas, tuple(point), max(1, round(3 * scale)), color, -1, cv2.LINE_AA)
        anchor = tuple(pts[0])
        label = f"#{instance['instance_index']}"
        cv2.putText(canvas, label, anchor, cv2.FONT_HERSHEY_SIMPLEX, max(0.45, 0.8 * scale), (0, 0, 0), 4, cv2.LINE_AA)
        cv2.putText(canvas, label, anchor, cv2.FONT_HERSHEY_SIMPLEX, max(0.45, 0.8 * scale), (255, 255, 255), 2, cv2.LINE_AA)
    _write_image(output_path, canvas)


def write_review_html(report: dict[str, Any], output_path: Path) -> None:
    cards: list[str] = []
    for image_record in report["images"]:
        image_signals = sorted({signal for inst in image_record["instances"] for signal in inst["signals"]})
        signal_text = " ".join(image_signals + (["MISSING_SOURCE_IMAGE"] if not image_record["source_exists"] else []))
        rows: list[str] = []
        for instance in image_record["instances"]:
            stable_id = instance["stable_id"]
            signals = "; ".join(_signal_label(signal) for signal in instance["signals"])
            rows.append(f"""
              <tr data-signals="{html.escape(' '.join(instance['signals']))}">
                <td>#{instance['instance_index']}<br><small>{html.escape(stable_id)}</small></td>
                <td>{html.escape(instance['review_priority'])}</td><td>{instance['vertex_count']}</td>
                <td>{instance['area_ratio']:.6f}</td>
                <td>{html.escape(signals)}<br><small>{html.escape(instance['likely_issue'])}</small></td>
                <td>{html.escape(instance['decision_required'])}</td>
                <td><select data-id="{html.escape(stable_id)}"><option value="">İNCELENMEDİ</option>
                  <option value="GOOD">İYİ — düzeltme gerekmiyor</option>
                  <option value="MINOR_CORRECTION">KÜÇÜK DÜZELTME</option>
                  <option value="MAJOR_CORRECTION">BÜYÜK DÜZELTME</option>
                  <option value="INVALID">GEÇERSİZ</option>
                  <option value="AMBIGUOUS">BELİRSİZ</option>
                  <option value="REVIEW_REQUIRED">TEKRAR İNCELEME GEREKLİ</option></select></td>
                <td><input data-note="{html.escape(stable_id)}" placeholder="Kararın nedeni / CVAT'ta yapılacak düzeltme" /></td>
              </tr>""")
        if image_record["source_exists"]:
            visual = f'<a href="{html.escape(image_record["source_href"])}" target="_blank"><img src="{html.escape(image_record["overlay_href"])}" loading="lazy" /></a>'
        else:
            visual = '<div class="missing">KAYNAK GÖRÜNTÜ EKSİK — maske görseli oluşturulamadı</div>'
        cards.append(f"""
          <section class="card" data-signals="{html.escape(signal_text)}" data-name="{html.escape(image_record['name'])}">
            <h2>{image_record['image_id']:03d} · {html.escape(image_record['name'])}</h2>
            <p>{len(image_record['instances'])} polygon · görüntü durumu: <strong>İNSAN İNCELEMESİ GEREKLİ</strong></p>
            <p><small>Maskeli görüntüye tıklayarak orijinal fotoğrafı açabilirsiniz.</small></p>
            {visual}
            <table><thead><tr><th>Instance</th><th>Öncelik</th><th>Köşe</th><th>Alan oranı</th><th>Uyarılar / olası sorun</th><th>Kontrol ve CVAT işlemi</th><th>İnsan kararı</th><th>Notlar</th></tr></thead>
            <tbody>{''.join(rows)}</tbody></table>
          </section>""")
    metadata = html.escape(json.dumps(report["summary"], indent=2, ensure_ascii=False))
    output_path.write_text(f"""<!doctype html><html lang="tr"><head><meta charset="utf-8"><title>Çelik kütük annotation incelemesi</title>
      <style>body{{font:14px system-ui;margin:0;background:#121820;color:#e6edf3}}header{{position:sticky;top:0;background:#0b1016;padding:16px;z-index:2;border-bottom:1px solid #34404c}}main{{padding:18px;max-width:1500px;margin:auto}}.card{{background:#1b2430;padding:16px;margin:0 0 20px;border-radius:10px}}img{{max-width:100%;max-height:760px;background:#000}}table{{width:100%;border-collapse:collapse;margin-top:12px}}th,td{{border:1px solid #3b4652;padding:6px;text-align:left;vertical-align:top}}input{{width:300px;max-width:95%}}select,input,button{{background:#0f1720;color:#e6edf3;border:1px solid #526170;padding:7px;margin:3px}}.missing{{padding:70px;background:#5b2020;font-size:20px}}pre{{white-space:pre-wrap}}.hidden{{display:none}}small{{color:#b8c4cf}}</style></head><body>
      <header><strong>Doğrulanmamış CVAT annotation incelemesi</strong><br>
      <input id="filter" placeholder="Dosya adı, uyarı veya sorun ara" />
      <select id="quickFilter"><option value="">Tüm kayıtlar</option><option value="SELF_INTERSECTION DUPLICATE_VERTEX">Yapısal sorunlar</option>
      <option value="MISSING_SOURCE_IMAGE">Kaynak görüntüsü eksik</option><option value="TRIANGULAR_VISIBLE_REGION_REVIEW">Üçgen maskeler</option>
      <option value="MULTISIDED_VISIBLE_REGION_REVIEW">Çok köşeli maskeler</option><option value="CONCAVE_VISIBLE_REGION_REVIEW">İçbükey maskeler</option>
      <option value="FRAME_BOUNDARY_TRUNCATION_REVIEW">Görüntü sınırındaki maskeler</option><option value="VERY_SMALL_MASK_REVIEW">Çok küçük maskeler</option></select>
      <button id="export">Kararları JSON olarak indir</button><span id="progress"></span></header><main>
      <section class="card"><h2>Nasıl kullanılır?</h2><p>Önce kritik filtrelerden başlayın. Renkli maskeyi görüntüyle karşılaştırın, insan kararını seçin ve gerekiyorsa CVAT'ta yapılacak düzeltmeyi not edin. Üçgen, çok köşeli veya içbükey olması tek başına hata değildir.</p></section>
      <details><summary>Ölçülen özet ve veri kaynağı bilgileri</summary><pre>{metadata}</pre></details>{''.join(cards)}</main>
      <script>
      const key='steel-billet-cvat-job-2-review-v1'; const state=JSON.parse(localStorage.getItem(key)||'{{}}');
      function save(){{localStorage.setItem(key,JSON.stringify(state)); update();}}
      document.querySelectorAll('select[data-id]').forEach(el=>{{let id=el.dataset.id;if(state[id])el.value=state[id].decision||'';el.onchange=()=>{{state[id]=state[id]||{{}};state[id].decision=el.value;save();}}}});
      document.querySelectorAll('input[data-note]').forEach(el=>{{let id=el.dataset.note;if(state[id])el.value=state[id].note||'';el.oninput=()=>{{state[id]=state[id]||{{}};state[id].note=el.value;save();}}}});
      function update(){{let done=Object.values(state).filter(x=>x.decision).length;document.getElementById('progress').textContent=` · ${{done}}/{report['summary']['instances_total']} instance kararı tamamlandı`;}} update();
      function applyFilters(){{let q=document.getElementById('filter').value.toLowerCase();let selected=document.getElementById('quickFilter').value.split(' ').filter(Boolean);document.querySelectorAll('.card[data-name]').forEach(c=>{{let haystack=(c.dataset.name+' '+c.dataset.signals).toLowerCase();let textOk=!q||haystack.includes(q);let quickOk=!selected.length||selected.some(x=>c.dataset.signals.includes(x));c.classList.toggle('hidden',!(textOk&&quickOk));}});}}
      document.getElementById('filter').oninput=applyFilters; document.getElementById('quickFilter').onchange=applyFilters;
      document.getElementById('export').onclick=()=>{{let blob=new Blob([JSON.stringify({{schema_version:'1.0',annotation_version:{json.dumps(report['summary']['annotation_version'])},exported_at:new Date().toISOString(),decisions:state}},null,2)],{{type:'application/json'}});let a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download='inceleme_kararlari.json';a.click();}};
      </script></body></html>""", encoding="utf-8")
