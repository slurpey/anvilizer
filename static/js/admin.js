// Admin page JS for Anvilizer
document.addEventListener("DOMContentLoaded", function () {
 loadThumbnails();
 loadSessions();
 loadQueueInfo();
 loadStats();

 // Session delete handler (delegated)
 document.getElementById("sessions-table-body").addEventListener("click", function (e) {
 if (e.target.classList.contains("delete-session-btn")) {
 const uid = e.target.dataset.uid;
 if (confirm(`Delete session ${uid}? This cannot be undone.`)) {
 deleteSession(uid);
 }
 }
 });
});

// Thumbnails with pagination support
let currentPage = 1;
let totalPages = 1;
let isLoading = false;

function loadThumbnails(page = 1, perPage = 50) {
 if (isLoading) return;
 isLoading = true;
 
 const url = `/admin/api/logs?page=${page}&per_page=${perPage}`;
 
 fetch(url)
 .then(resp => resp.json())
 .then(data => {
 const grid = document.getElementById("thumbnail-grid");
 const section = grid.closest('section');
 const h2 = section.querySelector('h2');
 
 // Update pagination variables
 currentPage = data.page;
 totalPages = data.total_pages;
 
 // Update header with comprehensive count information
 const startNum = ((data.page - 1) * data.per_page) + 1;
 const endNum = Math.min(data.page * data.per_page, data.total_count);
 h2.textContent = `Recent Thumbnails (${startNum}-${endNum} of ${data.total_count} total)`;
 
 // Clear grid and add thumbnails
 grid.innerHTML = "";
 data.thumbnails.forEach((item, index) => {
 const globalIndex = ((data.page - 1) * data.per_page) + index + 1;
 const div = document.createElement("div");
 div.className = "thumbnail-item";
 div.title = `${item.filename}\nUploaded: ${item.timestamp}\n#${globalIndex} of ${data.total_count}`;
 
 const img = document.createElement("img");
 img.src = item.url;
 img.alt = item.filename;
 img.className = "thumb-img";
 img.onerror = function() {
 this.style.display = 'none';
 div.innerHTML = '<div style="color:#666;font-size:12px;text-align:center;">Image not found</div>';
 };
 
 // Add click handler to open image in new tab
 div.addEventListener('click', () => {
 window.open(item.url, '_blank');
 });
 
 div.appendChild(img);
 grid.appendChild(div);
 });
 
 // Update pagination controls
 updatePaginationControls(data);
 isLoading = false;
 })
 .catch(error => {
 console.error('Error loading thumbnails:', error);
 const grid = document.getElementById("thumbnail-grid");
 grid.innerHTML = '<div style="color:#e53935;text-align:center;padding:20px;">Failed to load thumbnails</div>';
 isLoading = false;
 });
}

function updatePaginationControls(data) {
 let controlsContainer = document.getElementById("pagination-controls");
 
 // Create pagination controls if they don't exist
 if (!controlsContainer) {
 controlsContainer = document.createElement("div");
 controlsContainer.id = "pagination-controls";
 controlsContainer.className = "pagination-controls";
 
 const thumbnailSection = document.querySelector("#thumbnail-grid").closest('section');
 thumbnailSection.appendChild(controlsContainer);
 }
 
 // Clear existing controls
 controlsContainer.innerHTML = "";
 
 if (data.total_pages <= 1) {
 return; // No pagination needed
 }
 
 // Page info
 const pageInfo = document.createElement("div");
 pageInfo.className = "page-info";
 pageInfo.textContent = `Page ${data.page} of ${data.total_pages}`;
 controlsContainer.appendChild(pageInfo);
 
 // Controls container
 const buttonsDiv = document.createElement("div");
 buttonsDiv.className = "pagination-buttons";
 
 // Previous button
 if (data.has_prev) {
 const prevBtn = document.createElement("button");
 prevBtn.textContent = "← Previous";
 prevBtn.className = "pagination-btn";
 prevBtn.onclick = () => loadThumbnails(data.page - 1);
 buttonsDiv.appendChild(prevBtn);
 }
 
 // Page numbers (show current and nearby pages)
 const showPages = [];
 const maxButtons = 7;
 let start = Math.max(1, data.page - Math.floor(maxButtons / 2));
 let end = Math.min(data.total_pages, start + maxButtons - 1);
 
 // Adjust start if we're near the end
 if (end - start + 1 < maxButtons) {
 start = Math.max(1, end - maxButtons + 1);
 }
 
 // First page
 if (start > 1) {
 const firstBtn = document.createElement("button");
 firstBtn.textContent = "1";
 firstBtn.className = "pagination-btn page-num";
 firstBtn.onclick = () => loadThumbnails(1);
 buttonsDiv.appendChild(firstBtn);
 
 if (start > 2) {
 const ellipsis = document.createElement("span");
 ellipsis.textContent = "...";
 ellipsis.className = "pagination-ellipsis";
 buttonsDiv.appendChild(ellipsis);
 }
 }
 
 // Page numbers
 for (let i = start; i <= end; i++) {
 const pageBtn = document.createElement("button");
 pageBtn.textContent = i.toString();
 pageBtn.className = `pagination-btn page-num ${i === data.page ? 'current' : ''}`;
 pageBtn.onclick = () => loadThumbnails(i);
 buttonsDiv.appendChild(pageBtn);
 }
 
 // Last page
 if (end < data.total_pages) {
 if (end < data.total_pages - 1) {
 const ellipsis = document.createElement("span");
 ellipsis.textContent = "...";
 ellipsis.className = "pagination-ellipsis";
 buttonsDiv.appendChild(ellipsis);
 }
 
 const lastBtn = document.createElement("button");
 lastBtn.textContent = data.total_pages.toString();
 lastBtn.className = "pagination-btn page-num";
 lastBtn.onclick = () => loadThumbnails(data.total_pages);
 buttonsDiv.appendChild(lastBtn);
 }
 
 // Next button
 if (data.has_next) {
 const nextBtn = document.createElement("button");
 nextBtn.textContent = "Next →";
 nextBtn.className = "pagination-btn";
 nextBtn.onclick = () => loadThumbnails(data.page + 1);
 buttonsDiv.appendChild(nextBtn);
 }
 
 controlsContainer.appendChild(buttonsDiv);
 
 // Load more button (alternative to pagination)
 if (data.has_next && data.page < 5) { // Show load more for first few pages
 const loadMoreBtn = document.createElement("button");
 loadMoreBtn.textContent = `Load More (${data.total_count - (data.page * data.per_page)} remaining)`;
 loadMoreBtn.className = "load-more-btn";
 loadMoreBtn.onclick = () => loadMoreThumbnails();
 controlsContainer.appendChild(loadMoreBtn);
 }
}

