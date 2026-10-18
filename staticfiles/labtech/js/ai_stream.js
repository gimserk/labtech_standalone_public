/* Reassemble Server-Sent Events across arbitrary HTTP and UTF-8 chunk boundaries. */
window.LabTechAIStream = {
    async consume(response, onText) {
        if (!response.body) throw new Error('The AI provider did not return a response stream.');
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let pending = '';
        let fullResponse = '';
        function processEvents() {
            pending = pending.replace(/\r\n/g, '\n');
            let boundary;
            while ((boundary = pending.indexOf('\n\n')) !== -1) {
                const event = pending.slice(0, boundary);
                pending = pending.slice(boundary + 2);
                const data = event.split('\n').filter(line => line.startsWith('data:'))
                    .map(line => line.slice(5).trimStart()).join('\n');
                if (!data || data === '[DONE]') continue;
                let packet;
                try {
                    packet = JSON.parse(data);
                } catch (error) {
                    throw new Error('The AI provider sent an invalid stream event.');
                }
                if (packet.error) throw new Error('The AI provider interrupted the response.');
                const delta = packet.choices?.[0]?.delta?.content;
                if (typeof delta === 'string') {
                    fullResponse += delta;
                    onText(fullResponse);
                }
            }
        }
        try {
            while (true) {
                const { done, value } = await reader.read();
                if (done) break;
                pending += decoder.decode(value, { stream: true });
                processEvents();
            }
            pending += decoder.decode();
            processEvents();
            if (!fullResponse) throw new Error('The AI provider returned an empty answer.');
            return fullResponse;
        } finally {
            reader.releaseLock();
        }
    }
};
