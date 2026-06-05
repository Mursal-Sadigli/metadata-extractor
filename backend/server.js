const express = require('express');
const multer = require('multer');
const cors = require('cors');
const crypto = require('crypto');
const { spawn } = require('child_process');
const path = require('path');
const fs = require('fs');
const os = require('os');

/** Layihə kökündəki .env (Python ilə eyni) */
function loadEnvFile() {
    const envPath = path.join(__dirname, '..', '.env');
    if (!fs.existsSync(envPath)) return;
    try {
        for (const line of fs.readFileSync(envPath, 'utf8').split('\n')) {
            const trimmed = line.trim();
            if (!trimmed || trimmed.startsWith('#') || !trimmed.includes('=')) continue;
            const eq = trimmed.indexOf('=');
            const key = trimmed.slice(0, eq).trim();
            let val = trimmed.slice(eq + 1).trim().replace(/^["']|["']$/g, '');
            if (key && process.env[key] === undefined) process.env[key] = val;
        }
    } catch (_) { /* ignore */ }
}
loadEnvFile();

const app = express();
const port = Number(process.env.PORT) || 3001;
const PYTHON_BIN = process.env.PYTHON_BIN || (process.platform === 'win32' ? 'python' : 'python3');

app.use(cors({
    origin: true,
    credentials: true,
    allowedHeaders: ['Content-Type', 'x-auth-token', 'Authorization'],
    methods: ['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'],
}));
app.use(express.json());

/** Admin girişi — API qorunması */
const ADMIN_PASSWORD = process.env.ADMIN_PASSWORD || '482916';
const authTokens = new Map();
const AUTH_TTL_MS = 24 * 60 * 60 * 1000;

function issueAuthToken() {
    const token = crypto.randomBytes(24).toString('hex');
    authTokens.set(token, Date.now() + AUTH_TTL_MS);
    return token;
}

function isValidAuthToken(token) {
    if (!token || !authTokens.has(token)) return false;
    if (Date.now() > authTokens.get(token)) {
        authTokens.delete(token);
        return false;
    }
    return true;
}

app.use('/api', (req, res, next) => {
    if (req.method === 'OPTIONS') return next();
    if (req.method === 'GET' && req.path === '/health') {
        return res.json({ ok: true });
    }
    if (req.method === 'POST' && req.path === '/auth/login') {
        const password = String(req.body?.password || '');
        if (password === ADMIN_PASSWORD) {
            const token = issueAuthToken();
            console.log('[+] Admin girişi uğurlu');
            return res.json({ ok: true, token });
        }
        console.log('[-] Admin giriş cəhdi — səhv parol');
        return res.status(401).json({ error: 'Parol səhvdir' });
    }
    const token = req.headers['x-auth-token'];
    if (isValidAuthToken(token)) return next();
    return res.status(401).json({ error: 'Giriş lazımdır', code: 'unauthorized' });
});

/** Müvəqqəti yükləmələr — layihə uploads/ qovluğuna yazılmır */
const uploadDir = path.join(os.tmpdir(), 'metadata-extractor-uploads');

function ensureUploadDir() {
    if (!fs.existsSync(uploadDir)) {
        fs.mkdirSync(uploadDir, { recursive: true });
    }
}

function clearUploadDir() {
    try {
        if (!fs.existsSync(uploadDir)) return;
        for (const name of fs.readdirSync(uploadDir)) {
            try {
                fs.rmSync(path.join(uploadDir, name), { recursive: true, force: true });
            } catch (_) { /* ignore */ }
        }
    } catch (_) { /* ignore */ }
}

ensureUploadDir();
clearUploadDir();

function publicUploadUrl(filename) {
    const pubBase = process.env.PUBLIC_APP_URL || process.env.PUBLIC_IMAGE_BASE_URL;
    const base = pubBase
        ? pubBase.replace(/\/$/, '')
        : `http://localhost:${port}`;
    return `${base}/uploads/${path.basename(filename)}`;
}

// Şəkil önizləməsi (yalnız aktiv sessiya üçün)
app.use('/uploads', express.static(uploadDir));

const storage = multer.diskStorage({
    destination: (req, file, cb) => {
        cb(null, uploadDir);
    },
    filename: (req, file, cb) => {
        const uniqueSuffix = Date.now() + '-' + Math.round(Math.random() * 1E9);
        cb(null, uniqueSuffix + '-' + file.originalname.replace(/[^a-zA-Z0-9.]/g, '_'));
    }
});

const upload = multer({ storage: storage });
const uploadZip = multer({
    storage: multer.diskStorage({
        destination: (req, file, cb) => cb(null, uploadDir),
        filename: (req, file, cb) => {
            const uniqueSuffix = Date.now() + '-' + Math.round(Math.random() * 1E9);
            cb(null, uniqueSuffix + '-archive.zip');
        }
    })
});

function parsePythonJson(stdoutData) {
    let str = stdoutData.trim();
    if (!str) return null;
    try {
        return JSON.parse(str);
    } catch (e) {
        const lines = str.split('\n');
        for (let i = 0; i < lines.length; i++) {
            const possibleJson = lines.slice(i).join('\n').trim();
            try {
                return JSON.parse(possibleJson);
            } catch (err) {
                const firstChar = possibleJson[0];
                if (firstChar === '{' || firstChar === '[') {
                    const lastChar = firstChar === '{' ? '}' : ']';
                    const lastIdx = possibleJson.lastIndexOf(lastChar);
                    if (lastIdx > 0) {
                        try {
                            return JSON.parse(possibleJson.substring(0, lastIdx + 1));
                        } catch (err2) {}
                    }
                }
            }
        }
    }
    return null;
}

function runPython(args, label, res) {
    const pythonCoreDir = path.join(__dirname, '..', 'python-core');
    const mainPyPath = path.join(pythonCoreDir, 'main.py');
    const pythonProcess = spawn(PYTHON_BIN, [mainPyPath, ...args], {
        cwd: pythonCoreDir,
        env: { ...process.env, PYTHONIOENCODING: 'utf-8' },
    });

    let stdoutData = '';
    let stderrData = '';

    pythonProcess.stdout.on('data', (data) => { stdoutData += data.toString(); });
    pythonProcess.stderr.on('data', (data) => {
        stderrData += data.toString();
        process.stdout.write(`[Python ${label}] ${data}`);
    });

    pythonProcess.on('close', (code) => {
        if (code !== 0 && stdoutData.trim() === '') {
            return res.status(500).json({ error: 'Analiz xətası', details: stderrData });
        }
        const result = parsePythonJson(stdoutData);
        if (!result) {
            console.error(`[-] JSON parse (${label}):`, stdoutData.slice(0, 500));
            return res.status(500).json({
                error: 'Python çıxışı oxuna bilmədi',
                details: stderrData || stdoutData.slice(0, 300),
            });
        }
        // API xətası JSON içindədirsə də 200 qaytar (UI göstərsin)
        res.json(result);
    });
}

// Müvəqqəti faylları təmizlə (səhifə yenilənməsi / sessiya bitməsi)
app.post('/api/cleanup-uploads', (req, res) => {
    clearUploadDir();
    ensureUploadDir();
    console.log('[~] Müvəqqəti yükləmələr təmizləndi');
    res.json({ ok: true });
});

// 1. Fayl Yükləmə (Analiz etmir, yalnız yadda saxlayır)
app.post('/api/upload', upload.single('file'), (req, res) => {
    if (!req.file) {
        return res.status(400).json({ error: 'Fayl yüklənmədi' });
    }
    console.log(`[+] Yükləndi: ${req.file.filename}`);
    res.json({ 
        filename: req.file.filename, 
        originalName: req.file.originalname,
        url: publicUploadUrl(req.file.filename),
    });
});

// 2. Analiz Endpoint-i (Tək-tək analiz üçün)
app.post('/api/analyze', (req, res) => {
    const { filename, type } = req.body; // type: 'exif', 'location', 'ai'
    
    if (!filename || !type) {
        return res.status(400).json({ error: 'Fayl adı və ya analiz növü yoxdur' });
    }

    const filePath = path.join(uploadDir, filename);
    if (!fs.existsSync(filePath)) {
        return res.status(404).json({ error: 'Fayl tapılmadı (Silinmiş ola bilər)' });
    }

    const pythonCoreDir = path.join(__dirname, '..', 'python-core');
    const mainPyPath = path.join(pythonCoreDir, 'main.py');

    console.log(`[>>] Analiz başlayır (${type}): ${filename}`);

    const extraArgs = [];
    if (req.body.video_frame != null) {
        extraArgs.push('--video-frame', String(req.body.video_frame));
    }
    if (req.body.location_text) {
        extraArgs.push('--text', String(req.body.location_text));
    }

    const pythonProcess = spawn(PYTHON_BIN, [
        mainPyPath, 
        filePath, 
        '--only', type, 
        '--format', 'json', 
        '--quiet',
        ...extraArgs,
    ], {
        cwd: pythonCoreDir,
        env: { ...process.env, PYTHONIOENCODING: 'utf-8' },
    });

    let stdoutData = '';
    let stderrData = '';

    pythonProcess.stdout.on('data', (data) => {
        stdoutData += data.toString();
    });

    pythonProcess.stderr.on('data', (data) => {
        stderrData += data.toString();
        process.stdout.write(`[Python ${type}] ${data}`);
    });

    pythonProcess.on('close', (code) => {
        if (code !== 0 && stdoutData.trim() === '') {
            return res.status(500).json({ 
                error: 'Analiz zamanı xəta baş verdi', 
                details: stderrData 
            });
        }

        const result = parsePythonJson(stdoutData);
        if (!result) {
            console.error('Gələn data:', stdoutData);
            return res.status(500).json({ error: 'Python çıxışı oxuna bilmədi' });
        }
        console.log(`[OK] Analiz bitdi (${type}): ${filename}`);
        res.json(result);
    });
});

function readUploadSidecarUrls(filename) {
    try {
        const safe = path.basename(String(filename));
        const sidecarPath = path.join(uploadDir, safe.replace(/\.[^.]+$/, '') + '.source.json');
        if (!fs.existsSync(sidecarPath)) return {};
        const sc = JSON.parse(fs.readFileSync(sidecarPath, 'utf8'));
        return {
            source_url: sc.source_url || null,
            resolved_url: sc.resolved_url || null,
        };
    } catch {
        return {};
    }
}

function resolvePublicImageUrl(filename, bodyUrl) {
    const sidecar = readUploadSidecarUrls(filename);
    const isLocal = (u) => !u || /localhost|127\.0\.0\.1/i.test(String(u));
    if (bodyUrl && !isLocal(bodyUrl)) return bodyUrl;
    if (sidecar.resolved_url && !isLocal(sidecar.resolved_url)) return sidecar.resolved_url;
    if (sidecar.source_url && !isLocal(sidecar.source_url)) return sidecar.source_url;
    const pubBase = process.env.PUBLIC_APP_URL || process.env.PUBLIC_IMAGE_BASE_URL;
    if (pubBase) {
        return `${pubBase.replace(/\/$/, '')}/uploads/${path.basename(filename)}`;
    }
    return null;
}

app.post('/api/propagation-analysis', (req, res) => {
    const { filename, public_image_url } = req.body;
    if (!filename) {
        return res.status(400).json({ error: 'Fayl adı lazımdır' });
    }
    const safe = path.basename(String(filename));
    const filePath = path.join(uploadDir, safe);
    if (!fs.existsSync(filePath)) {
        return res.status(404).json({ error: 'Fayl tapılmadı' });
    }
    const autoPublic = resolvePublicImageUrl(safe, public_image_url);
    const args = [filePath, '--only', 'propagation', '--format', 'json', '--quiet'];
    console.log(`[>>] Yayılma analizi (tam): ${safe}`);
    const pythonCoreDir = path.join(__dirname, '..', 'python-core');
    const mainPyPath = path.join(pythonCoreDir, 'main.py');
    const env = {
        ...process.env,
        PYTHONIOENCODING: 'utf-8',
        PUBLIC_APP_URL: process.env.PUBLIC_APP_URL || process.env.PUBLIC_IMAGE_BASE_URL || '',
    };
    const pythonProcess = spawn(PYTHON_BIN, [mainPyPath, ...args], {
        cwd: pythonCoreDir,
        env,
    });
    let stdoutData = '';
    let stderrData = '';
    const timeoutMs = 240000;
    const timer = setTimeout(() => {
        pythonProcess.kill();
        if (!res.headersSent) {
            res.status(504).json({ error: 'Yayılma analizi vaxtı keçdi (4 dəq)' });
        }
    }, timeoutMs);
    pythonProcess.stdout.on('data', (d) => { stdoutData += d.toString(); });
    pythonProcess.stderr.on('data', (d) => {
        stderrData += d.toString();
        process.stdout.write(`[Python propagation] ${d}`);
    });
    pythonProcess.on('close', (code) => {
        clearTimeout(timer);
        if (res.headersSent) return;
        if (code !== 0 && stdoutData.trim() === '') {
            return res.status(500).json({ error: 'Yayılma analizi xətası', details: stderrData });
        }
        const result = parsePythonJson(stdoutData);
        if (!result) {
            return res.status(500).json({ error: 'Python çıxışı oxuna bilmədi', details: stderrData });
        }
        const payload = result.image_propagation || result;
        if (autoPublic && payload && !payload.public_image_url) {
            payload.public_image_url = autoPublic;
        }
        res.json(payload);
    });
});

app.post('/api/reverse-image-search', (req, res) => {
    const { filename, public_image_url } = req.body;
    if (!filename) {
        return res.status(400).json({ error: 'Fayl adı lazımdır' });
    }
    const safe = path.basename(String(filename));
    const filePath = path.join(uploadDir, safe);
    if (!fs.existsSync(filePath)) {
        return res.status(404).json({ error: 'Fayl tapılmadı' });
    }
    const autoPublic = resolvePublicImageUrl(safe, public_image_url);
    const args = [filePath, '--only', 'reverse_image', '--format', 'json', '--quiet'];
    console.log(`[>>] Tərs şəkil axtarışı: ${safe}`);
    const pythonCoreDir = path.join(__dirname, '..', 'python-core');
    const mainPyPath = path.join(pythonCoreDir, 'main.py');
    const env = {
        ...process.env,
        PYTHONIOENCODING: 'utf-8',
        PUBLIC_APP_URL: process.env.PUBLIC_APP_URL || process.env.PUBLIC_IMAGE_BASE_URL || '',
    };
    const pythonProcess = spawn(PYTHON_BIN, [mainPyPath, ...args], {
        cwd: pythonCoreDir,
        env,
    });
    let stdoutData = '';
    let stderrData = '';
    const timeoutMs = 180000;
    const timer = setTimeout(() => {
        pythonProcess.kill();
        if (!res.headersSent) {
            res.status(504).json({ error: 'Tərs şəkil axtarışı vaxtı keçdi (3 dəq)' });
        }
    }, timeoutMs);
    pythonProcess.stdout.on('data', (d) => { stdoutData += d.toString(); });
    pythonProcess.stderr.on('data', (d) => {
        stderrData += d.toString();
        process.stdout.write(`[Python reverse_image] ${d}`);
    });
    pythonProcess.on('close', (code) => {
        clearTimeout(timer);
        if (res.headersSent) return;
        if (code !== 0 && stdoutData.trim() === '') {
            return res.status(500).json({ error: 'Axtarış xətası', details: stderrData });
        }
        const result = parsePythonJson(stdoutData);
        if (!result) {
            return res.status(500).json({ error: 'Python çıxışı oxuna bilmədi', details: stderrData });
        }
        const payload = result.reverse_image_search || result;
        if (autoPublic && payload && !payload.public_image_url) {
            payload.public_image_url = autoPublic;
        }
        res.json(payload);
    });
});

app.post('/api/timeline-mapping', (req, res) => {
    const { filenames } = req.body;
    if (!Array.isArray(filenames) || filenames.length < 2) {
        return res.status(400).json({ error: 'Ən azı 2 fayl adı lazımdır' });
    }
    const paths = [];
    const missing = [];
    for (const name of filenames.slice(0, 100)) {
        const safe = path.basename(String(name));
        const filePath = path.join(uploadDir, safe);
        if (fs.existsSync(filePath)) {
            paths.push(filePath);
        } else {
            missing.push(safe);
        }
    }
    if (paths.length < 2) {
        return res.status(400).json({
            error: 'Ən azı 2 mövcud şəkil lazımdır',
            missing,
        });
    }
    console.log(`[>>] Timeline mapping: ${paths.length} fayl`);
    runPython(['--timeline', ...paths, '--format', 'json', '--quiet'], 'timeline', res);
});

app.post('/api/compare', (req, res) => {
    const { filenameA, filenameB } = req.body;
    if (!filenameA || !filenameB) {
        return res.status(400).json({ error: 'İki fayl adı lazımdır' });
    }
    const pathA = path.join(uploadDir, filenameA);
    const pathB = path.join(uploadDir, filenameB);
    if (!fs.existsSync(pathA) || !fs.existsSync(pathB)) {
        return res.status(404).json({ error: 'Fayllardan biri tapılmadı' });
    }
    console.log(`[>>] Müqayisə: ${filenameA} vs ${filenameB}`);
    runPython(['--compare', pathA, pathB, '--format', 'json', '--quiet'], 'compare', res);
});

app.post('/api/analyze-archive', uploadZip.single('file'), (req, res) => {
    if (!req.file) {
        return res.status(400).json({ error: 'ZIP yüklənmədi' });
    }
    const zipPath = path.join(uploadDir, req.file.filename);
    console.log(`[>>] Arxiv analizi: ${req.file.filename}`);
    runPython(['--archive', zipPath, '--format', 'json', '--quiet'], 'archive', res);
});

app.post('/api/face-privacy', (req, res) => {
    const { filename, anonymize, method, strength, video_frame } = req.body;
    if (!filename) {
        return res.status(400).json({ error: 'Fayl adı lazımdır' });
    }
    const filePath = path.join(uploadDir, filename);
    if (!fs.existsSync(filePath)) {
        return res.status(404).json({ error: 'Fayl tapılmadı' });
    }
    const args = [filePath, '--only', 'faces', '--format', 'json', '--quiet'];
    if (video_frame != null) {
        args.push('--video-frame', String(video_frame));
    }
    if (anonymize) {
        args.push('--anonymize');
        if (method === 'pixelate' || method === 'blur') {
            args.push('--anon-method', method);
        }
        if (strength != null) {
            args.push('--anon-strength', String(Math.min(5, Math.max(1, Number(strength) || 3))));
        }
    }
    console.log(`[>>] Üz məxfiliyi: ${filename}${anonymize ? ' (anonim)' : ''}`);
    runPython(args, 'faces', res);
});

app.post('/api/object-detection', (req, res) => {
    const { filename, confidence, video_frame } = req.body;
    if (!filename) {
        return res.status(400).json({ error: 'Fayl adı lazımdır' });
    }
    const filePath = path.join(uploadDir, filename);
    if (!fs.existsSync(filePath)) {
        return res.status(404).json({ error: 'Fayl tapılmadı' });
    }
    const args = [filePath, '--only', 'objects', '--format', 'json', '--quiet'];
    if (video_frame != null) {
        args.push('--video-frame', String(video_frame));
    }
    if (confidence != null) {
        const c = Math.min(0.9, Math.max(0.1, Number(confidence) || 0.16));
        args.push('--object-confidence', String(c));
    }
    console.log(`[>>] Obyekt aşkarlanması (YOLO/COCO): ${filename}`);
    runPython(args, 'objects', res);
});

app.post('/api/vision-ml', (req, res) => {
    const { filename, confidence, video_frame } = req.body;
    if (!filename) {
        return res.status(400).json({ error: 'Fayl adı lazımdır' });
    }
    const filePath = path.join(uploadDir, path.basename(filename));
    if (!fs.existsSync(filePath)) {
        return res.status(404).json({ error: 'Fayl tapılmadı' });
    }
    const args = [filePath, '--only', 'vision', '--format', 'json', '--quiet'];
    if (confidence != null) {
        args.push('--object-confidence', String(Math.min(0.9, Math.max(0.1, Number(confidence) || 0.16))));
    }
    if (video_frame != null) {
        args.push('--video-frame', String(Number(video_frame) || 0));
    }
    console.log(`[>>] Computer Vision & ML: ${filename}`);
    const pythonCoreDir = path.join(__dirname, '..', 'python-core');
    const mainPyPath = path.join(pythonCoreDir, 'main.py');
    const pythonProcess = spawn(PYTHON_BIN, [mainPyPath, ...args], {
        cwd: pythonCoreDir,
        env: { ...process.env, PYTHONIOENCODING: 'utf-8' },
    });
    let stdoutData = '';
    let stderrData = '';
    const timeoutMs = 600000;
    const timer = setTimeout(() => {
        pythonProcess.kill();
        if (!res.headersSent) {
            res.status(504).json({ error: 'Computer Vision analizi vaxtı keçdi (10 dəq)' });
        }
    }, timeoutMs);
    pythonProcess.stdout.on('data', (d) => { stdoutData += d.toString(); });
    pythonProcess.stderr.on('data', (d) => {
        stderrData += d.toString();
        process.stdout.write(`[Python vision] ${d}`);
    });
    pythonProcess.on('close', (code) => {
        clearTimeout(timer);
        if (res.headersSent) return;
        if (code !== 0 && stdoutData.trim() === '') {
            return res.status(500).json({ error: 'Vision analizi xətası', details: stderrData });
        }
        const result = parsePythonJson(stdoutData);
        if (!result) {
            return res.status(500).json({ error: 'Python çıxışı oxuna bilmədi', details: stderrData });
        }
        res.json(result);
    });
});

app.post('/api/restore-analyze', (req, res) => {
    const { filename, extra_text } = req.body;
    if (!filename) {
        return res.status(400).json({ error: 'Fayl adı lazımdır' });
    }
    const filePath = path.join(uploadDir, path.basename(filename));
    if (!fs.existsSync(filePath)) {
        return res.status(404).json({ error: 'Fayl tapılmadı' });
    }
    const args = [filePath, '--only', 'restore', '--format', 'json', '--quiet'];
    if (extra_text) {
        args.push('-t', String(extra_text));
    }
    console.log(`[>>] Şəkil bərpası + metadata/lokasiya: ${filename}`);
    const pythonCoreDir = path.join(__dirname, '..', 'python-core');
    const mainPyPath = path.join(pythonCoreDir, 'main.py');
    const pythonProcess = spawn(PYTHON_BIN, [mainPyPath, ...args], {
        cwd: pythonCoreDir,
        env: { ...process.env, PYTHONIOENCODING: 'utf-8' },
    });
    let stdoutData = '';
    let stderrData = '';
    const timeoutMs = 600000;
    const timer = setTimeout(() => {
        pythonProcess.kill();
        if (!res.headersSent) {
            res.status(504).json({ error: 'Bərpa analizi vaxtı keçdi (10 dəq)' });
        }
    }, timeoutMs);
    pythonProcess.stdout.on('data', (d) => { stdoutData += d.toString(); });
    pythonProcess.stderr.on('data', (d) => {
        stderrData += d.toString();
        process.stdout.write(`[Python restore] ${d}`);
    });
    pythonProcess.on('close', (code) => {
        clearTimeout(timer);
        if (res.headersSent) return;
        if (code !== 0 && stdoutData.trim() === '') {
            return res.status(500).json({ error: 'Bərpa analizi xətası', details: stderrData });
        }
        const result = parsePythonJson(stdoutData);
        if (!result) {
            return res.status(500).json({ error: 'Python çıxışı oxuna bilmədi', details: stderrData });
        }
        res.json(result);
    });
});

app.post('/api/video-tracking', (req, res) => {
    const {
        filename,
        tracker,
        enable_face_reid,
        anonymize_first,
        method,
        strength,
        confidence,
        sample_fps,
        max_duration_sec,
    } = req.body;
    if (!filename) {
        return res.status(400).json({ error: 'Fayl adı lazımdır' });
    }
    const filePath = path.join(uploadDir, path.basename(filename));
    if (!fs.existsSync(filePath)) {
        return res.status(404).json({ error: 'Fayl tapılmadı' });
    }
    const args = [filePath, '--only', 'tracking', '--format', 'json', '--quiet'];
    if (tracker === 'botsort' || tracker === 'bytetrack') {
        args.push('--tracker', tracker);
    }
    if (enable_face_reid) {
        args.push('--face-reid');
    }
    if (anonymize_first) {
        args.push('--anonymize');
        if (method === 'pixelate' || method === 'blur') {
            args.push('--anon-method', method);
        }
        if (strength != null) {
            args.push('--anon-strength', String(Math.min(5, Math.max(1, Number(strength) || 3))));
        }
    }
    if (confidence != null) {
        args.push('--object-confidence', String(Math.min(0.9, Math.max(0.1, Number(confidence) || 0.16))));
    }
    if (sample_fps != null) {
        args.push('--sample-fps', String(Number(sample_fps) || 2));
    }
    if (max_duration_sec != null) {
        args.push('--max-duration', String(Number(max_duration_sec) || 120));
    }
    console.log(`[>>] Video MOT: ${filename}${anonymize_first ? ' (anonim)' : ''}${enable_face_reid ? ' + re-id' : ''}`);

    const pythonCoreDir = path.join(__dirname, '..', 'python-core');
    const mainPyPath = path.join(pythonCoreDir, 'main.py');
    const pythonProcess = spawn(PYTHON_BIN, [mainPyPath, ...args], {
        cwd: pythonCoreDir,
        env: { ...process.env, PYTHONIOENCODING: 'utf-8' },
    });
    let stdoutData = '';
    let stderrData = '';
    const timeoutMs = 600000;
    const timer = setTimeout(() => {
        pythonProcess.kill();
        if (!res.headersSent) {
            res.status(504).json({ error: 'Video izləmə vaxtı keçdi (10 dəq limit)' });
        }
    }, timeoutMs);
    pythonProcess.stdout.on('data', (d) => { stdoutData += d.toString(); });
    pythonProcess.stderr.on('data', (d) => {
        stderrData += d.toString();
        process.stdout.write(`[Python tracking] ${d}`);
    });
    pythonProcess.on('close', (code) => {
        clearTimeout(timer);
        if (res.headersSent) return;
        if (code !== 0 && stdoutData.trim() === '') {
            return res.status(500).json({ error: 'Video izləmə xətası', details: stderrData });
        }
        const result = parsePythonJson(stdoutData);
        if (!result) {
            return res.status(500).json({ error: 'Python çıxışı oxuna bilmədi', details: stderrData });
        }
        res.json(result);
    });
});

app.post('/api/geocode-text', (req, res) => {
    const { text } = req.body;
    if (!text || !String(text).trim()) {
        return res.status(400).json({ error: 'Mətn lazımdır (ünvan, koordinat və ya xəritə linki)' });
    }
    console.log('[>>] Mətn geocoding');
    runPython(['--geocode-text', String(text), '--format', 'json', '--quiet'], 'geocode', res);
});

app.post('/api/analyze-url', (req, res) => {
    const { url } = req.body;
    if (!url) {
        return res.status(400).json({ error: 'URL lazımdır' });
    }
    console.log(`[>>] URL metadata: ${url}`);
    runPython(['--url', url, '--only', 'social_meta', '--format', 'json', '--quiet'], 'social', res);
});

/** Google / birbaşa şəkil URL → uploads (sonra Metadata, Lokasiya və s.) */
app.post('/api/upload-from-url', (req, res) => {
    const { url } = req.body;
    if (!url || !String(url).trim()) {
        return res.status(400).json({ error: 'URL lazımdır (birbaşa şəkil linki)' });
    }
    const trimmed = String(url).trim();
    console.log(`[>>] Şəkil URL yüklənir: ${trimmed.slice(0, 120)}`);
    const pythonCoreDir = path.join(__dirname, '..', 'python-core');
    const fetchCliPath = path.join(pythonCoreDir, 'fetch_image_cli.py');
    const fetchArgs = [
        fetchCliPath,
        trimmed,
        '--upload-dir', uploadDir,
    ];
    const pythonProcess = spawn(PYTHON_BIN, fetchArgs, {
        cwd: pythonCoreDir,
        env: { ...process.env, PYTHONIOENCODING: 'utf-8' },
    });

    let stdoutData = '';
    let stderrData = '';
    pythonProcess.stderr.on('data', (d) => {
        stderrData += d.toString();
        process.stdout.write(`[Python upload-url] ${d}`);
    });
    pythonProcess.stdout.on('data', (d) => { stdoutData += d.toString(); });

    pythonProcess.on('close', async (code) => {
        const result = parsePythonJson(stdoutData);
        if (!result) {
            return res.status(500).json({
                error: 'URL yükləmə cavabı oxunmadı',
                details: stderrData || stdoutData.slice(0, 300),
            });
        }
        if (result.status !== 'success') {
            return res.status(400).json({
                error: result.error || 'Şəkil URL yüklənmədi',
                hint: result.hint,
                resolved_url: result.resolved_url,
            });
        }
        if (!fs.existsSync(path.join(uploadDir, result.filename))) {
            return res.status(500).json({ error: 'Fayl uploads qovluğunda tapılmadı' });
        }
        const savedPath = path.join(uploadDir, result.filename);
        if (result.sidecar) {
            try {
                const sidecarPath = savedPath.replace(/\.[^.]+$/, '') + '.source.json';
                fs.writeFileSync(sidecarPath, JSON.stringify(result.sidecar, null, 2), 'utf8');
            } catch (e) {
                console.warn('[!] Sidecar yazılmadı:', e.message);
            }
        }
        console.log(`[>>] URL şəkil yükləndi (analiz düymələrdən): ${result.filename}`);
        res.json({
            filename: result.filename,
            originalName: result.originalName || result.filename,
            url: publicUploadUrl(result.filename),
            source: result.source || 'image_url',
            source_url: result.source_url,
            resolved_url: result.resolved_url,
            warnings: result.warnings || [],
            note_az: result.note_az,
            size_bytes: result.size_bytes,
        });
    });
});

app.post('/api/social-meta', (req, res) => {
    const { filename, video_frame } = req.body;
    if (!filename) {
        return res.status(400).json({ error: 'filename lazımdır' });
    }
    const filePath = path.join(uploadDir, path.basename(filename));
    if (!fs.existsSync(filePath)) {
        return res.status(404).json({ error: 'Fayl tapılmadı' });
    }
    console.log(`[>>] Sosial metadata (fayl): ${filename}`);
    const args = [filePath, '--only', 'social_meta', '--format', 'json', '--quiet'];
    if (video_frame != null) {
        args.push('--video-frame', String(video_frame));
    }
    runPython(args, 'social_meta', res);
});

// 3. İnstagram Kəşfiyyat Endpoint-i
app.post('/api/instagram', (req, res) => {
    const { username, max_posts } = req.body;
    
    if (!username) {
        return res.status(400).json({ error: 'İnstagram istifadəçi adı daxil edilməyib' });
    }

    const pythonCoreDir = path.join(__dirname, '..', 'python-core');
    const mainPyPath = path.join(pythonCoreDir, 'main.py');

    console.log(`[>>] İnstagram kəşfiyyatı başlayır: @${username}`);

    const pythonArgs = [
        mainPyPath, 
        '--instagram', username, 
        '--format', 'json', 
        '--quiet'
    ];

    // max_posts parametresi varsa ekle
    if (max_posts && parseInt(max_posts) > 0) {
        pythonArgs.push('--max-posts', String(max_posts));
    }

    const pythonProcess = spawn(PYTHON_BIN, pythonArgs, { 
        cwd: pythonCoreDir,
        stdio: ['ignore', 'pipe', 'pipe'], // stdin kapalı, stdout/stderr pipe
        env: { ...process.env, PYTHONIOENCODING: 'utf-8' } // UTF-8 encoding
    });

    let stdoutData = '';
    let stderrData = '';

    pythonProcess.stdout.on('data', (data) => {
        stdoutData += data.toString();
    });

    pythonProcess.stderr.on('data', (data) => {
        stderrData += data.toString();
        process.stdout.write(`[Python IG] ${data}`);
    });

    pythonProcess.on('close', (code) => {
        if (code !== 0 && stdoutData.trim() === '') {
            return res.status(500).json({ 
                error: 'İnstagram analizi zamanı xəta baş verdi', 
                details: stderrData 
            });
        }

        try {
            let str = stdoutData.trim();
            if (!str) {
                return res.status(500).json({ error: 'Nəticə tapılmadı.' });
            }

            let result = null;
            let parsed = false;

            const lines = str.split('\n');
            for (let i = 0; i < lines.length; i++) {
                const possibleJson = lines.slice(i).join('\n').trim();
                try {
                    result = JSON.parse(possibleJson);
                    parsed = true;
                    break;
                } catch (err) {
                    const firstChar = possibleJson[0];
                    if (firstChar === '{' || firstChar === '[') {
                        const lastChar = firstChar === '{' ? '}' : ']';
                        const lastIdx = possibleJson.lastIndexOf(lastChar);
                        if (lastIdx > 0) {
                            try {
                                result = JSON.parse(possibleJson.substring(0, lastIdx + 1));
                                parsed = true;
                                break;
                            } catch (err2) {}
                        }
                    }
                }
            }

            if (!parsed) {
                throw new Error('Geçərli JSON tapılmadı');
            }
            console.log(`[OK] İnstagram kəşfiyyatı bitdi: @${username}`);
            res.json(result);
        } catch (e) {
            console.error('[-] IG JSON Parse xətası:', e);
            res.status(500).json({ error: 'Python çıxışı oxuna bilmədi' });
        }
    });
});
const server = app.listen(port, () => {
    console.log(`\n🚀 Backend server işləyir: http://localhost:${port}`);
    console.log('Dayandırmaq üçün: Ctrl+C\n');
});

server.on('error', (err) => {
    if (err.code === 'EADDRINUSE') {
        console.error(`\n❌ Port ${port} artıq istifadədədir. Köhnə serveri bağlayın:`);
        console.error(`   netstat -ano | findstr :${port}`);
        console.error('   taskkill /PID <PID> /F\n');
    } else {
        console.error('Server xətası:', err.message);
    }
    process.exit(1);
});
