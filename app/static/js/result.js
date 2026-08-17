const processingPanel = document.querySelector("#processing-panel");
const publicId = processingPanel.dataset.publicId;
const statusBadge = document.querySelector("#status-badge");
const headerStatus = document.querySelector("#header-status");
const processingTitle = document.querySelector("#processing-title");
const processingMessage = document.querySelector("#processing-message");
const processingError = document.querySelector("#processing-error");
const progressTrack = document.querySelector("#progress-track");
const progressBar = document.querySelector("#progress-bar");
const transcriptText = document.querySelector("#transcript-text");
const recordingDuration = document.querySelector("#recording-duration");
const reanalyzeButton = document.querySelector("#reanalyze-button");
const analysisWorkspace = document.querySelector("#analysis-workspace");
const analysisContent = document.querySelector("#analysis-content");
const analysisEmpty = document.querySelector("#analysis-empty");
const copyAnswerButton = document.querySelector("#copy-answer");
const chatShell = document.querySelector(".chat-shell");
const chatForm = document.querySelector("#chat-form");
const chatQuestion = document.querySelector("#chat-question");
const chatMessages = document.querySelector("#chat-messages");
const chatError = document.querySelector("#chat-error");

const statusView = {
    uploaded: {
        label: "В очереди",
        title: "Запись загружена",
        message: "Ставим обработку в очередь. Можно оставить страницу открытой.",
        progress: 12,
    },
    transcribing: {
        label: "Транскрибация",
        title: "Whisper распознаёт речь",
        message: "Превращаем аудиодорожку в полный текст ответа.",
        progress: 52,
    },
    transcription_completed: {
        label: "Расшифровка готова",
        title: "Расшифровка сохранена",
        message: "Подключите Gemini или повторите AI-анализ — видео больше не обрабатывается.",
        progress: 68,
    },
    ai_analysis_processing: {
        label: "AI-анализ",
        title: "Gemini разбирает ответ",
        message: "Оцениваем структуру, ясность, конкретику и готовим рекомендации.",
        progress: 84,
    },
    completed: {
        label: "Готово",
        title: "Разбор готов",
        message: "Результат сохранён. Возвращайтесь к нему в любое время.",
        progress: 100,
    },
    ai_analysis_failed: {
        label: "AI-анализ не выполнен",
        title: "Расшифровка готова, AI-анализ не выполнен",
        message: "Текст сохранён. Повторите только AI-анализ после устранения причины.",
        progress: 86,
    },
    failed: {
        label: "Ошибка",
        title: "Обработка остановилась",
        message: "Запустите обработку ещё раз — загружать видео повторно не нужно.",
        progress: 100,
    },
};

const statusClasses = Object.keys(statusView).map((status) => `status-${status}`);
let pollTimerId = null;

function schedulePoll() {
    window.clearTimeout(pollTimerId);
    pollTimerId = window.setTimeout(pollRecording, 2000);
}

function parseAnalysis(rawAnalysis) {
    if (!rawAnalysis) {
        return null;
    }
    try {
        const parsed = JSON.parse(rawAnalysis);
        if (parsed && typeof parsed === "object" && !parsed.criteria) {
            parsed.overall_score = Number(parsed.overall_score || 0) * 10;
            parsed.criteria = {
                structure: Number(parsed.structure_score || 0) * 10,
                specificity: Number(parsed.specificity_score || 0) * 10,
                relevance: 50,
                clarity: Number(parsed.clarity_score || 0) * 10,
                confidence: 50,
            };
        }
        return parsed && typeof parsed === "object" ? parsed : null;
    } catch (error) {
        console.error("Could not parse stored AI analysis", error);
        return null;
    }
}

function replaceList(selector, items) {
    const list = document.querySelector(selector);
    list.replaceChildren();
    items.forEach((item) => {
        const listItem = document.createElement("li");
        listItem.textContent = item;
        list.append(listItem);
    });
}

function renderRecommendations(items) {
    const list = document.querySelector("#recommendations-list");
    list.replaceChildren();
    items.forEach((item, index) => {
        const listItem = document.createElement("li");
        const number = document.createElement("span");
        const text = document.createElement("p");
        number.textContent = String(index + 1).padStart(2, "0");
        text.textContent = item;
        listItem.append(number, text);
        list.append(listItem);
    });
}

