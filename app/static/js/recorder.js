const recordingForm = document.querySelector("#recording-form");
const liveVideo = document.querySelector("#live-video");
const mixCanvas = document.querySelector("#mix-canvas");
const cameraPlaceholder = document.querySelector("#camera-placeholder");
const previewSection = document.querySelector("#preview-section");
const previewVideo = document.querySelector("#preview-video");
const startButton = document.querySelector("#start-button");
const pauseButton = document.querySelector("#pause-button");
const stopButton = document.querySelector("#stop-button");
const uploadButton = document.querySelector("#upload-button");
const statusMessage = document.querySelector("#status-message");
const recordingIndicator = document.querySelector("#recording-indicator");
const recordingTimer = document.querySelector("#recording-timer");
const recordingPanel = document.querySelector("#recording-panel");
const fileUploadPanel = document.querySelector("#file-upload-panel");
const recordSourceButton = document.querySelector("#record-source-button");
const fileSourceButton = document.querySelector("#file-source-button");
const fileInput = document.querySelector("#video-file-input");
const fileDropZone = document.querySelector("#file-drop-zone");
const previewTitle = document.querySelector("#preview-title");
const previewFileName = document.querySelector("#preview-file-name");
const resetMediaButton = document.querySelector("#reset-media-button");

let sourceStreams = [];
let recorderStream = null;
let mediaRecorder = null;
let recordedChunks = [];
let recordedBlob = null;
let previewUrl = null;
let drawingFrameId = null;
let timerIntervalId = null;
let recordingStartedAt = 0;
let pauseStartedAt = null;
let totalPausedMilliseconds = 0;
let durationSeconds = 0;
let usedCameraFallback = false;
let uploadedFile = null;
let activeSource = "record";

const supportedUploadTypes = new Set([
    "video/webm",
    "video/mp4",
    "video/quicktime",
    "audio/webm",
]);

function detectMediaCapabilities() {
    return {
        secureContext: window.isSecureContext,
        mediaDevices: Boolean(navigator.mediaDevices),
        getUserMedia: Boolean(navigator.mediaDevices?.getUserMedia),
        getDisplayMedia: Boolean(navigator.mediaDevices?.getDisplayMedia),
        mediaRecorder: Boolean(window.MediaRecorder),
        userAgent: navigator.userAgent,
    };
}

function supportsMediaRecording() {
    const capabilities = detectMediaCapabilities();
    return capabilities.getUserMedia && capabilities.mediaRecorder;
}

async function openSystemBrowserForRecording() {
    const desktopApi = window.pywebview?.api;
    if (!desktopApi?.open_recording_in_browser) {
        setStatus("Этот браузер не поддерживает запись медиа.", true);
        return;
    }
    try {
        const opened = await desktopApi.open_recording_in_browser();
        setStatus(opened
            ? "Студия записи открыта в системном браузере. Приложение оставьте запущенным."
            : "Не удалось открыть системный браузер.", !opened);
    } catch (error) {
        console.error("Could not open recording studio in system browser", error);
        setStatus("Не удалось открыть системный браузер.", true);
    }
}

async function reportDesktopMediaCapabilities() {
    const desktopApi = window.pywebview?.api;
    if (desktopApi?.report_media_capabilities) {
        try {
            await desktopApi.report_media_capabilities(detectMediaCapabilities());
        } catch (error) {
            console.warn("Could not report desktop media capabilities", error);
        }
    }
}

function setStatus(message, isError = false) {
    statusMessage.textContent = message;
    statusMessage.classList.toggle("error", isError);
}

function revokePreviewUrl() {
    if (previewUrl) {
        URL.revokeObjectURL(previewUrl);
        previewUrl = null;
    }
}

function resetPreparedMedia() {
    revokePreviewUrl();
    recordedBlob = null;
    uploadedFile = null;
    durationSeconds = 0;
    previewVideo.removeAttribute("src");
    previewVideo.load();
    previewSection.hidden = true;
    uploadButton.disabled = false;
    startButton.disabled = false;
    fileInput.value = "";
    if (activeSource === "record") {
        setStatus("Подготовьте контекст слева, затем включите камеру.");
    }
}

function selectSource(source) {
    if (mediaRecorder && mediaRecorder.state !== "inactive") {
        setStatus("Сначала остановите текущую запись.", true);
        return;
    }
    activeSource = source;
    resetPreparedMedia();
    const recordSelected = source === "record";
    recordingPanel.hidden = !recordSelected;
    fileUploadPanel.hidden = recordSelected;
    recordSourceButton.classList.toggle("active", recordSelected);
    fileSourceButton.classList.toggle("active", !recordSelected);
    recordSourceButton.setAttribute("aria-selected", recordSelected.toString());
    fileSourceButton.setAttribute("aria-selected", (!recordSelected).toString());
    setStatus(
        recordSelected
            ? "Подготовьте контекст слева, затем включите камеру."
            : "Заполните контекст и выберите готовое видео."
    );
}

