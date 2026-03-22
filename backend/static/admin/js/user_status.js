function getCSRFToken() {
    const input = document.querySelector("[name=csrfmiddlewaretoken]");
    if (input) {
        return input.value;
    }

    for (const cookie of document.cookie.split(";")) {
        const [name, value] = cookie.trim().split("=");
        if (name === "csrftoken") {
            return value;
        }
    }

    return "";
}

function hideRowFromElement(element, userId) {
    const row = element.closest("tr");

    if (!row) {
        console.error(`Could not find table row for user ${userId}`, element);
        return;
    }

    row.style.display = "none";
}

function handleUserAction(element, userId, action) {
    console.log(`${action} user:`, userId);

    fetch(`${action}-user/${userId}/`, {
        method: "POST",
        headers: {
            "Content-Type": "application/x-www-form-urlencoded",
            "X-CSRFToken": getCSRFToken(),
        },
    })
        .then((response) => response.json())
        .then((data) => {
            console.log(`${action} response:`, data);

            if (!data.success) {
                alert(`Failed to ${action} user: ${data.error || "Unknown error"}`);
                return;
            }

            hideRowFromElement(element, userId);
        })
        .catch((error) => {
            console.error(`${action} error:`, error);
            alert(`Error ${action}ing user: ${error.message}`);
        });
}

function hideUser(element, userId) {
    handleUserAction(element, userId, "hide");
}

function confirmUser(element, userId) {
    handleUserAction(element, userId, "confirm");
}