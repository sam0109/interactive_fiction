document.addEventListener('DOMContentLoaded', () => {
    const characterSelect = document.getElementById('character-select');
    const characterPortrait = document.getElementById('character-portrait');
    const portraitPlaceholder = document.getElementById('portrait-placeholder');
    const chatBox = document.getElementById('chat-box');
    const chatInput = document.getElementById('chat-input');
    const sendButton = document.getElementById('send-button');
    // Inventory elements
    const inventoryDisplay = document.getElementById('inventory-display');
    const inventoryLoading = document.getElementById('inventory-loading');
    const inventoryContent = document.getElementById('inventory-content');
    const inventoryMoney = document.getElementById('inventory-money');
    const inventoryItems = document.getElementById('inventory-items');
    const inventoryError = document.getElementById('inventory-error');

    let selectedCharacterName = null;
    let isThinking = false;

    // --- Initial Load ---
    updatePlayerInventoryDisplay(); // Fetch player inventory on load

    // --- Event Listeners ---
    characterSelect.addEventListener('change', async () => {
        selectedCharacterName = characterSelect.value;
        updateCharacterPortrait();
        clearChat();
        // updateInventoryDisplay(); // REMOVED - No longer updating based on NPC selection

        if (selectedCharacterName) {
            // Fetch HISTORY for selected character
            chatInput.disabled = true;
            sendButton.disabled = true;
            addSystemMessage("Loading history...");
            try {
                const response = await fetch(`/history/${encodeURIComponent(selectedCharacterName)}`);
                clearChat();
                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }
                const history = await response.json();
                if (history.length > 0) {
                    console.log("Loading history:", history);
                    history.forEach(msg => {
                        if (msg && msg.role && typeof msg.text !== 'undefined') {
                            addChatMessage(msg.role, msg.text);
                        } else {
                            console.warn("Skipping invalid message in history:", msg);
                        }
                    });
                } else {
                    addSystemMessage(`You approach ${selectedCharacterName}.`);
                }
                chatInput.disabled = false;
                sendButton.disabled = false;
                chatInput.focus();
            } catch (error) {
                console.error("Error fetching history:", error);
                clearChat();
                addErrorMessage("Error loading conversation history.");
            }
        } else {
            chatInput.disabled = true;
            sendButton.disabled = true;
        }
    });

    sendButton.addEventListener('click', sendMessage);
    chatInput.addEventListener('keypress', (event) => {
        if (event.key === 'Enter' && !isThinking && selectedCharacterName) {
            sendMessage();
        }
    });

    // --- UI Functions ---
    function updateCharacterPortrait() {
        if (selectedCharacterName) {
            const imageUrl = `/character_image/${encodeURIComponent(selectedCharacterName)}`;
            characterPortrait.src = imageUrl;
            characterPortrait.style.display = 'block';
            portraitPlaceholder.style.display = 'none';
            characterPortrait.onerror = () => {
                characterPortrait.style.display = 'none';
                portraitPlaceholder.textContent = `(Image not found for ${selectedCharacterName})`;
                portraitPlaceholder.style.display = 'block';
            };
        } else {
            characterPortrait.style.display = 'none';
            portraitPlaceholder.textContent = 'Select a character to see their portrait.';
            portraitPlaceholder.style.display = 'block';
        }
    }

    // Renamed function for clarity
    async function updatePlayerInventoryDisplay() {
        // inventoryLoading.style.display = 'block'; // Not needed - player inventory loads initially
        inventoryContent.style.display = 'none';
        inventoryError.style.display = 'none';
        inventoryItems.innerHTML = '<li>(None)</li>';
        inventoryMoney.textContent = '0';

        try {
            const response = await fetch(`/player_inventory`); // Fetch from the new route
            if (!response.ok) {
                let errorMsg = `HTTP error! status: ${response.status}`;
                try { const errData = await response.json(); errorMsg = errData.error || errorMsg; } catch (e) { }
                throw new Error(errorMsg);
            }
            const inventory = await response.json();

            inventoryMoney.textContent = inventory.money || 0;
            inventoryItems.innerHTML = ''; // Clear default
            if (inventory.items && Object.keys(inventory.items).length > 0) {
                for (const [item, count] of Object.entries(inventory.items)) {
                    const li = document.createElement('li');
                    li.textContent = `${item} (x${count})`;
                    inventoryItems.appendChild(li);
                }
            } else {
                inventoryItems.innerHTML = '<li>(None)</li>';
            }
            inventoryContent.style.display = 'block';
        } catch (error) {
            console.error("Error fetching player inventory:", error);
            inventoryError.textContent = `Error loading your inventory: ${error.message}`;
            inventoryError.style.display = 'block';
        } finally {
            // inventoryLoading.style.display = 'none'; // Not needed
        }
    }

    function clearChat() {
        chatBox.innerHTML = '';
    }

    // Only displays messages, history is managed server-side
    function addChatMessage(role, text) {
        const messageDiv = document.createElement('div');
        messageDiv.classList.add('chat-message'); // Base class
        let prefix = "";
        let cssClass = "";

        switch (role.toLowerCase()) { // Use lowercase for case-insensitivity
            case 'player':
                cssClass = 'user-message';
                prefix = "You: ";
                break;
            case 'character':
                cssClass = 'character-message';
                const characterName = selectedCharacterName || 'Character';
                prefix = `${characterName}: `;
                break;
            case 'system':
                cssClass = 'system-message';
                // No prefix for system messages (like actions, thinking)
                break;
            case 'error':
                cssClass = 'system-message'; // Use system style
                prefix = "[Error] "; // Add error prefix
                break;
            default:
                console.warn("Unknown chat message role - styling as System:", role);
                cssClass = 'system-message'; // Fallback to system style
                prefix = `[${role}] `; // Use original role as prefix if unknown
        }

        messageDiv.classList.add(cssClass);
        messageDiv.textContent = `${prefix}${text}`;

        chatBox.appendChild(messageDiv);
        chatBox.scrollTop = chatBox.scrollHeight;
    }

    // Keep helper functions, they now correctly call addChatMessage with 'System' or 'Error'
    function addSystemMessage(text) {
        addChatMessage('System', text);
    }

    function addErrorMessage(text) {
        addChatMessage('Error', text);
    }

    // --- Send Message Logic ---
    async function sendMessage() {
        const prompt = chatInput.value.trim();
        if (!prompt || !selectedCharacterName || isThinking) {
            return;
        }

        addChatMessage('Player', prompt);
        chatInput.value = '';
        isThinking = true;
        sendButton.disabled = true;
        chatInput.disabled = true;

        const thinkingMessageDiv = document.createElement('div');
        thinkingMessageDiv.classList.add('thinking-message');
        thinkingMessageDiv.textContent = `${selectedCharacterName} is thinking...`;
        thinkingMessageDiv.id = 'thinking-indicator';
        chatBox.appendChild(thinkingMessageDiv);
        chatBox.scrollTop = chatBox.scrollHeight;

        try {
            const response = await fetch('/chat', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    character_name: selectedCharacterName,
                    prompt: prompt,
                }),
            });

            const thinkingIndicator = document.getElementById('thinking-indicator');
            if (thinkingIndicator) chatBox.removeChild(thinkingIndicator);

            if (!response.ok) {
                let errorText = 'Failed to get response';
                try {
                    const errorData = await response.json();
                    errorText = errorData.error || errorText;
                } catch (e) { /* Ignore */ }
                console.error("Chat API Error:", response.status, errorText);
                addErrorMessage(`Error: ${errorText}`);
                // Display a generic fallback message from the character
                addChatMessage('Character', `(My mind feels muddled right now...)`);
            } else {
                const data = await response.json();
                // Display the character response first (dialogue part)
                if (data.response) { // Check if dialogue exists
                    addChatMessage('Character', data.response);
                }

                // Display the action result separately using the 'System' role
                if (data.action_result) {
                    addChatMessage('System', data.action_result); // Use 'System' role
                }

                // NOW check the flag and update inventory if needed
                if (data.player_inventory_updated === true) {
                    console.log("Server indicated player inventory updated, refreshing display...");
                    updatePlayerInventoryDisplay();
                }
            }
        } catch (error) {
            console.error("Fetch Error:", error);
            const thinkingIndicator = document.getElementById('thinking-indicator');
            if (thinkingIndicator) chatBox.removeChild(thinkingIndicator);
            addErrorMessage('Could not connect to the server.');
            // Display a generic fallback message from the character
            addChatMessage('Character', `(My connection seems fuzzy...)`);
        } finally {
            isThinking = false;
            if (characterSelect.value) {
                chatInput.disabled = false;
                sendButton.disabled = false;
                chatInput.focus();
            }
        }
    }
}); 