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

function showAdminMessage(html, level) {
    let list = document.querySelector("ul.messagelist");
    if (!list) {
        list = document.createElement("ul");
        list.className = "messagelist";
        const content = document.querySelector("#content");
        if (content) content.prepend(list);
    }
    const li = document.createElement("li");
    li.className = level || "success";
    li.innerHTML = html;
    list.appendChild(li);
}

function runPipeline(element, userId) {
    fetch(`run-pipeline-ajax/${userId}/`, {
        method: "POST",
        headers: {
            "Content-Type": "application/x-www-form-urlencoded",
            "X-CSRFToken": getCSRFToken(),
        },
    })
        .then((response) => response.json())
        .then((data) => {
            if (!data.success) {
                alert(`Failed to start pipeline: ${data.error || "Unknown error"}`);
                return;
            }
            setTimeout(() => {
                const a = document.createElement("a");
                a.href = data.job_url;
                document.body.appendChild(a);
                a.dispatchEvent(new MouseEvent("click", { ctrlKey: true, bubbles: true }));
                document.body.removeChild(a);
            }, 1000);
            showAdminMessage(
                `Pipeline started for "${data.username}" — <a href="${data.job_url}">View job</a>`
            );
        })
        .catch((error) => {
            alert(`Error starting pipeline: ${error.message}`);
        });
}

function handleUserAction(element, userId, action) {
    console.log(`${action} user:`, userId);

    const row = element.closest("tr");
    if (row) row.style.display = "none";

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
                if (row) row.style.display = "";
                alert(`Failed to ${action} user: ${data.error || "Unknown error"}`);
            }
        })
        .catch((error) => {
            console.error(`${action} error:`, error);
            if (row) row.style.display = "";
            alert(`Error ${action}ing user: ${error.message}`);
        });
}

function hideUser(element, userId) {
    handleUserAction(element, userId, "hide");
}

function confirmUser(element, userId) {
    handleUserAction(element, userId, "confirm");
}

