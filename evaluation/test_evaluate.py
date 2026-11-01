import csv
import json
import sqlite3
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch
import evaluate
from pathlib import Path
from evaluate import metrics, read_gallery, read_manifest


class EvaluationTests(unittest.TestCase):
    def test_offline_run_writes_reports_without_loading_web_or_changing_db(self):
        with tempfile.TemporaryDirectory(prefix='evaluation-test-', dir=Path(__file__).resolve().parent) as folder:
            root = Path(folder)
            database = root/'fixture.db'
            db = sqlite3.connect(database)
            db.executescript('CREATE TABLE classes(id INTEGER); CREATE TABLE students(id INTEGER,class_id INTEGER,code TEXT,embedding TEXT); INSERT INTO classes VALUES(1);')
            db.execute('INSERT INTO students VALUES(1,1,?,?)', ('A', '[1.0,0.0]'))
            db.commit(); db.close()
            before = database.read_bytes()
            (root/'a.jpg').write_bytes(b'synthetic input')
            manifest = root/'samples.csv'
            manifest.write_text('path,expected_code,split,condition\na.jpg,A,test,synthetic\n')
            with patch.object(evaluate, 'ROOT', root), patch.dict('sys.modules', {'face_engine':SimpleNamespace(face_app=object())}), patch.object(evaluate, 'extract', return_value=[1.,0.]):
                self.assertEqual(evaluate.main(['--database',str(database),'--manifest',str(manifest),'--class-id','1','--split','test','--threshold','0.75']), 0)
            report = next((root/'evaluation/reports').glob('*/summary.json'))
            data = json.loads(report.read_text(encoding='utf-8'))
            self.assertEqual(data['baseline']['known_correct'], 1)
            self.assertEqual(len(data['thresholds']), 1)
            self.assertTrue((report.parent/'predictions.csv').exists())
            self.assertTrue((report.parent/'thresholds.csv').exists())
            self.assertEqual(database.read_bytes(), before)

    def test_counts_do_not_hide_wrong_identity_or_errors(self):
        def row(expected, candidate='', score=0, error=''):
            return dict(expected_code=expected,candidate=candidate,score=score,error=error)
        data=[row('A','A',.7),row('A','B',.9),row('A','A',.6),row('', 'A',.8),row('', 'A',.2),row('',error='invalid')]
        r=metrics(data,.7)
        self.assertEqual(r['known_correct'],1)
        self.assertEqual(r['known_wrong_identity'],1)
        self.assertEqual(r['known_rejected'],1)
        self.assertEqual(r['unknown_accepted'],1)
        self.assertEqual(r['unknown_rejected'],1)
        self.assertEqual(r['errors'],1)
        self.assertAlmostEqual(r['unknown_accept_rate'],1/3)
        self.assertIsNone(metrics([], .7)['known_correct_rate'])

    def test_manifest_rejects_duplicate_bytes_between_splits(self):
        with tempfile.TemporaryDirectory(prefix='evaluation-test-', dir=Path(__file__).resolve().parent) as folder:
            root=Path(folder)
            (root/'a.jpg').write_bytes(b'same image')
            (root/'b.jpg').write_bytes(b'same image')
            (root/'samples.csv').write_text('path,expected_code,split,condition\na.jpg,A,validation,light\nb.jpg,A,test,light\n')
            with self.assertRaisesRegex(ValueError,'Duplicate'):
                read_manifest(root/'samples.csv',[{'code':'A'}])

    def test_manifest_validates_identity_and_missing_data(self):
        with tempfile.TemporaryDirectory(prefix='evaluation-test-', dir=Path(__file__).resolve().parent) as folder:
            root=Path(folder); manifest=root/'samples.csv'
            manifest.write_text('path,expected_code,split,condition\n')
            with self.assertRaisesRegex(ValueError,'No images'):
                read_manifest(manifest,[{'code':'A'}])
            (root/'a.jpg').write_bytes(b'image')
            manifest.write_text('path,expected_code,split,condition\na.jpg,B,validation,light\n')
            with self.assertRaisesRegex(ValueError,'Unknown student'):
                read_manifest(manifest,[{'code':'A'}])
            manifest.write_text('path,expected_code,split,condition\na.jpg,,test,light\n')
            rows=read_manifest(manifest,[{'code':'A'}])
            self.assertEqual(rows[0]['expected_code'],'')

    def test_read_gallery_does_not_create_missing_database(self):
        with tempfile.TemporaryDirectory(prefix='evaluation-test-', dir=Path(__file__).resolve().parent) as folder:
            path=Path(folder)/'missing.db'
            with self.assertRaises(sqlite3.OperationalError):
                read_gallery(path,1)
            self.assertFalse(path.exists())

    def test_gallery_read_leaves_database_unchanged(self):
        with tempfile.TemporaryDirectory(prefix='evaluation-test-', dir=Path(__file__).resolve().parent) as folder:
            path=Path(folder)/'fixture.db'
            with sqlite3.connect(path) as db:
                db.executescript('CREATE TABLE classes(id INTEGER); CREATE TABLE students(id INTEGER,class_id INTEGER,code TEXT,embedding TEXT); INSERT INTO classes VALUES(1);')
                db.execute('INSERT INTO students VALUES(1,1,?,?)',('A',json.dumps([1.,0.])))
            db.close()
            before=path.read_bytes()
            self.assertEqual(read_gallery(path,1)[0]['code'],'A')
            self.assertEqual(path.read_bytes(),before)

if __name__=='__main__':
    unittest.main()
