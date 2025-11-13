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

// Typing effect for initial message
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
    // Convert markdown-style formatting to HTML
    let formatted = text
        // Bold text: **text** to <strong>text</strong>
        .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
        // Links: [text](url) to <a href="url">text</a>
        .replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer" style="color: #667eea; text-decoration: underline;">$1</a>')
        // Bullet points: number followed by period
        .replace(/(\d+)\.\s/g, '<br>$1. ')
        // Line breaks for better readability
        .replace(/\n/g, '<br>');
    
    return formatted;
}

function addLoadingMessage() {
    const messageDiv = document.createElement('div');
    messageDiv.className = 'message';
    messageDiv.id = 'loadingMessage';
    
    // Add avatar for loading message
    const avatar = document.createElement('div');
    avatar.className = 'message-avatar bot-avatar';
    avatar.textContent = '👩‍🏫';
    
    const contentDiv = document.createElement('div');
    contentDiv.className = 'bot-message';
    contentDiv.innerHTML = '<span class="loading"></span> <span class="loading"></span> <span class="loading"></span>';
    
    messageDiv.appendChild(avatar);
    messageDiv.appendChild(contentDiv);
    chatMessages.appendChild(messageDiv);
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

function removeLoadingMessage() {
    const loading = document.getElementById('loadingMessage');
    if (loading) loading.remove();
}

async function sendMessage() {
    const message = userInput.value.trim();
    if (!message) return;

    addMessage(message, true);
    userInput.value = '';
    
    // Create a placeholder for streaming response WITH AVATAR
    const botMessageDiv = document.createElement('div');
    botMessageDiv.className = 'message';
    
    // Add bot avatar
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
                            contentDiv.id = ''; // Remove streaming id
                        }
                    } catch (e) {
                        // Skip invalid JSON
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

sendBtn.addEventListener('click', sendMessage);
userInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') sendMessage();
});

