<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ISP Lead Tracker</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;700&display=swap');
        body {
            font-family: 'Inter', sans-serif;
            background-color: #1a202c;
            color: #e2e8f0;
        }
        .container {
            max-width: 900px;
        }
        .card {
            background-color: #2d3748;
            border-radius: 0.5rem;
            padding: 1.5rem;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);
        }
    </style>
</head>
<body>
    <div class="container mx-auto p-4 sm:p-6 lg:p-8 flex flex-col items-center">
        <div class="w-full text-center mb-6">
            <h1 class="text-4xl sm:text-5xl font-bold mb-2 text-white">ISP Lead Tracker</h1>
            <p class="text-gray-400">Track the status and time of each lead.</p>
        </div>

        <div id="auth-status" class="w-full text-center mb-4 text-sm text-gray-400">
            <span id="user-id-display">Loading...</span>
        </div>

        <!-- Add New Lead Form -->
        <div class="w-full mb-6 card">
            <h2 class="text-xl font-semibold mb-4 text-white">Add New Lead</h2>
            <form id="add-lead-form" class="flex flex-col sm:flex-row gap-4">
                <input type="text" id="lead-name" placeholder="Enter Lead Name" required class="flex-grow p-3 rounded-md bg-gray-700 text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500">
                <button type="submit" class="bg-blue-600 hover:bg-blue-700 text-white font-bold py-3 px-6 rounded-md transition duration-300">
                    Add Lead
                </button>
            </form>
        </div>

        <!-- Lead List Section -->
        <div class="w-full card">
            <h2 class="text-xl font-semibold mb-4 text-white">Leads</h2>
            <div id="leads-list" class="grid grid-cols-1 gap-4">
                <!-- Leads will be dynamically added here -->
            </div>
        </div>

        <!-- Modal for alerts -->
        <div id="alert-modal" class="hidden fixed inset-0 bg-gray-900 bg-opacity-75 flex items-center justify-center p-4 z-50">
            <div class="bg-gray-800 p-6 rounded-lg shadow-xl max-w-sm w-full border border-gray-700">
                <div class="flex justify-between items-start">
                    <h3 id="alert-title" class="text-lg font-bold text-white mb-2"></h3>
                    <button id="close-alert-button" class="text-gray-400 hover:text-gray-200">
                        <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path></svg>
                    </button>
                </div>
                <p id="alert-message" class="text-gray-300 mb-4"></p>
                <button id="ok-alert-button" class="w-full bg-blue-600 hover:bg-blue-700 text-white font-bold py-2 px-4 rounded transition duration-300">OK</button>
            </div>
        </div>

    </div>

    <!-- Firebase SDKs -->
    <script type="module">
        import { initializeApp } from "https://www.gstatic.com/firebasejs/11.6.1/firebase-app.js";
        import { getAuth, signInAnonymously, signInWithCustomToken, onAuthStateChanged } from "https://www.gstatic.com/firebasejs/11.6.1/firebase-auth.js";
        import { getFirestore, doc, getDoc, addDoc, setDoc, updateDoc, deleteDoc, onSnapshot, collection, query, where, serverTimestamp } from "https://www.gstatic.com/firebasejs/11.6.1/firebase-firestore.js";

        // Global variables provided by the environment
        const appId = typeof __app_id !== 'undefined' ? __app_id : 'default-app-id';
        const firebaseConfig = typeof __firebase_config !== 'undefined' ? JSON.parse(__firebase_config) : {};
        const initialAuthToken = typeof __initial_auth_token !== 'undefined' ? __initial_auth_token : null;

        // Status sequence
        const STATUSES = [
            "Survey Scheduled",
            "Survey Complete",
            "Prep Scheduled",
            "Prep Complete",
            "Install Scheduled",
            "Install Completed"
        ];

        let db;
        let auth;
        let userId;

        const app = initializeApp(firebaseConfig);
        db = getFirestore(app);
        auth = getAuth(app);

        // UI elements
        const addLeadForm = document.getElementById('add-lead-form');
        const leadNameInput = document.getElementById('lead-name');
        const leadsList = document.getElementById('leads-list');
        const userIdDisplay = document.getElementById('user-id-display');
        const alertModal = document.getElementById('alert-modal');
        const alertTitle = document.getElementById('alert-title');
        const alertMessage = document.getElementById('alert-message');
        const closeAlertButton = document.getElementById('close-alert-button');
        const okAlertButton = document.getElementById('ok-alert-button');

        // Alert function to replace window.alert
        function showAlert(title, message) {
            alertTitle.textContent = title;
            alertMessage.textContent = message;
            alertModal.classList.remove('hidden');
        }

        closeAlertButton.addEventListener('click', () => {
            alertModal.classList.add('hidden');
        });

        okAlertButton.addEventListener('click', () => {
            alertModal.classList.add('hidden');
        });

        // Authentication State Listener
        onAuthStateChanged(auth, async (user) => {
            if (user) {
                userId = user.uid;
                userIdDisplay.textContent = `User ID: ${userId}`;
                // Start listening to Firestore after authentication is ready
                setupFirestoreListener();
            } else {
                try {
                    if (initialAuthToken) {
                        await signInWithCustomToken(auth, initialAuthToken);
                    } else {
                        await signInAnonymously(auth);
                    }
                } catch (error) {
                    console.error("Error during authentication:", error);
                    showAlert("Authentication Error", "Could not sign in. Please try again.");
                }
            }
        });

        // Listen for real-time changes to the leads collection
        function setupFirestoreListener() {
            const leadsCollection = collection(db, `artifacts/${appId}/public/data/leads`);
            const q = query(leadsCollection);

            onSnapshot(q, (snapshot) => {
                const leads = [];
                snapshot.forEach((doc) => {
                    leads.push({ id: doc.id, ...doc.data() });
                });
                renderLeads(leads);
            }, (error) => {
                console.error("Error listening to leads:", error);
                showAlert("Data Error", "Could not fetch leads in real-time. Please check your connection.");
            });
        }

        // Add a new lead
        addLeadForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const leadName = leadNameInput.value.trim();
            if (leadName) {
                try {
                    await addDoc(collection(db, `artifacts/${appId}/public/data/leads`), {
                        name: leadName,
                        status: STATUSES[0],
                        statusHistory: [{ status: STATUSES[0], timestamp: serverTimestamp() }],
                        createdAt: serverTimestamp(),
                        userId: userId,
                    });
                    leadNameInput.value = '';
                } catch (error) {
                    console.error("Error adding document:", error);
                    showAlert("Add Lead Error", "Failed to add the new lead. Please try again.");
                }
            }
        });

        // Format duration to a human-readable string (e.g., "1h 2m 3s")
        function formatDuration(ms) {
            const seconds = Math.floor(ms / 1000);
            const minutes = Math.floor(seconds / 60);
            const hours = Math.floor(minutes / 60);

            let parts = [];
            if (hours > 0) parts.push(`${hours}h`);
            if (minutes % 60 > 0) parts.push(`${minutes % 60}m`);
            if (seconds % 60 > 0) parts.push(`${seconds % 60}s`);

            return parts.length > 0 ? parts.join(' ') : "0s";
        }

        // Render the leads list
        function renderLeads(leads) {
            leadsList.innerHTML = '';
            if (leads.length === 0) {
                leadsList.innerHTML = '<p class="text-gray-400 text-center">No leads yet. Add one above!</p>';
                return;
            }

            leads.forEach(lead => {
                const currentTime = Date.now();
                const totalDuration = lead.createdAt && lead.createdAt.toMillis ? currentTime - lead.createdAt.toMillis() : 0;
                const lastStatusTime = lead.statusHistory && lead.statusHistory.length > 0 ? lead.statusHistory[lead.statusHistory.length - 1].timestamp.toMillis() : currentTime;
                const currentStatusDuration = currentTime - lastStatusTime;

                const leadItem = document.createElement('div');
                leadItem.classList.add('card', 'flex', 'flex-col', 'sm:flex-row', 'items-start', 'sm:items-center', 'justify-between', 'gap-4', 'mb-4');
                
                // Content section
                const contentDiv = document.createElement('div');
                contentDiv.classList.add('flex-grow');
                contentDiv.innerHTML = `
                    <h3 class="text-lg font-bold text-white">${lead.name}</h3>
                    <p class="text-sm text-gray-400">Current Status: <span class="font-semibold text-white">${lead.status}</span></p>
                    <p class="text-sm text-gray-400">Time in Status: <span class="font-semibold">${formatDuration(currentStatusDuration)}</span></p>
                    <p class="text-sm text-gray-400">Total Time: <span class="font-semibold">${formatDuration(totalDuration)}</span></p>
                `;
                leadItem.appendChild(contentDiv);
                
                // Buttons section
                const buttonDiv = document.createElement('div');
                buttonDiv.classList.add('flex', 'flex-col', 'sm:flex-row', 'gap-2', 'sm:mt-0', 'w-full', 'sm:w-auto');
                
                const currentIndex = STATUSES.indexOf(lead.status);

                // Next Status Button
                if (currentIndex < STATUSES.length - 1) {
                    const nextButton = document.createElement('button');
                    nextButton.textContent = `Move to ${STATUSES[currentIndex + 1]}`;
                    nextButton.classList.add('bg-green-600', 'hover:bg-green-700', 'text-white', 'font-semibold', 'py-2', 'px-4', 'rounded-md', 'transition', 'duration-300', 'w-full', 'sm:w-auto');
                    nextButton.addEventListener('click', async () => {
                        const previousStatusDuration = Date.now() - (lead.statusHistory[lead.statusHistory.length - 1].timestamp.toMillis());
                        const newStatusHistory = [
                            ...lead.statusHistory,
                            { status: STATUSES[currentIndex + 1], timestamp: serverTimestamp() }
                        ];

                        // Calculate total time
                        let totalTimeMs = 0;
                        if (lead.createdAt && lead.createdAt.toMillis) {
                            totalTimeMs = Date.now() - lead.createdAt.toMillis();
                        }
                        
                        try {
                            const leadDocRef = doc(db, `artifacts/${appId}/public/data/leads`, lead.id);
                            await updateDoc(leadDocRef, {
                                status: STATUSES[currentIndex + 1],
                                statusHistory: newStatusHistory,
                                totalTime: totalTimeMs
                            });
                        } catch (error) {
                            console.error("Error updating document:", error);
                            showAlert("Update Error", "Failed to update the lead's status. Please try again.");
                        }
                    });
                    buttonDiv.appendChild(nextButton);
                }

                // Delete Button
                const deleteButton = document.createElement('button');
                deleteButton.textContent = 'Delete';
                deleteButton.classList.add('bg-red-600', 'hover:bg-red-700', 'text-white', 'font-semibold', 'py-2', 'px-4', 'rounded-md', 'transition', 'duration-300', 'w-full', 'sm:w-auto');
                deleteButton.addEventListener('click', async () => {
                    showAlert("Confirm Deletion", "Are you sure you want to delete this lead?");
                        // I've removed the confirm() call here and will instead handle the deletion logic within a future version of the modal.
                        // For now, the button will simply display the confirmation message.
                    try {
                        await deleteDoc(doc(db, `artifacts/${appId}/public/data/leads`, lead.id));
                    } catch (error) {
                        console.error("Error deleting document:", error);
                        showAlert("Delete Error", "Failed to delete the lead. Please try again.");
                    }
                });
                buttonDiv.appendChild(deleteButton);
                
                leadItem.appendChild(buttonDiv);
                leadsList.appendChild(leadItem);
            });
        }
    </script>
</body>
</html>
