/* =========================================
   AI SMART ATTENDANCE - MASTER CONTROLLER
   ========================================= */

// 1. Element Selectors
const rawVideo = document.getElementById('rawVideo'); 
const aiFeed = document.getElementById('ai-feed'); 
const visualFrame = document.getElementById('visual-frame'); 
const hiddenCanvas = document.getElementById('hidden-canvas');
const statusText = document.getElementById('system-ready-text');
const engineMode = document.getElementById('engine-mode');
const detName = document.getElementById('detected-name');
const detRoll = document.getElementById('detected-roll');
const activeClass = document.getElementById('activeClass');

// Buttons
const startBtn = document.getElementById('startWebcam');
const stopBtn = document.getElementById('stop-btn');

let stream = null;
let processingInterval = null;
let isProcessing = false; 
const FPS = 4; 

/**
 * 2. LOAD SAVED CLASSES
 * Fetches the classes from SQLite via the Flask API
 */
async function loadClasses() {
    try {
        // FIXED: Pointing to the optimized global endpoint instead of the old one
        
        const response = await fetch('/api/get_my_classes');
        const data = await response.json();
        
        if (data.success && activeClass) {
            activeClass.innerHTML = '<option value="">-- Choose a Class --</option>';
            data.classes.forEach(c => {
                const option = document.createElement('option');
                option.value = c.id;
                option.textContent = c.class_name;
                activeClass.appendChild(option);
            });
            console.log(">>> [SYS_INIT]: Classes loaded into Scanner.");
        }
    } catch (err) {
        console.error("Failed to load classes:", err);
    }
}

// Run class loader immediately on page load
window.addEventListener('load', loadClasses);

/**
 * 3. START SYSTEM
 * Initializes the webcam and starts the AI loop
 */
async function startSystem() {
    const classId = activeClass.value;
    if (!classId) return;

    try {
        engineMode.innerText = "Initializing Camera...";
        
        stream = await navigator.mediaDevices.getUserMedia({ 
            video: { width: 640, height: 480 }, 
            audio: false 
        });
        
        rawVideo.srcObject = stream;
        
        // ⚡ THE FIX: Only disable buttons if they actually exist in the HTML!
        if (startBtn) startBtn.disabled = true;
        if (stopBtn) stopBtn.disabled = false;
        
        activeClass.disabled = true; // Lock class during session

        rawVideo.onloadedmetadata = () => {
            hiddenCanvas.width = 640;
            hiddenCanvas.height = 480;
            statusText.innerText = "SYSTEM ACTIVE";
            statusText.className = "status-online";
            engineMode.innerText = "AI Live Analysis Running...";
            
            // Start the processing loop
            processingInterval = setInterval(sendFrameToBackend, 1000 / FPS);
        };
    } catch (err) {
        console.error("Camera Access Error:", err);
        engineMode.innerText = "Error: Check Permissions";
        alert("Could not access webcam. Ensure you are on localhost or HTTPS.");
    }
}


/**
 * 4. AI LOOP: CAPTURE -> SEND -> ANNOTATE
 */