function readMediaDuration(sourceUrl) {
    return new Promise((resolve) => {
        const finish = () => {
            const detectedDuration = Number.isFinite(previewVideo.duration)
                ? previewVideo.duration
                : 0;
            resolve(Math.round(detectedDuration * 10) / 10);
        };
        previewVideo.addEventListener("loadedmetadata", finish, { once: true });
        previewVideo.addEventListener("error", () => resolve(0), { once: true });
        previewVideo.src = sourceUrl;
    });
}

async function prepareUploadedFile(file) {
    if (!recordingForm.reportValidity()) {
        setStatus("Сначала заполните обязательные поля слева.", true);
        return;
    }
    const maxSize = Number.parseInt(fileUploadPanel.dataset.maxSize, 10);
    if (!supportedUploadTypes.has(file.type)) {
        setStatus("Выберите видео в формате WebM, MP4 или MOV.", true);
        return;
    }
    if (!file.size) {
        setStatus("Выбранный файл пуст.", true);
        return;
    }
    if (file.size > maxSize) {
        setStatus("Размер видео превышает допустимый лимит.", true);
        return;
    }

    resetPreparedMedia();
    uploadedFile = file;
    recordedBlob = file;
    previewUrl = URL.createObjectURL(file);
    durationSeconds = await readMediaDuration(previewUrl);
    previewTitle.textContent = "Видео готово к загрузке";
    previewFileName.textContent = file.name;
    previewSection.hidden = false;
    setStatus("Проверьте выбранное видео перед отправкой.");
}

function preferredMimeType() {
    const candidates = [
        "video/webm;codecs=vp9,opus",
        "video/webm;codecs=vp8,opus",
        "video/webm",
        "video/mp4",
    ];
    return candidates.find((type) => MediaRecorder.isTypeSupported(type)) || "";
}

function selectedRecordingMode() {
    return document.querySelector('input[name="recording_mode"]:checked').value;
}

function formatElapsedTime(totalSeconds) {
    const minutes = Math.floor(totalSeconds / 60).toString().padStart(2, "0");
    const seconds = Math.floor(totalSeconds % 60).toString().padStart(2, "0");
    return `${minutes}:${seconds}`;
}

function calculateDurationSeconds() {
    if (!recordingStartedAt) {
        return 0;
    }
    const activePause = pauseStartedAt ? Date.now() - pauseStartedAt : 0;
    const elapsed = Date.now() - recordingStartedAt - totalPausedMilliseconds - activePause;
    return Math.max(0, elapsed / 1000);
}

function updateTimer() {
    recordingTimer.textContent = formatElapsedTime(calculateDurationSeconds());
}

function startTimer() {
    recordingStartedAt = Date.now();
    pauseStartedAt = null;
    totalPausedMilliseconds = 0;
    durationSeconds = 0;
    updateTimer();
    timerIntervalId = window.setInterval(updateTimer, 250);
}

function stopTimer() {
    durationSeconds = Math.round(calculateDurationSeconds() * 10) / 10;
    if (timerIntervalId) {
        window.clearInterval(timerIntervalId);
        timerIntervalId = null;
    }
    updateTimer();
}

function stopMediaTracks() {
    sourceStreams.forEach((stream) => stream.getTracks().forEach((track) => track.stop()));
    sourceStreams = [];
    if (recorderStream) {
        recorderStream.getTracks().forEach((track) => track.stop());
        recorderStream = null;
    }
    if (drawingFrameId) {
        window.cancelAnimationFrame(drawingFrameId);
        drawingFrameId = null;
    }
}

function watchDisplayTrack(displayStream) {
    const displayTrack = displayStream.getVideoTracks()[0];
    displayTrack.addEventListener("ended", () => {
        if (mediaRecorder && mediaRecorder.state !== "inactive") {
            stopRecording();
            setStatus("Демонстрация экрана завершена. Запись остановлена.");
        }
    }, { once: true });
}

async function createCameraStream() {
    const stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: true });
    sourceStreams.push(stream);
    return stream;
}

async function createScreenStream() {
    const displayStream = await navigator.mediaDevices.getDisplayMedia({ video: true, audio: false });
    const microphoneStream = await navigator.mediaDevices.getUserMedia({ video: false, audio: true });
    sourceStreams.push(displayStream, microphoneStream);
    watchDisplayTrack(displayStream);
    return new MediaStream([
        ...displayStream.getVideoTracks(),
        ...microphoneStream.getAudioTracks(),
    ]);
}

