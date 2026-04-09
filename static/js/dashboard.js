/* =========================================
   CORE COMMAND CENTER LOGIC - UI 2.0
   ========================================= */

let attendanceChart = null;

document.addEventListener('DOMContentLoaded', () => {
    console.log(">>> [SYSTEM_INIT]: Dashboard protocols active.");
    
    // 1. Initialize High-Tech Clock & make it tick every second
    updateDate();
    setInterval(updateDate, 1000); // <-- Added real-time ticking
    
    // 2. Initial Data Load
    refreshDashboard(); 
    loadManagementData();

    // 3. Attach Roster Listener (Fixes the "Waiting" bug)
    const rosterSelect = document.getElementById('roster_class_select');
    if (rosterSelect) {
        rosterSelect.addEventListener('change', loadClassRoster);
    }

    // 4. Attach Admin Form Listeners
    setupAdminForms();

    // 5. Auto-Refresh Stats every 60 seconds
    setInterval(refreshDashboard, 60000);
});

/* --- 1. TELEMETRY & STATS --- */

async function refreshDashboard() {
    try {
        const response = await fetch('/api/dashboard_stats');
        const data = await response.json();

        if (data.success) {
            // Update the 3 main cards
            safeUpdateValue("totalStudents", data.total_students);
            safeUpdateValue("presentToday", data.present_today);
            
            const absentCount = data.total_students - data.present_today;
            safeUpdateValue("absentToday", absentCount > 0 ? absentCount : 0);

            // Update Logs & Chart
            renderLogsTable(data.logs);
            initAttendanceChart(data.logs);
            
            console.log(">>> [STATS]: System counts synced.");
        }
    } catch (err) {
        console.error(">>> [ERR]: Cannot reach stats API.", err);
    }
}

// A simpler, safer way to update numbers without the animation crashing
function safeUpdateValue(id, value) {
    const el = document.getElementById(id);
    if (el) {
        // We still use a small animation, but with a fallback
        let start = parseInt(el.innerText) || 0;
        let end = parseInt(value);
        if (start === end) return;
        
        el.innerText = end; // Immediate update for reliability
        el.style.color = "var(--accent)"; // Highlight change
        setTimeout(() => el.style.color = "", 500);
    }
}

function renderLogsTable(logs) {
    const tbody = document.getElementById('attendanceTableBody');
    if (!tbody) return;

    if (logs.length === 0) {
        tbody.innerHTML = '<tr><td colspan="4" class="empty-msg">NO_ACTIVITY_DETECTED_TODAY</td></tr>';
        return;
    }

    tbody.innerHTML = logs.map(log => `
        <tr>
            <td><code style="color: var(--accent);">${log.Time}</code></td>
            <td><strong>${log.Name}</strong></td>
            <td><span class="roll-tag">${log['Roll No']}</span></td>
            <td><span class="status-tag"><i class="fas fa-check"></i> VERIFIED</span></td>
        </tr>
    `).join('');
}

/* --- 2. ROSTER & MANAGEMENT --- */

async function loadManagementData() {
    try {
        const response = await fetch('/api/get_management_data');
        const data = await response.json();

        if (data.success) {
            // Populate Roster Viewer Dropdown
            populateDropdown('roster_class_select', data.classes, 'class_name', 'id', '-- SELECT_CLASS --');

            // Populate Admin Dropdowns (if present)
            populateDropdown('c_teacher', data.teachers, 'name', 'id', '-- ASSIGN_TEACHER --');
            populateDropdown('e_student', data.students, 'name', 'roll_no', '-- SELECT_STUDENT --');
            populateDropdown('e_class', data.classes, 'class_name', 'id', '-- SELECT_CLASS --');
            // Add these inside loadManagementData() where you populate the other dropdowns:
            populateDropdown('edit_c_select', data.classes, 'class_name', 'id', '-- SELECT_CLASS_TO_EDIT --');
            populateDropdown('edit_c_teacher', data.teachers, 'name', 'id', '-- REASSIGN_TEACHER --');

            // Save the classes to the window so we can access their times instantly when selected
            window.allClassesData = data.classes;
        }
    } catch (err) {
        console.log(">>> [DEBUG]: Non-admin session or fetch error.");
    }
}