function renderFillerWords(items) {
    const container = document.querySelector("#filler-words");
    container.replaceChildren();
    if (!items.length) {
        const message = document.createElement("p");
        message.className = "no-fillers";
        message.textContent = "Не обнаружены — отлично!";
        container.append(message);
        return;
    }
    items.forEach((item) => {
        const chip = document.createElement("span");
        const count = document.createElement("b");
        chip.append(`${item.word} `);
        count.textContent = `×${item.count}`;
        chip.append(count);
        container.append(chip);
    });
}

function renderAnalysis(analysis) {
    analysisWorkspace.classList.add("has-analysis");
    analysisContent.hidden = false;
    analysisEmpty.hidden = true;

    document.querySelector("#overall-score").textContent = analysis.overall_score;
    document.querySelector("#score-caption").textContent = analysis.overall_score >= 80
        ? "Сильный ответ"
        : analysis.overall_score >= 60 ? "Хорошая база" : "Есть точки роста";
    document.querySelector("#score-dial").style.setProperty("--score", `${analysis.overall_score}%`);

    ["structure", "clarity", "specificity", "relevance", "confidence"].forEach((metric) => {
        const value = analysis.criteria[metric];
        document.querySelector(`#${metric}-score`).textContent = value;
        document.querySelector(`#${metric}-bar`).style.width = `${value}%`;
    });

    document.querySelector("#analysis-summary").textContent = analysis.summary;
    document.querySelector("#improved-answer").textContent = analysis.improved_answer;
    document.querySelector("#follow-up-question").textContent = analysis.follow_up_question;
    replaceList("#strengths-list", analysis.strengths || []);
    replaceList("#weaknesses-list", analysis.weaknesses || []);
    renderRecommendations(analysis.recommendations || []);
    renderFillerWords(analysis.filler_words || []);
}

function renderRecording(recording) {
    const view = statusView[recording.status] || statusView.uploaded;
    const analysis = parseAnalysis(recording.analysis_json);
    const processing = ["uploaded", "transcribing", "ai_analysis_processing"].includes(recording.status);

    statusBadge.textContent = view.label;
    headerStatus.textContent = view.label;
    processingTitle.textContent = view.title;
    processingMessage.textContent = view.message;
    progressBar.style.width = `${view.progress}%`;
    progressTrack.setAttribute("aria-valuenow", view.progress.toString());

    processingPanel.classList.remove(...statusClasses);
    processingPanel.classList.add(`status-${recording.status}`);
    headerStatus.className = `header-status status-${recording.status}`;
    analysisWorkspace.classList.toggle("is-processing", processing);

    if (recording.transcript) {
        transcriptText.textContent = recording.transcript;
    }
    recordingDuration.textContent = `${Number(recording.duration_seconds).toFixed(1)} сек.`;

    processingError.textContent = recording.error_message || "";
    processingError.hidden = !recording.error_message;
    reanalyzeButton.disabled = processing;
    reanalyzeButton.hidden = processing || !recording.transcript;
    reanalyzeButton.firstChild.textContent = recording.transcript
        ? "Повторить AI-анализ "
        : "Повторить обработку ";

    if (analysis) {
        renderAnalysis(analysis);
        processingTitle.textContent = "AI-разбор готов";
    } else if (!processing) {
        analysisWorkspace.classList.remove("has-analysis");
        analysisContent.hidden = true;
        analysisEmpty.hidden = false;
        if (recording.status === "transcription_completed") {
            processingTitle.textContent = "Расшифровка готова";
            processingMessage.textContent = "Текст сохранён. Для AI-разбора подключите Gemini или повторите анализ.";
        }
    }

    if (processing) {
        schedulePoll();
    } else {
        window.clearTimeout(pollTimerId);
    }
}

