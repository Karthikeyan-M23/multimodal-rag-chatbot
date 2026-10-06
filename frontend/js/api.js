const API = {

  async createSession() {
    const res = await fetch('/api/session', {
      method: 'POST'
    });

    if (!res.ok) {
      throw new Error('Could not create a session.');
    }

    return res.json();
  },


  async processKnowledge(sessionId, files, urls) {

    const form = new FormData();

    form.append('session_id', sessionId);
    form.append('urls', urls || '');

    /*
     * IMPORTANT:
     * Every file must use append().
     *
     * Do NOT use form.set('files', file).
     */
    for (const file of files) {
      form.append('files', file, file.name);
    }

    /*
     * Debug information.
     * This lets us verify exactly what is being sent.
     */
    console.log(
      'Uploading files:',
      files.map(file => file.name)
    );

    const res = await fetch(
      '/api/knowledge/process',
      {
        method: 'POST',
        body: form
      }
    );

    const data = await res.json();

    if (!res.ok) {
      throw new Error(
        data.detail ||
        'Knowledge-base processing failed.'
      );
    }

    return data;
  },


  async status(sessionId) {

    const res = await fetch(
      `/api/knowledge/status/${encodeURIComponent(sessionId)}`
    );

    const data = await res.json();

    if (!res.ok) {
      throw new Error(
        data.detail ||
        'Could not read knowledge-base status.'
      );
    }

    return data;
  },


  async resetChat(sessionId) {

    const res = await fetch(
      `/api/chat/reset/${encodeURIComponent(sessionId)}`,
      {
        method: 'POST'
      }
    );

    const data = await res.json();

    if (!res.ok) {
      throw new Error(
        data.detail ||
        'Could not reset conversation.'
      );
    }

    return data;
  },


  async clearKnowledge(sessionId) {

    const res = await fetch(
      `/api/knowledge/${encodeURIComponent(sessionId)}`,
      {
        method: 'DELETE'
      }
    );

    const data = await res.json();

    if (!res.ok) {
      throw new Error(
        data.detail ||
        'Could not clear knowledge base.'
      );
    }

    return data;
  },


  async chat(sessionId, question) {

    const res = await fetch(
      '/api/chat',
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          session_id: sessionId,
          question: question
        })
      }
    );

    const data = await res.json();

    if (!res.ok) {
      throw new Error(
        data.detail ||
        'Chat request failed.'
      );
    }

    return data;
  },


  async health() {

    const res = await fetch('/api/health');

    if (!res.ok) {
      throw new Error('API unavailable.');
    }

    return res.json();
  }

};