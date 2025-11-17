


const chatMessages = document.getElementById('chatMessages');
const userInput = document.getElementById('userInput');
const sendBtn = document.getElementById('sendBtn');

function addMessage(message, isUser) {
    const messageDiv = document.createElement('div');
    messageDiv.className = isUser ? 'message user' : 'message';
    
    const avatar = document.createElement('div');
    avatar.className = isUser ? 'message-avatar user-avatar' : 'message-avatar bot-avatar';
    avatar.textContent = isUser ? '👩‍🎓' : '🤖';
    
    const textDiv = document.createElement('div');
    textDiv.className = isUser ? 'user-message' : 'bot-message';
    textDiv.textContent = message;
    
    messageDiv.appendChild(avatar);
    messageDiv.appendChild(textDiv);
    
    chatMessages.appendChild(messageDiv);
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

// Typing effect for initial welcome message
window.addEventListener('load', function() {
    const firstMessage = document.querySelector('.bot-message');
    if (firstMessage) {
        const text = firstMessage.textContent;
        firstMessage.textContent = '';
        let i = 0;
        
        function type() {
            if (i < text.length) {
                firstMessage.textContent += text.charAt(i);
                i++;
                chatMessages.scrollTop = chatMessages.scrollHeight;
                setTimeout(type, 20);
            }
        }
        
        setTimeout(type, 400);
    }
});

function formatBotMessage(text) {
    let formatted = text
        .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
        .replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer" style="color: #667eea; text-decoration: underline;">$1</a>')
        .replace(/(\d+)\.\s/g, '<br>$1. ')
        .replace(/\n/g, '<br>');
    
    return formatted;
}

// ===== FOLLOW-UP SUGGESTIONS ===== 

function displayFollowUpSuggestions(followUps) {
    // Remove any existing suggestions
    const existingSuggestions = document.querySelectorAll('.follow-up-suggestions');
    existingSuggestions.forEach(el => el.remove());
    
    if (!followUps || followUps.length === 0) return;
    
    const suggestionsContainer = document.createElement('div');
    suggestionsContainer.className = 'follow-up-suggestions';
    
    const headerDiv = document.createElement('div');
    headerDiv.className = 'suggestions-header';
    headerDiv.innerHTML = `
        <span class="suggestions-icon">💡</span>
        <span>You might also want to know:</span>
    `;
    
    suggestionsContainer.appendChild(headerDiv);
    
    const buttonsContainer = document.createElement('div');
    buttonsContainer.className = 'suggestions-buttons';
    
    followUps.forEach((suggestion, index) => {
        const button = document.createElement('button');
        button.className = 'suggestion-button';
        button.textContent = suggestion;
        button.onclick = () => handleSuggestionClick(suggestion);
        
        button.style.opacity = '0';
        button.style.transform = 'translateY(10px)';
        button.style.transition = 'all 0.3s ease';
        
        setTimeout(() => {
            button.style.opacity = '1';
            button.style.transform = 'translateY(0)';
        }, index * 100);
        
        buttonsContainer.appendChild(button);
    });
    
    suggestionsContainer.appendChild(buttonsContainer);
    chatMessages.appendChild(suggestionsContainer);
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

function handleSuggestionClick(suggestion) {
    userInput.value = suggestion;
    sendMessage();
    
    const suggestions = document.querySelectorAll('.follow-up-suggestions');
    suggestions.forEach(el => {
        el.style.opacity = '0';
        setTimeout(() => el.remove(), 300);
    });
}

// ===== SEND MESSAGE ===== 

async function sendMessage() {
    const message = userInput.value.trim();
    if (!message) return;

    addMessage(message, true);
    userInput.value = '';
    
    const botMessageDiv = document.createElement('div');
    botMessageDiv.className = 'message';
    
    const avatar = document.createElement('div');
    avatar.className = 'message-avatar bot-avatar';
    avatar.textContent = '👩‍🏫';
    
    const contentDiv = document.createElement('div');
    contentDiv.className = 'bot-message';
    contentDiv.id = 'streaming-message';
    
    botMessageDiv.appendChild(avatar);
    botMessageDiv.appendChild(contentDiv);
    chatMessages.appendChild(botMessageDiv);
    chatMessages.scrollTop = chatMessages.scrollHeight;

    try {
        const response = await fetch('/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message })
        });

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let fullText = '';
        const DELAY_MS = 20;

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            const chunk = decoder.decode(value);
            const lines = chunk.split('\n');

            for (const line of lines) {
                if (line.startsWith('data: ')) {
                    try {
                        const data = JSON.parse(line.slice(6));
                        
                        if (data.error) {
                            contentDiv.innerHTML = formatBotMessage('Sorry, I encountered an error. Please try again.');
                            break;
                        }
                        
                        if (data.content) {
                            fullText += data.content;
                            contentDiv.innerHTML = formatBotMessage(fullText);
                            chatMessages.scrollTop = chatMessages.scrollHeight;
                            await new Promise(resolve => setTimeout(resolve, DELAY_MS));
                        }
                        
                        if (data.done) {
                            contentDiv.id = '';
                            
                            if (data.follow_ups && Array.isArray(data.follow_ups) && data.follow_ups.length > 0) {
                                setTimeout(() => {
                                    displayFollowUpSuggestions(data.follow_ups);
                                }, 100);
                            }
                        }
                    } catch (e) {
                        // Silently skip invalid JSON
                    }
                }
            }
        }
    } catch (error) {
        const streamingMsg = document.getElementById('streaming-message');
        if (streamingMsg) {
            streamingMsg.innerHTML = formatBotMessage('Connection error. Please check if the server is running.');
        }
    }
}

// Event listeners
sendBtn.addEventListener('click', sendMessage);
userInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') {
        sendMessage();
    }
});