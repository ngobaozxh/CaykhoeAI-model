import argparse
import csv
import hashlib
import json
import math
import platform
from collections import Counter
from pathlib import Path

LABELS = [
    'benh_loet_chanh', 'cam_bi_xi_mu', 'cam_khoe_manh', 'chanh_khoe_manh',
    'chanh_vang_la', 'lua_bi_nam', 'lua_binh_thuong', 'lua_sau_cuon_la',
    'lua_sau_duc_than', 'mia_gi_sat', 'mia_khoe_manh', 'mia_thoi_do',
    'ngo_chay_la', 'ngo_khoe_manh',
]
SPLITS = ('train', 'val', 'test')
PREPROCESSING = 'whole-image nearest 224, iterative center indices, RGB/255; EXIF orientation; no crop'

def require(condition, message):
    if not condition:
        raise ValueError(message)

def nearest_indices(length, size=224):
    step = length / size
    value = 0.5 * step
    result = []
    for _ in range(size):
        result.append(min(length - 1, math.floor(value)))
        value += step
    return result

def canonical_image(path):
    from PIL import Image, ImageOps
    with Image.open(path) as source:
        require(getattr(source, 'n_frames', 1) == 1, 'Animated images require a reviewed still export: ' + str(path))
        require(source.format in {'JPEG', 'PNG', 'WEBP', 'BMP'}, 'Unsupported training format: ' + str(path))
        if 'A' in source.getbands() or 'transparency' in source.info:
            require(source.convert('RGBA').getchannel('A').getextrema() == (255, 255),
                    'Transparent image requires a reviewed opaque export: ' + str(path))
        image = ImageOps.exif_transpose(source).convert('RGB')
        require(min(image.size) >= 100, 'Image short side below 100 px: ' + str(path))

        require(image.width * image.height <= 16000000,
                'Image exceeds 16 megapixels; export a reviewed smaller copy: ' + str(path))
        return image

def read_manifest(manifest):
    manifest = Path(manifest).resolve()
    with manifest.open(encoding='utf-8-sig', newline='') as handle:
        reader = csv.DictReader(handle)
        headers = reader.fieldnames or []
        require(len(headers) == len(set(headers)), 'Duplicate CSV column names')
        require({'path', 'label', 'split', 'group'} <= set(reader.fieldnames or []),
                'Missing CSV columns: path,label,split,group')
        rows = list(reader)
    require(rows, 'Empty dataset')
    groups, hashes, paths, counts = {}, {}, set(), Counter()
    for line, row in enumerate(rows, 2):
        require(None not in row, 'Extra CSV fields at line ' + str(line))
        for key in ('path', 'label', 'split', 'group'):
            require(isinstance(row.get(key), str) and row[key].strip(),
                    'Missing ' + key + ' at line ' + str(line))
            row[key] = row[key].strip()
        require(row['label'] in LABELS, 'Unknown label: ' + row['label'])
        require(row['split'] in SPLITS, 'Invalid split: ' + row['split'])
        path = Path(row['path'])
        if not path.is_absolute():
            path = manifest.parent / path
        path = path.resolve()
        require(path.is_file(), 'Missing image: ' + str(path))
        require(path not in paths, 'Duplicate file path: ' + str(path))
        paths.add(path)
        require(groups.setdefault(row['group'], row['split']) == row['split'],
                'Group leakage: ' + row['group'])
        image = canonical_image(path)
        digest = hashlib.sha256(str(image.size).encode('ascii') + image.tobytes()).hexdigest()
        image.close()
        require(digest not in hashes,
                'Duplicate decoded image: ' + str(path) + ' and ' + hashes.get(digest, ''))
        hashes[digest] = str(path)
        row['path'] = str(path)
        row['sha256_rgb'] = digest
        counts[(row['split'], row['label'])] += 1
    for split in SPLITS:
        for label in LABELS:
            require(counts[(split, label)] > 0, 'Missing ' + split + '/' + label)
    audit = {
        'validation_only': True,
        'training_executed': False,
        'samples': len(rows),
        'groups': len(groups),
        'class_order': LABELS,
        'counts': {split: {label: counts[(split, label)] for label in LABELS} for split in SPLITS},
        'manifest_sha256': hashlib.sha256(manifest.read_bytes()).hexdigest(),
        'preprocessing': PREPROCESSING,
        'warnings': [
            'Exact decoded duplicates and group leakage are rejected; near-duplicates require review.',
            'Every class being present is a validity check, not evidence of sufficient data.',
            'Review label quality and sources; reserve independent field sessions for test.',
            'Browser/Pillow decoding, color management and EXIF parity need real-image comparison.',
        ],
    }
    return rows, counts, audit

