const settingsForm = document.querySelector("#gemini-settings-form");

if (settingsForm) {
    const keyInput = document.querySelector("#gemini-api-key");
    const statusBadge = document.querySelector("#gemini-key-status");
    const message = document.querySelector("#settings-message");
    const saveButton = document.querySelector("#save-gemini-key");
    const validateButton = document.querySelector("#validate-gemini-key");
    const deleteButton = document.querySelector("#delete-gemini-key");
    const visibilityButton = document.querySelector("#toggle-key-visibility");
    const getKeyLink = document.querySelector("#get-gemini-key-link");

    function showMessage(text, isError = false) {
        message.textContent = text;
        message.classList.toggle("error", isError);
    }

    function renderConfigured(configured) {
        statusBadge.textContent = configured ? "Gemini подключён" : "Gemini не подключён";
        statusBadge.classList.toggle("configured", configured);
        deleteButton.disabled = !configured;
    }

    visibilityButton.addEventListener("click", () => {
        const selectionStart = keyInput.selectionStart;
        const selectionEnd = keyInput.selectionEnd;
        const reveal = keyInput.type === "password";
        keyInput.type = reveal ? "text" : "password";
        visibilityButton.textContent = reveal ? "Скрыть" : "Показать";
        keyInput.focus({ preventScroll: true });
        if (selectionStart !== null && selectionEnd !== null) {
            keyInput.setSelectionRange(selectionStart, selectionEnd);
        }
    });

    getKeyLink.addEventListener("click", async (event) => {
        const desktopApi = window.pywebview?.api;
        if (!desktopApi?.open_gemini_key_page) {
            return;
        }
        event.preventDefault();
        try {
            await desktopApi.open_gemini_key_page();
        } catch (error) {
            console.error("Could not open Google AI Studio", error);
            window.open(getKeyLink.href, "_blank", "noopener,noreferrer");
        }
    });

    settingsForm.addEventListener("submit", async (event) => {
        event.preventDefault();
        if (!settingsForm.reportValidity()) {
            return;
        }
        saveButton.disabled = true;
        showMessage("Проверяем и сохраняем ключ…");
        try {
            const response = await fetch("/api/settings/gemini", {
                method: "PUT",
                headers: { "Content-Type": "application/json", Accept: "application/json" },
                body: JSON.stringify({ api_key: keyInput.value }),
            });
            const payload = await response.json();
            if (!response.ok) {
                throw new Error(payload.detail || "Не удалось сохранить ключ.");
            }
            keyInput.value = "";
            keyInput.type = "password";
            visibilityButton.textContent = "Показать";
            renderConfigured(payload.configured);
            showMessage("Gemini подключён. Теперь можно повторить AI-анализ записи.");
        } catch (error) {
            showMessage(error instanceof Error ? error.message : "Не удалось сохранить ключ.", true);
        } finally {
            saveButton.disabled = false;
        }
    });

    validateButton.addEventListener("click", async () => {
        if (keyInput.value && !settingsForm.reportValidity()) {
            return;
        }
        validateButton.disabled = true;
        showMessage("Проверяем подключение к Gemini…");
        try {
            const response = await fetch("/api/settings/gemini/validate", {
                method: "POST",
                headers: { "Content-Type": "application/json", Accept: "application/json" },
                body: JSON.stringify(keyInput.value ? { api_key: keyInput.value } : {}),
            });
            const payload = await response.json();
            if (!response.ok) {
                throw new Error(payload.detail || "Не удалось проверить ключ.");
            }
            showMessage(keyInput.value ? "Подключение подтверждено. Нажмите «Сохранить ключ»." : "Gemini подключён и готов к AI-анализу.");
        } catch (error) {
            showMessage(error instanceof Error ? error.message : "Не удалось проверить ключ.", true);
        } finally {
            validateButton.disabled = false;
        }
    });

    deleteButton.addEventListener("click", async () => {
        deleteButton.disabled = true;
        showMessage("Удаляем ключ…");
        try {
            const response = await fetch("/api/settings/gemini", {
                method: "DELETE",
                headers: { Accept: "application/json" },
            });
            const payload = await response.json();
            if (!response.ok) {
                throw new Error(payload.detail || "Не удалось удалить ключ.");
            }
            renderConfigured(payload.configured);
            showMessage("Ключ удалён. Локальная транскрибация продолжит работать.");
        } catch (error) {
            showMessage(error instanceof Error ? error.message : "Не удалось удалить ключ.", true);
            deleteButton.disabled = false;
        }
    });
}
