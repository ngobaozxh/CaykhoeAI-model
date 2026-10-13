import csv
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np
from PIL import Image
import train_candidate as candidate

ROOT = Path(__file__).resolve().parent.parent
NODE = Path('C:/Users/Hi Admin/.workbuddy-ai/binaries/node/versions/22.22.2-6/node.exe')

class DatasetChecks(unittest.TestCase):
    def setUp(self):

        self.folder = Path(tempfile.mkdtemp(prefix='training-unit-', dir=ROOT / 'outputs'))
        self.rows = []
        for split_index, split in enumerate(candidate.SPLITS):
            for label_index, label in enumerate(candidate.LABELS):
                number = split_index * len(candidate.LABELS) + label_index
                name = str(number) + '.png'
                Image.new('RGB', (101, 103), (number, number + 50, number + 100)).save(self.folder / name)
                self.rows.append({'path': name, 'label': label, 'split': split, 'group': split + '-' + label})
        self.manifest = self.folder / 'manifest.csv'
        self.write_manifest()

    def write_manifest(self):
        with self.manifest.open('w', encoding='utf-8', newline='') as handle:
            writer = csv.DictWriter(handle, fieldnames=['path', 'label', 'split', 'group'])
            writer.writeheader()
            writer.writerows(self.rows)

    def test_valid_dataset_all_classes(self):
        rows, counts, audit = candidate.read_manifest(self.manifest)
        self.assertEqual(len(rows), 42)
        self.assertEqual(audit['groups'], 42)
        self.assertFalse(audit['training_executed'])
        self.assertTrue(all(counts[(split, label)] == 1 for split in candidate.SPLITS for label in candidate.LABELS))

    def test_group_leakage_rejected(self):
        self.rows[14]['group'] = self.rows[0]['group']
        self.write_manifest()
        with self.assertRaisesRegex(ValueError, 'Group leakage'):
            candidate.read_manifest(self.manifest)

    def test_identical_pixels_different_encoding_rejected(self):
        with Image.open(self.folder / self.rows[0]['path']) as image:
            image.save(self.folder / 'duplicate.bmp')
        self.rows[14]['path'] = 'duplicate.bmp'
        self.write_manifest()
        with self.assertRaisesRegex(ValueError, 'Duplicate decoded image'):
            candidate.read_manifest(self.manifest)

    def test_missing_class_rejected(self):
        self.rows.pop()
        self.write_manifest()
        with self.assertRaisesRegex(ValueError, 'Missing test/ngo_khoe_manh'):
            candidate.read_manifest(self.manifest)

    def test_invalid_label_rejected(self):
        self.rows[0]['label'] = 'unknown'
        self.write_manifest()
        with self.assertRaisesRegex(ValueError, 'Unknown label'):
            candidate.read_manifest(self.manifest)

    def test_small_image_rejected(self):
        Image.new('RGB', (99, 150)).save(self.folder / self.rows[0]['path'])
        with self.assertRaisesRegex(ValueError, 'below 100 px'):
            candidate.read_manifest(self.manifest)

    def test_read_only_cli_without_tensorflow(self):
        before = {p.name: p.read_bytes() for p in self.folder.iterdir() if p.is_file()}
        output = self.folder / 'audit'
        result = subprocess.run([sys.executable, str(ROOT / 'tools/train_candidate.py'),
                                 '--manifest', str(self.manifest), '--output', str(output), '--validate-only'],
                                capture_output=True, text=True, encoding='utf-8')
        self.assertEqual(result.returncode, 0, result.stderr)
        audit = json.loads((output / 'dataset_audit.json').read_text(encoding='utf-8'))
        self.assertFalse(audit['training_executed'])
        self.assertEqual(list(output.iterdir()), [output / 'dataset_audit.json'])
        for name, value in before.items():
            self.assertEqual((self.folder / name).read_bytes(), value)
        repeat = subprocess.run([sys.executable, str(ROOT / 'tools/train_candidate.py'),
                                 '--manifest', str(self.manifest), '--output', str(output), '--validate-only'],
                                capture_output=True, text=True, encoding='utf-8')
        self.assertEqual(repeat.returncode, 2)
        self.assertIn('never overwritten', repeat.stderr)

    def test_pixel_sampling_matches_browser_index_formula(self):
        sizes = [100, 101, 224, 225, 300, 1024, 4000]
        js = 'const sizes=' + json.dumps(sizes) + ';console.log(JSON.stringify(sizes.map(n=>{const s=n/224,a=[];let v=.5*s;for(let i=0;i<224;i++){a.push(Math.min(n-1,Math.floor(v)));v+=s;}return a;})));'
        result = subprocess.run([str(NODE), '-e', js], capture_output=True, text=True, check=True)
        self.assertEqual([candidate.nearest_indices(n) for n in sizes], json.loads(result.stdout))
        pixels = candidate.browser_pixels(self.folder / '0.png')
        self.assertEqual(pixels.shape, (224, 224, 3))
        self.assertEqual(pixels.dtype, np.float32)
        self.assertTrue(np.allclose(pixels[0, 0], [0, 50 / 255, 100 / 255]))

    def test_duplicate_csv_headers_rejected(self):
        with self.manifest.open('w', encoding='utf-8', newline='') as handle:
            writer = csv.writer(handle)
            writer.writerow(['path', 'label', 'split', 'group', 'split'])
            for row in self.rows:
                writer.writerow([row['path'], row['label'], row['split'], row['group'], 'test'])
        with self.assertRaisesRegex(ValueError, 'Duplicate CSV column'):
            candidate.read_manifest(self.manifest)

    def test_transparency_rejected(self):
        Image.new('RGBA', (101, 103), (255, 50, 20, 0)).save(self.folder / self.rows[0]['path'])
        with self.assertRaisesRegex(ValueError, 'Transparent image'):
            candidate.read_manifest(self.manifest)

    def test_metrics_include_confidence_one_bin(self):
        probs = np.eye(len(candidate.LABELS), dtype=np.float32)
        metrics = candidate.classification_metrics(probs, np.arange(len(candidate.LABELS)))
        self.assertEqual(metrics['accuracy'], 1)
        self.assertEqual(metrics['macro_f1'], 1)
        self.assertEqual(metrics['ece_10_bins'], 0)
        self.assertEqual(metrics['test_samples'], 14)

if __name__ == '__main__':
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(DatasetChecks)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    report = {
        'tests_run': result.testsRun,
        'failures': len(result.failures),
        'errors': len(result.errors),
        'ok': result.wasSuccessful(),
        'training_executed': False,
        'scope': 'Synthetic unit fixtures: manifest gate, read-only CLI, pixel-index formula and metrics. TensorFlow training/export not executed.',
    }
    (ROOT / 'outputs/training-pipeline-validation.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    sys.exit(0 if result.wasSuccessful() else 1)