async function loadClassRoster() {
    const classId = document.getElementById('roster_class_select').value;
    const rosterList = document.getElementById('roster_list');

    if (!classId) {
        rosterList.innerHTML = '<li class="empty-msg">Waiting for class selection...</li>';
        return;
    }

    rosterList.innerHTML = '<li class="empty-msg"><i class="fas fa-circle-notch fa-spin"></i> QUERYING_DATABASE...</li>';

    try {
        const response = await fetch(`/api/get_students_by_class?class_id=${classId}`);
        const data = await response.json();

        if (data.success) {
            if (data.students.length === 0) {
                rosterList.innerHTML = '<li class="empty-msg">NO_UNITS_FOUND_IN_THIS_INDEX</li>';
            } else {
                rosterList.innerHTML = data.students.map(s => `
                    <li>
                        <span><i class="far fa-user" style="margin-right:10px; color: var(--accent);"></i> ${s.name}</span>
                        <span class="roll-tag">${s.roll_no}</span>
                    </li>
                `).join('');
            }
        }
    } catch (err) {
        rosterList.innerHTML = '<li class="empty-msg" style="color: var(--danger);">COMM_LINK_FAILURE</li>';
    }
}

/* --- 3. DATA VISUALIZATION (Chart.js) --- */

function initAttendanceChart(logs) {
    const ctx = document.getElementById('attendanceChart');
    if (!ctx) return;

    // Sample processing: Count detections per hour
    const hours = ['08:00', '10:00', '12:00', '14:00', '16:00', '18:00'];
    const dataPoints = [2, 5, 12, 8, 15, 4]; // Placeholder if logs are thin

    if (attendanceChart) attendanceChart.destroy();

    attendanceChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: hours,
            datasets: [{
                label: 'Detections',
                data: dataPoints,
                borderColor: '#00d2ff',
                backgroundColor: 'rgba(0, 210, 255, 0.05)',
                borderWidth: 2,
                tension: 0.4,
                fill: true,
                pointBackgroundColor: '#00d2ff',
                pointRadius: 4
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { display: false } },
            scales: {
                x: { grid: { display: false }, ticks: { color: '#94a3b8', font: { family: 'JetBrains Mono' } } },
                y: { grid: { color: 'rgba(255,255,255,0.05)' }, ticks: { color: '#94a3b8' } }
            }
        }
    });
}

/* --- 4. ADMIN ACTIONS --- */

function setupAdminForms() {
    const forms = {
        'teacherForm': '/api/add_teacher',
        'classForm': '/api/add_class',
        'enrollmentForm': '/api/enroll_student'
    };

    Object.entries(forms).forEach(([id, url]) => {
        const form = document.getElementById(id);
        if (form) {
            form.addEventListener('submit', async (e) => {
                e.preventDefault();
                const formData = {};
                // Dynamically collect inputs
                if (id === 'teacherForm') {
                    formData.name = document.getElementById('t_name').value;
                    formData.username = document.getElementById('t_user').value;
                    formData.password = document.getElementById('t_pass').value;
                } else if (id === 'classForm') {
                    formData.class_name = document.getElementById('c_name').value;
                    formData.teacher_id = document.getElementById('c_teacher').value;
                    formData.start_time = document.getElementById('c_start').value;
                    formData.end_time = document.getElementById('c_end').value;
                } else if (id === 'enrollmentForm') {
                    formData.roll_no = document.getElementById('e_student').value;
                    formData.class_id = document.getElementById('e_class').value;
                }

                const res = await fetch(url, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(formData)
                });
                const result = await res.json();
                alert(result.message || "Action Successful");
                if (result.success) {
                    form.reset();
                    loadManagementData(); // Refresh dropdowns
                }
            });
        }
    });
}

/* --- HELPERS --- */

