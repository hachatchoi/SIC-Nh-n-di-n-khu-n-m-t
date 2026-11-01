"""Offline face recognition evaluation; never imports the web app or writes its DB."""
import argparse
import csv
import hashlib
import json
import math
import sqlite3
import sys
import time
from collections import Counter
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read_gallery(database, class_id):
    with closing(sqlite3.connect(Path(database).resolve().as_uri() + '?mode=ro', uri=True)) as db:
        db.row_factory = sqlite3.Row
        if db.execute('SELECT id FROM classes WHERE id=?', (class_id,)).fetchone() is None:
            raise ValueError('Class does not exist.')
        has_enrollments = db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='enrollments'").fetchone()
        query = ('SELECT s.id,s.code,s.embedding FROM students s JOIN enrollments e ON e.student_id=s.id WHERE e.class_id=? ORDER BY s.id'
                 if has_enrollments else 'SELECT id,code,embedding FROM students WHERE class_id=? ORDER BY id')
        rows = db.execute(query, (class_id,)).fetchall()
    if not rows:
        raise ValueError('Class has no enrolled students.')
    gallery = []
    dimension = None
    for row in rows:
        vector = json.loads(row['embedding'])
        if not isinstance(vector, list) or not vector or not all(isinstance(x, (int, float)) and math.isfinite(x) for x in vector):
            raise ValueError('Invalid stored embedding: ' + row['code'])
        norm = math.sqrt(sum(x*x for x in vector))
        if not 0.99 <= norm <= 1.01:
            raise ValueError('Stored embedding is not normalized: ' + row['code'])
        dimension = dimension or len(vector)
        if len(vector) != dimension:
            raise ValueError('Inconsistent embedding dimensions.')
        gallery.append({'id':row['id'], 'code':row['code'], 'embedding':vector})
    return gallery


def read_manifest(manifest, gallery):
    codes = {row['code'] for row in gallery}
    seen = {}
    samples = []
    manifest = Path(manifest).resolve()
    with manifest.open(encoding='utf-8-sig', newline='') as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != ['path', 'expected_code', 'split', 'condition']:
            raise ValueError('CSV columns must be: path,expected_code,split,condition')
        for number, row in enumerate(reader, 2):
            if None in row or any(value is None for value in row.values()):
                raise ValueError(f'Invalid CSV row {number}')
            row = {key:value.strip() for key,value in row.items()}
            if row['split'] not in ('validation', 'test'):
                raise ValueError(f'Invalid split on row {number}')
            if row['expected_code'] and row['expected_code'] not in codes:
                raise ValueError(f'Unknown student code on row {number}: {row["expected_code"]}')
            path = (manifest.parent / row['path']).resolve()
            if not row['path'] or not path.is_relative_to(manifest.parent) or not path.is_file():
                raise ValueError(f'Missing image or path outside manifest folder on row {number}')
            if not 0 < path.stat().st_size <= 10*1024*1024:
                raise ValueError(f'Image size must be 1 byte to 10 MiB: {row["path"]}')
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            if digest in seen:
                raise ValueError(f'Duplicate image bytes: {row["path"]} and {seen[digest]}')
            seen[digest] = row['path']
            samples.append({**row, 'file':path, 'sha256':digest})
    if not samples:
        raise ValueError('No images yet. Fill samples.csv following evaluation/README.md.')
    return samples


def metrics(results, threshold):
    counts = Counter()
    for row in results:
        known = bool(row['expected_code'])
        counts['known' if known else 'unknown'] += 1
        if row['error']:
            counts['errors'] += 1
            continue
        accepted = row['score'] >= threshold
        if known:
            if not accepted:
                counts['known_rejected'] += 1
            elif row['candidate'] == row['expected_code']:
                counts['known_correct'] += 1
            else:
                counts['known_wrong_identity'] += 1
        else:
            counts['unknown_accepted' if accepted else 'unknown_rejected'] += 1
    out = {key:counts[key] for key in ('known','unknown','errors','known_correct','known_rejected','known_wrong_identity','unknown_accepted','unknown_rejected')}
    out['threshold'] = threshold
    out['known_correct_rate'] = counts['known_correct']/counts['known'] if counts['known'] else None
    out['unknown_accept_rate'] = counts['unknown_accepted']/counts['unknown'] if counts['unknown'] else None
    return out