function loadMoreThumbnails() {
 if (isLoading || currentPage >= totalPages) return;
 
 isLoading = true;
 const nextPage = currentPage + 1;
 const url = `/admin/api/logs?page=${nextPage}&per_page=200`;
 
 fetch(url)
 .then(resp => resp.json())
 .then(data => {
 const grid = document.getElementById("thumbnail-grid");
 
 // Append new thumbnails to existing ones
 data.thumbnails.forEach((item, index) => {
 const globalIndex = ((data.page - 1) * data.per_page) + index + 1;
 const div = document.createElement("div");
 div.className = "thumbnail-item";
 div.title = `${item.filename}\nUploaded: ${item.timestamp}\n#${globalIndex} of ${data.total_count}`;
 
 const img = document.createElement("img");
 img.src = item.url;
 img.alt = item.filename;
 img.className = "thumb-img";
 img.onerror = function() {
 this.style.display = 'none';
 div.innerHTML = '<div style="color:#666;font-size:12px;text-align:center;">Image not found</div>';
 };
 
 div.addEventListener('click', () => {
 window.open(item.url, '_blank');
 });
 
 div.appendChild(img);
 grid.appendChild(div);
 });
 
 // Update variables
 currentPage = data.page;
 
 // Update header
 const section = grid.closest('section');
 const h2 = section.querySelector('h2');
 const totalLoaded = currentPage * 200;
 h2.textContent = `Recent Thumbnails (1-${Math.min(totalLoaded, data.total_count)} of ${data.total_count} total)`;
 
 // Update load more button
 const loadMoreBtn = document.querySelector('.load-more-btn');
 if (loadMoreBtn) {
 if (data.has_next) {
 loadMoreBtn.textContent = `Load More (${data.total_count - totalLoaded} remaining)`;
 } else {
 loadMoreBtn.remove();
 }
 }
 
 isLoading = false;
 })
 .catch(error => {
 console.error('Error loading more thumbnails:', error);
 isLoading = false;
 });
}

// Sessions
function loadSessions() {
 fetch("/admin/api/sessions")
 .then(resp => resp.json())
 .then(data => {
 const body = document.getElementById("sessions-table-body");
 body.innerHTML = "";
 data.sessions.forEach(sess => {
 const row = document.createElement("tr");

 // UID
 const uidCell = document.createElement("td");
 uidCell.textContent = sess.uid;

 // Created
 const createdCell = document.createElement("td");
 createdCell.textContent = sess.created;

 // Images
 const imgCell = document.createElement("td");
 imgCell.innerHTML = sess.images.map(img =>
 `<a href="${img.url}" target="_blank"><img src="${img.thumb}" alt="${img.style}" class="session-thumb"></a>`
 ).join(" ");

 // Status
 const statusCell = document.createElement("td");
 statusCell.textContent = sess.status;

 // Delete
 const delCell = document.createElement("td");
 const btn = document.createElement("button");
 btn.className = "delete-session-btn";
 btn.textContent = "Delete";
 btn.dataset.uid = sess.uid;
 delCell.appendChild(btn);

 row.appendChild(uidCell);
 row.appendChild(createdCell);
 row.appendChild(imgCell);
 row.appendChild(statusCell);
 row.appendChild(delCell);
 body.appendChild(row);
 });
 });
}

function deleteSession(uid) {
 fetch(`/admin/api/session/${encodeURIComponent(uid)}/delete`, { method: "POST" })
 .then(resp => resp.json())
 .then(data => {
 alert(data.success ? "Session deleted." : "Failed to delete session: " + (data.error || ""));
 loadSessions();
 });
}

// Queue Info
function loadQueueInfo() {
 fetch("/admin/api/queue")
 .then(resp => resp.json())
 .then(data => {
 const info = document.getElementById("queue-info");
 info.textContent = JSON.stringify(data, null,2);
 });
}

// Stats
function loadStats() {
 fetch("/admin/api/queue")
 .then(resp => resp.json())
 .then(data => {
 const div = document.getElementById("stats-summary");
 div.innerHTML = `
 <b>Total images processed:</b> ${data.images_processed}<br>
 <b>Active job:</b> ${data.active_job_id || "-"}<br>
 <b>Pod name:</b> ${data.pod_name || "-"}<br>
 <b>Queue length:</b> ${data.queue ? data.queue.length : 0}
 `;
 });
}