async function createScreenCameraStream() {
    const displayStream = await navigator.mediaDevices.getDisplayMedia({ video: true, audio: false });
    const cameraStream = await navigator.mediaDevices.getUserMedia({ video: true, audio: true });
    sourceStreams.push(displayStream, cameraStream);
    watchDisplayTrack(displayStream);

    const screenVideo = document.createElement("video");
    const cameraVideo = document.createElement("video");
    screenVideo.srcObject = displayStream;
    cameraVideo.srcObject = cameraStream;
    screenVideo.muted = true;
    cameraVideo.muted = true;
    screenVideo.playsInline = true;
    cameraVideo.playsInline = true;
    await Promise.all([screenVideo.play(), cameraVideo.play()]);

    const screenSettings = displayStream.getVideoTracks()[0].getSettings();
    mixCanvas.width = Math.min(screenSettings.width || 1280, 1920);
    mixCanvas.height = Math.round(mixCanvas.width / (16 / 9));
    const context = mixCanvas.getContext("2d");

    function drawCompositeFrame() {
        context.drawImage(screenVideo, 0, 0, mixCanvas.width, mixCanvas.height);
        const cameraWidth = Math.round(mixCanvas.width * 0.24);
        const cameraHeight = Math.round(cameraWidth * 9 / 16);
        const inset = Math.round(mixCanvas.width * 0.025);
        const cameraX = mixCanvas.width - cameraWidth - inset;
        const cameraY = mixCanvas.height - cameraHeight - inset;
        context.fillStyle = "#ffffff";
        context.fillRect(cameraX - 4, cameraY - 4, cameraWidth + 8, cameraHeight + 8);
        context.drawImage(cameraVideo, cameraX, cameraY, cameraWidth, cameraHeight);
        drawingFrameId = window.requestAnimationFrame(drawCompositeFrame);
    }
    drawCompositeFrame();

    const canvasStream = mixCanvas.captureStream(30);
    return new MediaStream([
        ...canvasStream.getVideoTracks(),
        ...cameraStream.getAudioTracks(),
    ]);
}

async function prepareRecorderStream(mode) {
    usedCameraFallback = false;
    if (mode === "screen" || mode === "screen-camera") {
        try {
            return mode === "screen"
                ? await createScreenStream()
                : await createScreenCameraStream();
        } catch (error) {
            console.warn("Screen capture is unavailable, falling back to camera", error);
            stopMediaTracks();
            usedCameraFallback = true;
            const cameraOption = document.querySelector('input[name="recording_mode"][value="camera"]');
            if (cameraOption) {
                cameraOption.checked = true;
            }
            return createCameraStream();
        }
    }
    return createCameraStream();
}

async function startRecording() {
    activeSource = "record";
    if (!supportsMediaRecording()) {
        await openSystemBrowserForRecording();
        return;
    }
    if (!recordingForm.reportValidity()) {
        setStatus("Заполните обязательные поля перед записью.", true);
        return;
    }
    try {
        stopMediaTracks();
        recordedChunks = [];
        recordedBlob = null;
        previewSection.hidden = true;
        recorderStream = await prepareRecorderStream(selectedRecordingMode());
        liveVideo.srcObject = recorderStream;
        cameraPlaceholder.hidden = true;

        const mimeType = preferredMimeType();
        const recorderOptions = mimeType ? { mimeType } : undefined;
        mediaRecorder = new MediaRecorder(recorderStream, recorderOptions);
        mediaRecorder.addEventListener("dataavailable", (event) => {
            if (event.data.size > 0) {
                recordedChunks.push(event.data);
            }
        });
        mediaRecorder.addEventListener("stop", showPreview, { once: true });
        mediaRecorder.start(1000);
        startTimer();

        startButton.disabled = true;
        pauseButton.disabled = false;
        pauseButton.textContent = "Пауза";
        stopButton.disabled = false;
        recordingIndicator.textContent = "Запись";
        recordingIndicator.hidden = false;
        setStatus(usedCameraFallback
            ? "Экран недоступен — продолжаем запись с камеры и микрофона."
            : "Идёт запись. Можно поставить её на паузу или остановить.");
    } catch (error) {
        stopMediaTracks();
        console.error("Could not start media recording", error);
        setStatus("Не удалось получить доступ к выбранным устройствам.", true);
    }
}