def browser_pixels(path):
    import numpy as np
    image = canonical_image(path)
    try:
        rgb = np.asarray(image)
        xs, ys = nearest_indices(image.width), nearest_indices(image.height)
        return rgb[np.asarray(ys)[:, None], np.asarray(xs)[None, :], :].astype(np.float32) / np.float32(255)
    finally:
        image.close()

def classification_metrics(probabilities, truth):
    import numpy as np
    probabilities = np.asarray(probabilities)
    truth = np.asarray(truth)
    require(probabilities.shape == (len(truth), len(LABELS)), 'Unexpected probability shape')
    require(np.isfinite(probabilities).all() and (probabilities >= 0).all(), 'Invalid probabilities')
    require(np.allclose(probabilities.sum(axis=1), 1, atol=1e-4), 'Probability sums not one')
    predicted = probabilities.argmax(axis=1)
    cm = np.zeros((len(LABELS), len(LABELS)), dtype=int)
    for actual, guess in zip(truth, predicted):
        cm[actual, guess] += 1
    recalls = np.divide(np.diag(cm), cm.sum(axis=1), out=np.zeros(len(LABELS)), where=cm.sum(axis=1) > 0)
    precision = np.divide(np.diag(cm), cm.sum(axis=0), out=np.zeros(len(LABELS)), where=cm.sum(axis=0) > 0)
    f1 = np.divide(2 * precision * recalls, precision + recalls,
                   out=np.zeros(len(LABELS)), where=precision + recalls > 0)
    confidence = probabilities.max(axis=1)
    correct = predicted == truth
    ece = 0.0
    for index in range(10):
        lo, hi = index / 10, (index + 1) / 10
        mask = (confidence >= lo) & ((confidence < hi) if index < 9 else (confidence <= 1))
        if mask.any():
            ece += float(mask.mean()) * abs(float(correct[mask].mean()) - float(confidence[mask].mean()))
    return {
        'accuracy': float(correct.mean()), 'macro_f1': float(f1.mean()),
        'ece_10_bins': ece, 'per_class_recall': dict(zip(LABELS, recalls.tolist())),
        'confusion_matrix': cm.tolist(), 'test_samples': len(truth),
    }

