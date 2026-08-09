const settingsForm = document.querySelector("#gemini-settings-form");

if (settingsForm) {
    const keyInput = document.querySelector("#gemini-api-key");
    const statusBadge = document.querySelector("#gemini-key-status");
    const message = document.querySelector("#settings-message");
    const saveButton = document.querySelector("#save-gemini-key");
    const deleteButton = document.querySelector("#delete-gemini-key");
    const visibilityButton = document.querySelector("#toggle-key-visibility");

    function showMessage(text, isError = false) {
        message.textContent = text;
        message.classList.toggle("error", isError);
    }

    function renderConfigured(configured) {
        statusBadge.textContent = configured ? "Сохранён" : "Не добавлен";
        statusBadge.classList.toggle("configured", configured);
        deleteButton.disabled = !configured;
    }

    visibilityButton.addEventListener("click", () => {
        const reveal = keyInput.type === "password";
        keyInput.type = reveal ? "text" : "password";
        visibilityButton.textContent = reveal ? "Скрыть" : "Показать";
    });

    settingsForm.addEventListener("submit", async (event) => {
        event.preventDefault();
        if (!settingsForm.reportValidity()) {
            return;
        }
        saveButton.disabled = true;
        showMessage("Сохраняем ключ в системном хранилище…");
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
            showMessage("Ключ сохранён. Теперь можно повторить AI-анализ записи.");
        } catch (error) {
            showMessage(error instanceof Error ? error.message : "Не удалось сохранить ключ.", true);
        } finally {
            saveButton.disabled = false;
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