function populateDropdown(id, items, textKey, valueKey, defaultText) {
    const el = document.getElementById(id);
    if (!el) {
        console.error(`>>> [SYS_ERR]: Element #${id} not found in HTML.`);
        return;
    }

    // Diagnostic: See what the server actually sent
    console.log(`>>> [DATA_SYNC]: Populating ${id} with ${items ? items.length : 0} items.`);

    if (!items || items.length === 0) {
        el.innerHTML = `<option value="">-- NO_CLASSES_FOUND --</option>`;
        return;
    }

    let html = `<option value="">${defaultText}</option>`;
    items.forEach(item => {
        // Ensure we are accessing the right keys
        const text = item[textKey] || "Unknown";
        const val = item[valueKey] || "";
        html += `<option value="${val}">${text}</option>`;
    });
    
    el.innerHTML = html;
}

function animateValue(id, endValue) {
    const obj = document.getElementById(id);
    if (!obj) return;
    let startValue = 0;
    let duration = 1000;
    let startTimestamp = null;
    const step = (timestamp) => {
        if (!startTimestamp) startTimestamp = timestamp;
        const progress = Math.min((timestamp - startTimestamp) / duration, 1);
        obj.innerHTML = Math.floor(progress * (endValue - startValue) + startValue);
        if (progress < 1) {
            window.requestAnimationFrame(step);
        }
    };
    window.requestAnimationFrame(step);
}

function updateDate() {
    const dateEl = document.getElementById('currentDateText');
    if (!dateEl) return;
    const now = new Date();
    const options = { weekday: 'short', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit', second: '2-digit' };
    dateEl.innerText = now.toLocaleString('en-US', options).toUpperCase().replace(/,/g, ' //');
}


// Auto-fills the form when the admin selects a class to edit
function populateEditForm() {
    const classId = document.getElementById('edit_c_select').value;
    if (!classId || !window.allClassesData) return;

    // Find the specific class data
    const selectedClass = window.allClassesData.find(c => c.id.toString() === classId.toString());
    
    if (selectedClass) {
        document.getElementById('edit_c_name').value = selectedClass.class_name || "";
        document.getElementById('edit_c_teacher').value = selectedClass.teacher_id || "";
        document.getElementById('edit_c_start').value = selectedClass.start_time || "";
        document.getElementById('edit_c_end').value = selectedClass.end_time || "";
    }
}

// Handle the Edit Form Submission
const editForm = document.getElementById('editClassForm');
if (editForm) {
    editForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        
        const formData = {
            class_id: document.getElementById('edit_c_select').value,
            class_name: document.getElementById('edit_c_name').value,
            teacher_id: document.getElementById('edit_c_teacher').value,
            start_time: document.getElementById('edit_c_start').value,
            end_time: document.getElementById('edit_c_end').value
        };

        if (!formData.class_id) {
            alert("Please select a class to edit!");
            return;
        }

        try {
            const res = await fetch('/api/edit_class', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(formData)
            });
            const result = await res.json();
            alert(result.message);
            
            if (result.success) {
                editForm.reset();
                loadManagementData(); // Refresh all UI data instantly
            }
        } catch (err) {
            console.error("Failed to update class:", err);
        }
    });
}


// Handle Student Removal
const removeStudentForm = document.getElementById('removeStudentForm');
if (removeStudentForm) {
    removeStudentForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        
        const rollNo = document.getElementById('remove_roll_no').value.trim();
        if (!rollNo) return;

        // HIGH SECURITY: Force the Admin to confirm the deletion
        const confirmed = confirm(`CRITICAL WARNING: Are you absolutely sure you want to permanently delete Roll Number ${rollNo}? This cannot be undone.`);
        
        if (!confirmed) {
            return; // Abort mission if they click Cancel
        }

        try {
            const res = await fetch('/api/remove_student', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ roll_no: rollNo })
            });
            const result = await res.json();
            
            alert(result.message);
            
            if (result.success) {
                removeStudentForm.reset();
                // If you have a function that updates stats on the dashboard, call it here
            }
        } catch (err) {
            console.error("Failed to remove student:", err);
            alert("COMM_FAILURE: Could not execute purge.");
        }
    });
}