function togglePause() {
    if (!mediaRecorder) {
        return;
    }
    if (mediaRecorder.state === "recording") {
        mediaRecorder.pause();
        pauseStartedAt = Date.now();
        pauseButton.textContent = "Продолжить";
        recordingIndicator.textContent = "Пауза";
        setStatus("Запись приостановлена.");
        return;
    }
    if (mediaRecorder.state === "paused") {
        mediaRecorder.resume();
        if (pauseStartedAt) {
            totalPausedMilliseconds += Date.now() - pauseStartedAt;
        }
        pauseStartedAt = null;
        pauseButton.textContent = "Пауза";
        recordingIndicator.textContent = "Запись";
        setStatus("Запись продолжена.");
    }
}

function stopRecording() {
    if (!mediaRecorder || mediaRecorder.state === "inactive") {
        return;
    }
    stopTimer();
    mediaRecorder.stop();
    pauseButton.disabled = true;
    stopButton.disabled = true;
    recordingIndicator.hidden = true;
    setStatus("Запись остановлена. Подготавливаем предварительный просмотр…");
}

function showPreview() {
    const mimeType = mediaRecorder?.mimeType || "video/webm";
    recordedBlob = new Blob(recordedChunks, { type: mimeType });
    revokePreviewUrl();
    previewUrl = URL.createObjectURL(recordedBlob);
    previewVideo.src = previewUrl;
    previewTitle.textContent = "Запись готова";
    previewFileName.textContent = "Проверьте звук и изображение";
    previewSection.hidden = false;
    startButton.disabled = false;
    pauseButton.textContent = "Пауза";
    stopMediaTracks();
    setStatus("Проверьте запись и загрузите её, если всё получилось.");
}

async function uploadRecording() {
    if (!recordedBlob) {
        setStatus("Сначала сделайте запись.", true);
        return;
    }

    uploadButton.disabled = true;
    startButton.disabled = true;
    setStatus("Загружаем видео…");

    const extension = recordedBlob.type.startsWith("video/mp4") ? "mp4"
        : recordedBlob.type === "video/quicktime" ? "mov" : "webm";
    const uploadFilename = uploadedFile?.name || `interview.${extension}`;
    const formData = new FormData(recordingForm);
    formData.delete("recording_mode");
    formData.append("duration_seconds", durationSeconds.toString());
    formData.append("video", recordedBlob, uploadFilename);

    try {
        const response = await fetch("/api/recordings", {
            method: "POST",
            body: formData,
        });
        const payload = await response.json();
        if (!response.ok) {
            throw new Error(payload.detail || "Не удалось сохранить запись.");
        }
        window.location.assign(`/recordings/${payload.public_id}`);
    } catch (error) {
        console.error("Could not upload recording", error);
        const message = error instanceof Error ? error.message : "Не удалось сохранить запись.";
        setStatus(message, true);
        uploadButton.disabled = false;
        startButton.disabled = false;
    }
}

startButton.addEventListener("click", startRecording);
pauseButton.addEventListener("click", togglePause);
stopButton.addEventListener("click", stopRecording);
uploadButton.addEventListener("click", uploadRecording);
resetMediaButton.addEventListener("click", resetPreparedMedia);
recordSourceButton.addEventListener("click", () => selectSource("record"));
fileSourceButton.addEventListener("click", () => selectSource("file"));
fileDropZone.addEventListener("click", () => fileInput.click());
fileInput.addEventListener("change", () => {
    const [file] = fileInput.files;
    if (file) {
        prepareUploadedFile(file);
    }
});
["dragenter", "dragover"].forEach((eventName) => {
    fileDropZone.addEventListener(eventName, (event) => {
        event.preventDefault();
        fileDropZone.classList.add("dragging");
    });
});
["dragleave", "drop"].forEach((eventName) => {
    fileDropZone.addEventListener(eventName, (event) => {
        event.preventDefault();
        fileDropZone.classList.remove("dragging");
    });
});
fileDropZone.addEventListener("drop", (event) => {
    const [file] = event.dataTransfer.files;
    if (file) {
        prepareUploadedFile(file);
    }
});
window.addEventListener("beforeunload", () => {
    stopMediaTracks();
    revokePreviewUrl();
});

function initializeDesktopMediaBridge() {
    reportDesktopMediaCapabilities();
    if (!supportsMediaRecording() && window.pywebview?.api?.open_recording_in_browser) {
        startButton.textContent = "Открыть запись в браузере";
        setStatus(
            "Встроенное окно не поддерживает камеру. Запись откроется в системном браузере."
        );
    }
}

if (window.pywebview?.api) {
    initializeDesktopMediaBridge();
} else {
    window.addEventListener("pywebviewready", initializeDesktopMediaBridge, { once: true });
}