async function pollRecording() {
    try {
        const response = await fetch(`/api/recordings/${publicId}`, {
            headers: { Accept: "application/json" },
        });
        if (!response.ok) {
            throw new Error("Не удалось получить статус записи.");
        }
        renderRecording(await response.json());
    } catch (error) {
        console.error("Could not poll recording status", error);
        processingMessage.textContent = "Не удалось обновить статус. Повторяем попытку…";
        schedulePoll();
    }
}

async function restartAnalysis() {
    reanalyzeButton.disabled = true;
    processingError.hidden = true;
    processingMessage.textContent = "Запускаем AI-анализ по сохранённой расшифровке…";
    try {
        const response = await fetch(`/api/recordings/${publicId}/analyze`, {
            method: "POST",
            headers: { Accept: "application/json" },
        });
        const payload = await response.json();
        if (!response.ok) {
            throw new Error(payload.detail || "Не удалось запустить обработку.");
        }
        renderRecording(payload);
    } catch (error) {
        console.error("Could not restart recording analysis", error);
        processingError.textContent = error instanceof Error
            ? error.message
            : "Не удалось запустить обработку.";
        processingError.hidden = false;
        reanalyzeButton.disabled = false;
    }
}

async function copyImprovedAnswer() {
    const answer = document.querySelector("#improved-answer").textContent.trim();
    if (!answer) {
        return;
    }
    try {
        await navigator.clipboard.writeText(answer);
        copyAnswerButton.firstChild.textContent = "Скопировано ";
        window.setTimeout(() => { copyAnswerButton.firstChild.textContent = "Копировать "; }, 1800);
    } catch (error) {
        console.error("Could not copy improved answer", error);
    }
}

function appendChatMessage(role, content) {
    const message = document.createElement("article");
    const badge = document.createElement("span");
    const text = document.createElement("p");
    message.className = `chat-message ${role}`;
    badge.textContent = role === "assistant" ? "AI" : "Вы";
    text.textContent = content;
    message.append(badge, text);
    chatMessages.append(message);
    message.scrollIntoView({ behavior: "smooth", block: "nearest" });
}

async function loadChatHistory() {
    try {
        const response = await fetch(`/api/recordings/${publicId}/chat`, {
            headers: { Accept: "application/json" },
        });
        if (!response.ok) return;
        const payload = await response.json();
        payload.messages.forEach((message) => appendChatMessage(message.role, message.content));
    } catch (error) {
        console.error("Could not load AI chat history", error);
    }
}

async function askChat(event) {
    event.preventDefault();
    const question = chatQuestion.value.trim();
    if (!question) return;
    if (chatShell.dataset.chatConfigured !== "true") {
        chatError.textContent = "Сначала подключите Gemini API key в настройках.";
        chatError.hidden = false;
        return;
    }
    const submitButton = chatForm.querySelector("button");
    appendChatMessage("user", question);
    chatQuestion.value = "";
    submitButton.disabled = true;
    chatError.hidden = true;
    try {
        const response = await fetch(`/api/recordings/${publicId}/chat`, {
            method: "POST",
            headers: { "Content-Type": "application/json", Accept: "application/json" },
            body: JSON.stringify({ question }),
        });
        const payload = await response.json();
        if (!response.ok) throw new Error(payload.detail || "AI Chat временно недоступен.");
        appendChatMessage("assistant", payload.content);
    } catch (error) {
        console.error("Could not send AI chat question", error);
        chatError.textContent = error instanceof Error ? error.message : "AI Chat временно недоступен.";
        chatError.hidden = false;
    } finally {
        submitButton.disabled = false;
        chatQuestion.focus();
    }
}

reanalyzeButton.addEventListener("click", restartAnalysis);
copyAnswerButton.addEventListener("click", copyImprovedAnswer);
chatForm.addEventListener("submit", askChat);
loadChatHistory();

const initialTranscript = transcriptText.textContent.trim();
renderRecording({
    status: processingPanel.dataset.initialStatus,
    transcript: initialTranscript === "Расшифровка ещё не готова." ? null : initialTranscript,
    analysis_json: processingPanel.dataset.initialAnalysis || null,
    duration_seconds: Number.parseFloat(recordingDuration.textContent),
    error_message: processingError.textContent.trim() || null,
});
