// Copyright © 2025 Red Hat
// SPDX-License-Identifier: Apache-2.0

function createReport(url) {
  const eventsList = document.getElementById("events");
  const reportContainer = document.getElementById("report-container");
  const messageArea = document.getElementById("message-area");

  function showMessage(message, type = 'info') {
    messageArea.textContent = message;
    messageArea.classList.remove('bg-blue-100', 'text-blue-800', 'bg-red-100', 'text-red-800');
    if (type === 'info') {
      messageArea.classList.add('bg-blue-100', 'text-blue-800');
    } else if (type === 'error') {
      messageArea.classList.add('bg-red-100', 'text-red-800');
    }
    messageArea.style.display = 'block';
  }

  if (!url) {
    showMessage("No build URL provided. Add '?build=<URL>' to the page URL.", 'error');
  } else {
    showMessage("Submitting build for analysis...", 'info');
    fetch("/submit?build=" + url, { method: "PUT" })
      .then(resp => {
        if (!resp.ok) throw new Error(`Server responded with status ${resp.status}`);
        return resp.json();
      })
      .then(build => {
        if (build.status === "PENDING") {
          showMessage("Build is pending. Streaming logs...", 'info');
          eventsList.style.display = 'block';
          reportContainer.innerHTML = '';

          const evtSource = new EventSource("/watch?build=" + url);
          let currentListItem;
          let llmOutputContainer;

          evtSource.addEventListener('status', function (e) {
            const newElement = document.createElement("li");
            newElement.textContent = e.data;
            newElement.classList.add('font-semibold');
            eventsList.appendChild(newElement);
            currentListItem = null; // Reset for next LLM output
            llmOutputContainer = null;
          });

          evtSource.addEventListener('chunk', function (e) {
            if (!currentListItem) {
              currentListItem = document.createElement("li");
              llmOutputContainer = document.createElement("div");
              llmOutputContainer.classList.add("whitespace-pre-wrap", "bg-gray-50", "p-3", "rounded-md");
              currentListItem.appendChild(llmOutputContainer);
              eventsList.appendChild(currentListItem);
            }
            llmOutputContainer.textContent += e.data;
          });

          evtSource.addEventListener('error', function (e) {
            const newElement = document.createElement("li");
            newElement.textContent = `Error: ${e.data}`;
            newElement.classList.add('text-red-800', 'bg-red-100', 'p-2', 'rounded-md');
            eventsList.appendChild(newElement);
            currentListItem = null;
            llmOutputContainer = null;
          });

          evtSource.addEventListener('done', function (e) {
            showMessage("Analysis complete.", 'info');
            evtSource.close();
          });

          evtSource.onerror = (error) => {
            console.error("EventSource failed:", error);
            showMessage("Error receiving build events. The connection was closed.", 'error');
            evtSource.close();
          };
        } else if (build.status === "COMPLETED") {
          showMessage("Build completed. Fetching report...", 'info');
          fetch("/report?build=" + url)
            .then(resp => {
              if (!resp.ok) throw new Error(`Server responded with status ${resp.status}`);
              return resp.text();
            })
            .then(report => {
              eventsList.style.display = 'none';
              reportContainer.innerHTML = marked.parse(report);
              showMessage("Report loaded successfully.", 'info');
            })
            .catch(err => {
              console.error("Failed to fetch report:", err);
              showMessage(`Failed to fetch report: ${err.message}`, 'error');
            });
        } else {
          showMessage(`Unknown build status: ${build.status}`, 'error');
        }
      })
      .catch(err => {
        console.error("Failed to submit build:", err);
        showMessage(`Failed to submit build: ${err.message}`, 'error');
      });
  }
}