def extract(raw, engine, guide):
    import cv2
    import numpy as np
    from insightface.app.common import Face
    image = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError('Cannot decode image')
    h, w = image.shape[:2]
    if max(h,w) > 1600:
        image = cv2.resize(image, (round(w*1600/max(h,w)), round(h*1600/max(h,w))))
    boxes, landmarks = engine.det_model.detect(image, max_num=0, metric='default')
    indices = list(range(len(boxes)))
    if guide:
        # Same midpoint/ellipse rule as classroom.py; no app import or DB initialization.
        h,w = image.shape[:2]
        ry = min(h*.39, w*.4/.75)
        rx = ry*.75
        def inside(box):
            x1,y1,x2,y2 = box[:4]
            cx,cy = (x1+x2)/2,(y1+y2)/2
            return all(((x-w/2)/rx)**2+((y-h/2)/ry)**2 <= 1 for x,y in ((x1,cy),(x2,cy),(cx,y1),(cx,y2)))
        indices = [i for i in indices if inside(boxes[i])]
    if len(indices) != 1:
        raise ValueError(f'Expected one eligible face, found {len(indices)}')
    i = indices[0]
    face = Face(bbox=boxes[i,:4], kps=landmarks[i] if landmarks is not None else None, det_score=boxes[i,4])
    vector = np.asarray(engine.models['recognition'].get(image, face), dtype=np.float32)
    norm = float(np.linalg.norm(vector))
    if not np.isfinite(vector).all() or norm < 1e-12:
        raise ValueError('Invalid extracted embedding')
    return vector / norm


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database', type=Path, default=ROOT/'backend/classroom.db')
    parser.add_argument('--list-classes', action='store_true')
    parser.add_argument('--class-id', type=int)
    parser.add_argument('--manifest', type=Path, default=ROOT/'evaluation/samples.csv')
    parser.add_argument('--split', choices=['validation','test'], default='validation')
    parser.add_argument('--threshold', type=float, default=.70)
    parser.add_argument('--check', action='store_true', help='Validate inputs without loading AI')
    parser.add_argument('--guide', action='store_true', help='Apply the current oval rule to already viewport-cropped images')
    args = parser.parse_args(argv)
    if not math.isfinite(args.threshold) or not -1 <= args.threshold <= 1:
        parser.error('Threshold must be finite and in [-1, 1]')
    if args.list_classes:
        with closing(sqlite3.connect(args.database.resolve().as_uri()+'?mode=ro', uri=True)) as db:
            for row in db.execute('SELECT c.id,c.name,COUNT(s.id) FROM classes c LEFT JOIN students s ON s.class_id=c.id GROUP BY c.id ORDER BY c.id'):
                print(f'ID {row[0]} | {row[1]} | {row[2]} students')
        return 0
    if args.class_id is None:
        parser.error('--class-id is required unless --list-classes is used')
    try:
        gallery = read_gallery(args.database, args.class_id)
        samples = read_manifest(args.manifest, gallery)
        chosen = [s for s in samples if s['split'] == args.split]
        if not chosen:
            raise ValueError('No images for selected split')
        print(f'Validated {len(samples)} images; {len(chosen)} in {args.split}; {len(gallery)} enrolled students.')
        if args.check:
            return 0
        # Loaded only when explicitly running an offline evaluation.
        sys.path.insert(0, str(ROOT/'backend'))
        from face_engine import face_app
        import numpy as np
        results = []
        for sample in chosen:
            record = {key:sample[key] for key in ('path','expected_code','split','condition','sha256')}
            record.update(candidate='', score=None, error='', processing_ms=None)
            start = time.perf_counter()
            try:
                vector = extract(sample['file'].read_bytes(), face_app, args.guide)
                matches = [(float(np.dot(vector, np.asarray(s['embedding']))), s['id'], s['code']) for s in gallery]
                record['score'], _, record['candidate'] = max(matches)
            except Exception as error:
                record['error'] = str(error)
            record['processing_ms'] = round((time.perf_counter()-start)*1000, 2)
            results.append(record)
            print(f'{len(results)}/{len(chosen)}: {sample["path"]} | {record["error"] or "OK"}')
        thresholds = [round(i/100,2) for i in range(40,91,5)] if args.split == 'validation' else []
        thresholds = sorted(set(thresholds+[args.threshold]))
        report = {'created_utc':datetime.now(timezone.utc).isoformat(), 'class_id':args.class_id,
                  'split':args.split, 'guide':args.guide, 'sample_count':len(results),
                  'gallery_sha256':hashlib.sha256(json.dumps(gallery,sort_keys=True).encode()).hexdigest(),
                  'baseline':metrics(results,args.threshold), 'thresholds':[metrics(results,t) for t in thresholds],
                  'by_condition':{c:metrics([r for r in results if r['condition']==c],args.threshold) for c in sorted({r['condition'] for r in results})},
                  'timing':{'mean_ms':float(np.mean([r['processing_ms'] for r in results])),
                            'p95_ms':float(np.percentile([r['processing_ms'] for r in results],95)),
                            'scope':'Offline extraction and matching; excludes model startup, web requests, camera and database writes. Includes cold first inference and failed samples.'}}
        out = ROOT/'evaluation/reports'/datetime.now().strftime('%Y%m%d-%H%M%S-%f')
        out.mkdir(parents=True, exist_ok=False)
        (out/'summary.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
        with (out/'predictions.csv').open('w',encoding='utf-8-sig',newline='') as handle:
            writer=csv.DictWriter(handle,fieldnames=list(results[0]));writer.writeheader();writer.writerows(results)
        with (out/'thresholds.csv').open('w',encoding='utf-8-sig',newline='') as handle:
            writer=csv.DictWriter(handle,fieldnames=list(report['baseline']));writer.writeheader();writer.writerows(report['thresholds'])
        print(f'Report: {out}\nNo production threshold or attendance records were changed.')
        return 0
    except (ValueError, OSError, sqlite3.Error) as error:
        print(f'Error: {error}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