def train(args, rows, counts, audit):
    import numpy as np
    try:
        import tensorflow as tf
    except ImportError as error:
        raise RuntimeError('TensorFlow is unavailable. Use --validate-only or an isolated compatible ML environment.') from error
    tf.keras.utils.set_random_seed(args.seed)
    try:
        tf.config.experimental.enable_op_determinism()
    except (AttributeError, RuntimeError):
        pass

    def dataset(split):
        chosen = [row for row in rows if row['split'] == split]
        def generate():
            for row in chosen:
                yield browser_pixels(row['path']), LABELS.index(row['label'])
        ds = tf.data.Dataset.from_generator(generate, output_signature=(
            tf.TensorSpec((224, 224, 3), tf.float32), tf.TensorSpec((), tf.int32)))
        if split == 'train':
            ds = ds.shuffle(len(chosen), seed=args.seed, reshuffle_each_iteration=True)
        return ds.batch(args.batch).prefetch(tf.data.AUTOTUNE), chosen

    train_data, _ = dataset('train')
    val_data, _ = dataset('val')
    test_data, test_rows = dataset('test')

    backbone = tf.keras.applications.MobileNetV2(
        input_shape=(224, 224, 3), alpha=.5, include_top=False, weights='imagenet')
    backbone.trainable = False
    inputs = tf.keras.Input(shape=(224, 224, 3), name='image_rgb_0_1')

    normalize = tf.keras.layers.Conv2D(3, 1, trainable=False, name='fixed_rgb_normalization')
    x = normalize(inputs)
    normalize.set_weights([np.eye(3, dtype=np.float32).reshape(1, 1, 3, 3) * 2,
                           np.full(3, -1, dtype=np.float32)])
    x = backbone(x, training=False)
    x = tf.keras.layers.GlobalAveragePooling2D(name='pooled_features')(x)
    x = tf.keras.layers.Dropout(.25, name='head_dropout')(x)
    outputs = tf.keras.layers.Dense(len(LABELS), activation='softmax', name='probabilities')(x)
    candidate = tf.keras.Model(inputs, outputs, name='caykhoeai_candidate_05')
    raw = tf.keras.Input(shape=(224, 224, 3), name='training_image')
    augmentation = tf.keras.Sequential([
        tf.keras.layers.RandomFlip('horizontal'),
        tf.keras.layers.RandomRotation(.06),
        tf.keras.layers.RandomContrast(.15),
    ], name='training_only_augmentation')
    trainer = tf.keras.Model(raw, candidate(augmentation(raw)))

    def compile_trainer(rate):
        trainer.compile(optimizer=tf.keras.optimizers.Adam(rate),
                        loss='sparse_categorical_crossentropy', metrics=['accuracy'])

    def callbacks():
        return [tf.keras.callbacks.EarlyStopping(monitor='val_loss', patience=5, restore_best_weights=True),
                tf.keras.callbacks.ReduceLROnPlateau(monitor='val_loss', factor=.5, patience=2)]

    total = sum(counts[('train', label)] for label in LABELS)
    class_weight = {i: total / (len(LABELS) * counts[('train', label)]) for i, label in enumerate(LABELS)}
    compile_trainer(1e-3)
    head_fit = trainer.fit(train_data, validation_data=val_data, epochs=args.epochs,
                           class_weight=class_weight, callbacks=callbacks())
    head_weights = candidate.get_weights()
    head_val = float(trainer.evaluate(val_data, verbose=0)[0])
    fine_fit, selected = None, 'frozen_backbone'
    if args.fine_epochs > 0:
        backbone.trainable = True
        for layer in backbone.layers[:-30]:
            layer.trainable = False
        for layer in backbone.layers:
            if isinstance(layer, tf.keras.layers.BatchNormalization):
                layer.trainable = False
        compile_trainer(1e-5)
        fine_fit = trainer.fit(train_data, validation_data=val_data, epochs=args.fine_epochs,
                               class_weight=class_weight, callbacks=callbacks())
        if float(trainer.evaluate(val_data, verbose=0)[0]) > head_val:
            candidate.set_weights(head_weights)
        else:
            selected = 'fine_tuned_backbone'

    probabilities = candidate.predict(test_data, verbose=0)
    truth = np.asarray([LABELS.index(row['label']) for row in test_rows])
    metrics = classification_metrics(probabilities, truth)
    metrics.update({
        'candidate_only': True, 'trained_from': 'ImageNet MobileNetV2 alpha=0.5',
        'selected_stage': selected, 'parameter_count': candidate.count_params(),
        'seed': args.seed, 'preprocessing': PREPROCESSING,
        'environment': {'python': platform.python_version(), 'tensorflow': tf.__version__, 'numpy': np.__version__},
        'gate': 'Compare original on same independent field test set; TF.js conversion, decoding/parity, mobile latency and OOD tests required before deployment.',
    })
    candidate.save(args.output / 'candidate.keras')
    write_json(args.output / 'labels.json', LABELS)
    write_json(args.output / 'evaluation.json', metrics)
    write_json(args.output / 'training_history.json', {
        'head': head_fit.history, 'fine_tune': fine_fit.history if fine_fit else None,
    })
    with (args.output / 'test_predictions.csv').open('w', encoding='utf-8', newline='') as handle:
        writer = csv.writer(handle)
        writer.writerow(['path', 'group', 'actual', 'predicted', *LABELS])
        for row, probs in zip(test_rows, probabilities):
            writer.writerow([row['path'], row['group'], row['label'], LABELS[int(probs.argmax())], *probs.tolist()])
    audit['training_executed'] = True
    audit['validation_only'] = False
    write_json(args.output / 'dataset_audit.json', audit)
    print(json.dumps(metrics, ensure_ascii=False, indent=2))

def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--validate-only', action='store_true', help='Audit data without importing TensorFlow or training')
    parser.add_argument('--epochs', type=int, default=25)
    parser.add_argument('--fine-epochs', type=int, default=10)
    parser.add_argument('--batch', type=int, default=24)
    parser.add_argument('--seed', type=int, default=5243)
    args = parser.parse_args()
    try:
        require(args.epochs > 0 and args.fine_epochs >= 0 and args.batch > 0, 'Invalid epochs or batch size')
        require(not args.output.exists(),
                'Output must be a new folder; existing paths are never overwritten.')
        rows, counts, audit = read_manifest(args.manifest)

        args.output.mkdir(parents=True, exist_ok=False)
        write_json(args.output / 'dataset_audit.json', audit)
        if args.validate_only:
            print(json.dumps(audit, ensure_ascii=False, indent=2))
        else:
            train(args, rows, counts, audit)
    except (ValueError, OSError, RuntimeError) as error:
        parser.exit(2, 'Error: ' + str(error) + '\n')

if __name__ == '__main__':
    main()