async function sendFrameToBackend() {
    if (!stream || isProcessing) return;

    const classId = activeClass.value;
    isProcessing = true; 

    const ctx = hiddenCanvas.getContext('2d');
    ctx.drawImage(rawVideo, 0, 0, 640, 480);
    const base64Image = hiddenCanvas.toDataURL('image/jpeg', 0.5);

    try {
        const response = await fetch('/api/process_frame', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ 
                image: base64Image,
                class_id: classId 
            })
        });

        // ... [Keep the top of sendFrameToBackend the same, stop right before data = await response.json()] ...

        const data = await response.json();
        const resultImg = data.image || data.annotated_image;

        if (resultImg) {
            aiFeed.src = resultImg;
            
            // ⚡ GROUP UI HANDLING
            const listContainer = document.getElementById('detected-list');
            
            if (data.detected_users && data.detected_users.length > 0) {
                // Determine frame border color based on the worst state in the group
                const hasAlert = data.detected_users.some(u => u.state === 'alert');
                visualFrame.className = `scanner-wrapper ${hasAlert ? 'alert' : 'success'}`;

                // Render the list of all detected people
                listContainer.innerHTML = data.detected_users.map(user => `
                    <div style="background: rgba(255,255,255,0.05); padding: 10px; border-left: 3px solid ${user.state === 'success' ? 'var(--success)' : 'var(--danger)'}; border-radius: 4px;">
                        <div style="font-size: 1rem; font-weight: 700; color: #fff;">${user.name}</div>
                        <div style="font-family: 'JetBrains Mono'; font-size: 0.7rem; color: var(--text-secondary); margin-top: 4px;">ID: ${user.roll}</div>
                    </div>
                `).join('');

                // Toast Logic (Only fire if a user wasn't in the very last frame)
                data.detected_users.forEach(user => {
                    if (user.state === 'success' && !window.lastDetectedSet?.has(user.roll)) {
                        showToast(user.name, user.roll);
                    }
                });

                // Update memory cache for the next frame
                window.lastDetectedSet = new Set(data.detected_users.map(u => u.roll));

            } else {
                // Nobody in frame
                visualFrame.className = 'scanner-wrapper';
                listContainer.innerHTML = `<div style="text-align: center; color: var(--text-secondary); font-family: 'JetBrains Mono'; font-size: 0.8rem; padding: 20px 0;">AWAITING_TARGET...</div>`;
                window.lastDetectedSet = new Set();
            }
        }
    } catch (error) {
        console.error("API Connection Error:", error);
    } finally {
        isProcessing = false; 
    }
}


/**
 * 5. UI & FEEDBACK HELPERS
 */
function updateUIState(state, name, roll) {
    detName.innerText = name;
    detRoll.innerText = roll;
    
    visualFrame.classList.remove('success', 'alert');
    if (state === 'success') visualFrame.classList.add('success');
    if (state === 'alert') visualFrame.classList.add('alert');
}

function showToast(name, roll) {
    const container = document.getElementById('toast-container');
    const toast = document.createElement('div');
    toast.className = 'toast';
    toast.innerHTML = `<div class="toast-name">✅ ${name}</div><div class="toast-msg">Roll: ${roll} logged</div>`;
    container.appendChild(toast);
    
    setTimeout(() => {
        toast.style.opacity = '0';
        setTimeout(() => toast.remove(), 500);
    }, 3000);
}

/**
 * 6. EVENT LISTENERS
 */
/**
 * 6. ZERO-CLICK AUTOMATION
 */
if (activeClass) {
    activeClass.addEventListener('change', () => {
        const classId = activeClass.value;
        
        if (classId) {
            // Auto-Start the camera when a class is picked
            startSystem();
        } else {
            // Auto-Stop the camera if they deselect the class
            if (stream) stream.getTracks().forEach(track => track.stop());
            clearInterval(processingInterval);
            isProcessing = false;
            rawVideo.srcObject = null;
            aiFeed.src = "";
            statusText.innerText = "NEURAL_NET_READY";
            statusText.className = "status-online";
            engineMode.innerText = "STBY_MODE";
            document.getElementById('detected-list').innerHTML = '<div style="text-align: center; color: var(--text-secondary); font-family: \'JetBrains Mono\'; font-size: 0.8rem; padding: 20px 0;">SCANNING_AREA...</div>';
            visualFrame.className = 'scanner-wrapper';
        }
    });
}

if (stopBtn) {
    stopBtn.addEventListener('click', () => {
        if (stream) stream.getTracks().forEach(track => track.stop());
        clearInterval(processingInterval);
        
        rawVideo.srcObject = null;
        aiFeed.src = "";
        
        // Reset UI
        startBtn.disabled = false;
        stopBtn.disabled = true;
        activeClass.disabled = false;
        
        statusText.innerText = "SYSTEM PAUSED";
        statusText.className = "";
        engineMode.innerText = "Waiting for restart...";
        updateUIState('normal', "Waiting...", "No active scan");
    });
}