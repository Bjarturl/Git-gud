function getCSRFToken() {
    const input = document.querySelector("[name=csrfmiddlewaretoken]");
    if (input) return input.value;
    for (const cookie of document.cookie.split(";")) {
        const [name, value] = cookie.trim().split("=");
        if (name === "csrftoken") return value;
    }
    return "";
}

function hideRowFromElement(element) {
    const row = element.closest("tr");
    if (row) row.style.display = "none";
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

function markMatch(element, matchId, status) {
    fetch(`mark-match/${matchId}/${status}/`, {
        method: "POST",
        headers: {
            "Content-Type": "application/x-www-form-urlencoded",
            "X-CSRFToken": getCSRFToken(),
        },
    })
        .then((response) => response.json())
        .then((data) => {
            if (!data.success) {
                alert(`Failed: ${data.error || "Unknown error"}`);
                return;
            }
            hideRowFromElement(element);
            if (data.count > 1) {
                const label = status === "false-positive" ? "false positive" : "interesting";
                showAdminMessage(`Marked ${data.count} matches as ${label}: "${data.match}"`);
            }
        })
        .catch((error) => {
            alert(`Error: ${error.message}`);
        });
}

function markFalsePositive(element, matchId) {
    markMatch(element, matchId, "false-positive");
}

function markInteresting(element, matchId) {
    markMatch(element, matchId, "interesting");
}

function markMatchByUrl(element, url, hideRow) {
    fetch(url, {
        method: "POST",
        headers: {
            "Content-Type": "application/x-www-form-urlencoded",
            "X-CSRFToken": getCSRFToken(),
        },
    })
        .then((r) => r.json())
        .then((data) => {
            if (!data.success) {
                alert(`Failed: ${data.error || "Unknown error"}`);
                return;
            }
            if (hideRow) {
                const row = element.closest("tr");
                if (row) row.style.display = "none";
            }
            if (data.count > 1) {
                const label = url.includes("false-positive") ? "false positive" : "interesting";
                showAdminMessage(`Marked ${data.count} matches as ${label}: "${data.match}"`);
            }
        })
        .catch((err) => alert(`Error: ${err.message}`));
}
