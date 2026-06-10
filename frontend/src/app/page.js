'use client'

import { useState, useRef, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';

export default function YapEngine() {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [documents, setDocuments] = useState([]);
  const [loading, setLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [sourceContext, setSourceContext] = useState(null);
  
  // ✅ LOGIC: Session ID Tracking
  const [isDragging, setIsDragging] = useState(false);
  const [sessionId, setSessionId] = useState('');

  const messagesEndRef = useRef(null);
  const fileInputRef = useRef(null);

  const API_URL = "https://yap-engine.onrender.com";

  // 1. GENERATE SESSION ID (Hidden Logic)
  useEffect(() => {
    let id = localStorage.getItem("yap_session_id");
    if (!id) {
      id = "user_" + Math.random().toString(36).substr(2, 9);
      localStorage.setItem("yap_session_id", id);
    }
    setSessionId(id);
    
    const saved = localStorage.getItem('chat_history');
    if (saved) setMessages(JSON.parse(saved));
  }, []);

  // 2. SAVE HISTORY
  useEffect(() => {
    localStorage.setItem('chat_history', JSON.stringify(messages));
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // ✅ LOGIC: Upload with Session ID
  const processFile = async (file) => {
    if (!file) return;

    setUploading(true);
    const formData = new FormData();
    formData.append("file", file);

    try {
      const res = await fetch(`${API_URL}/upload`, { 
        method: "POST", 
        headers: { "x-session-id": sessionId }, // <--- SEND ID
        body: formData 
      });

      if (!res.ok) throw new Error("Upload failed");

      setDocuments(prev => [...prev, file.name]);
      
      setSourceContext({
        title: "File Uploaded Successfully",
        content: `Filename: ${file.name}\nSize: ${(file.size / 1024).toFixed(2)} KB\nType: ${file.type}\n\nYou can now ask questions!`
      });

      setMessages(prev => [...prev, { 
        type: 'ai', 
        text: `✅ Successfully uploaded "${file.name}". You can now ask questions about it!` 
      }]);
    } catch (err) {
      console.error(err);
      setMessages(prev => [...prev, { 
        type: 'ai', 
        text: "❌ Upload failed. The backend might be busy or restarting." 
      }]);
    } finally {
      setUploading(false);
      setIsDragging(false); 
    }
  };

  const handleFileInput = (e) => {
    processFile(e.target.files?.[0]);
  };

  const handleDragOver = (e) => { e.preventDefault(); setIsDragging(true); };
  const handleDragLeave = (e) => { e.preventDefault(); setIsDragging(false); };
  const handleDrop = (e) => {
    e.preventDefault();
    setIsDragging(false);
    const file = e.dataTransfer.files?.[0];
    if (file && file.type === "application/pdf") {
      processFile(file);
    } else {
      alert("Please drop a valid PDF file.");
    }
  };

  const handleSummarize = () => {
    if (loading) return;
    sendMessage("Summarize this document in 5 key bullet points.");
  };

  // ✅ LOGIC: Chat with Session ID
  const sendMessage = async (textOverride = null) => {
    const textToSend = textOverride || input;
    if (!textToSend.trim() || loading) return;

    if (!textOverride) setInput('');
    setMessages(prev => [...prev, { type: 'user', text: textToSend }]);
    setLoading(true);

    try {
      const res = await fetch(`${API_URL}/chat`, {
        method: "POST",
        headers: { 
            "Content-Type": "application/json",
            "x-session-id": sessionId // <--- SEND ID
        },
        body: JSON.stringify({ question: textToSend }),
      });

      if (!res.ok) throw new Error("Chat request failed");

      const data = await res.json();

      if (data.source) {
        setSourceContext({
          title: "Context Used",
          content: data.source
        });
      }

      setMessages(prev => [...prev, { 
        type: 'ai', 
        text: data.answer || "I couldn't find an answer.",
        source: data.source || null
      }]);
    } catch (err) {
      console.error(err);
      setMessages(prev => [...prev, { 
        type: 'ai', 
        text: "⚠️ Error connecting to backend. Is it running?" 
      }]);
    } finally {
      setLoading(false);
    }
  };

  // --- THE UI CODE (Restored to the Original Yellow Theme) ---
  return (
    <div style={{
      height: '100vh',
      display: 'flex',
      flexDirection: 'column',
      background: 'linear-gradient(to bottom right, #fffbeb, #fef3c7)'
    }}>

      {/* Header */}
      <header style={{
        height: '64px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '0 2rem',
        background: 'linear-gradient(to right, #fbbf24, #f59e0b)',
        boxShadow: '0 10px 15px -3px rgba(0, 0, 0, 0.1)'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <span style={{ fontSize: '1.875rem' }}>✨</span>
          <h1 style={{ fontSize: '1.5rem', fontWeight: '900', letterSpacing: '0.05em', color: '#78350f' }}>YAP ENGINE</h1>
        </div>
        <button 
          onClick={() => {
            localStorage.removeItem('chat_history');
            localStorage.removeItem('yap_session_id'); // ✅ RESET ID
            window.location.reload();
          }}
          style={{
            background: 'rgba(255,255,255,0.2)', border: 'none', padding: '0.5rem 1rem',
            borderRadius: '8px', color: '#78350f', fontWeight: '600', cursor: 'pointer', fontSize: '0.875rem'
          }}
        >
          🗑️ Reset Session
        </button>
      </header>

      {/* Main Content */}
      <div style={{ flex: 1, display: 'flex', overflow: 'hidden' }}>

        {/* Left Sidebar */}
        <aside style={{
          width: '20%', minWidth: '240px', background: 'rgba(255, 255, 255, 0.8)',
          backdropFilter: 'blur(10px)', borderRight: '1px solid #fcd34d', padding: '1rem',
          display: 'flex', flexDirection: 'column'
        }}>
          
          {/* Upload Area */}
          <div
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
            style={{
              marginBottom: '0.75rem',
              borderRadius: '12px',
              transition: 'all 0.2s',
              border: isDragging ? '2px dashed #78350f' : '2px dashed transparent',
              transform: isDragging ? 'scale(1.02)' : 'scale(1)',
            }}
          >
            <label style={{
              width: '100%', padding: '2rem 1rem', borderRadius: '12px',
              fontWeight: '600', color: '#78350f',
              background: uploading 
                ? '#d1d5db' 
                : isDragging ? '#fbbf24' : 'linear-gradient(to right, #fde047, #fbbf24)',
              border: 'none', cursor: uploading ? 'wait' : 'pointer',
              boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1)',
              textAlign: 'center', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '8px'
            }}>
              <span style={{ fontSize: '1.5rem' }}>{uploading ? '⏳' : '📂'}</span>
              <span>{uploading ? 'Uploading...' : isDragging ? 'Drop PDF Here!' : 'Upload PDF'}</span>
              <span style={{ fontSize: '0.7rem', opacity: 0.8, fontWeight: 'normal' }}>
                (Click or Drag & Drop)
              </span>
              
              <input 
                ref={fileInputRef} 
                type="file" 
                accept="application/pdf" 
                onChange={handleFileInput} 
                disabled={uploading} 
                style={{ display: 'none' }} 
              />
            </label>
          </div>

          {/* Summarize Button */}
          <button
            onClick={handleSummarize}
            disabled={loading || documents.length === 0}
            style={{
              width: '100%', padding: '0.75rem', marginBottom: '1.5rem', borderRadius: '12px',
              fontWeight: '600', color: 'white', background: (loading || documents.length === 0) ? '#d1d5db' : '#d97706',
              border: 'none', cursor: (loading || documents.length === 0) ? 'not-allowed' : 'pointer',
              boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1)', transition: 'all 0.2s'
            }}
          >
            ⚡ Summarize Doc
          </button>

          <div style={{ flex: 1, overflowY: 'auto' }}>
            <h3 style={{ fontSize: '0.75rem', fontWeight: '700', textTransform: 'uppercase', letterSpacing: '0.05em', color: '#b45309', marginBottom: '0.75rem' }}>Documents</h3>
            {documents.length === 0 ? (
              <p style={{ fontSize: '0.875rem', color: '#f59e0b', textAlign: 'center' }}>No documents yet</p>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                {documents.map((doc, i) => (
                  <div key={i} style={{
                    padding: '0.75rem', borderRadius: '8px', background: '#fef3c7', border: '1px solid #fcd34d',
                    display: 'flex', alignItems: 'center', gap: '0.5rem'
                  }}>
                    <span style={{ fontSize: '0.875rem' }}>📑</span>
                    <span style={{ fontSize: '0.875rem', color: '#78350f', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{doc}</span>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* ✅ Small visual ID at the bottom (Subtle) */}
          <div style={{ marginTop: 'auto', paddingTop: '1rem', textAlign: 'center', fontSize: '0.65rem', color: '#b45309', opacity: 0.6 }}>
            Session ID: {sessionId}
          </div>

        </aside>

        {/* Center - Chat Area */}
        <section style={{ width: '60%', display: 'flex', flexDirection: 'column' }}>
          <div style={{ flex: 1, overflowY: 'auto', padding: '1.5rem', display: 'flex', flexDirection: 'column', gap: '1rem' }}>
            {messages.length === 0 ? (
              <div style={{ height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                <div style={{ textAlign: 'center', maxWidth: '28rem' }}>
                  <div style={{ fontSize: '8rem', marginBottom: '1rem' }}>💬</div>
                  <h2 style={{ fontSize: '2rem', fontWeight: '700', color: '#78350f', marginBottom: '1rem' }}>Ask me anything</h2>
                  <p style={{ fontSize: '1.125rem', color: '#b45309' }}>Upload a PDF to get started.</p>
                </div>
              </div>
            ) : (
              <>
                {messages.map((msg, i) => (
                  <div key={i} style={{ display: 'flex', justifyContent: msg.type === 'user' ? 'flex-end' : 'flex-start' }}>
                    <div style={{
                      maxWidth: '75%', padding: '1rem', borderRadius: '16px',
                      boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1)',
                      background: msg.type === 'user' ? 'linear-gradient(to right, #fbbf24, #f59e0b)' : 'white',
                      color: msg.type === 'user' ? '#78350f' : '#1f2937',
                      border: msg.type === 'user' ? 'none' : '1px solid #fcd34d'
                    }}>
                      {/* Markdown Rendering */}
                      {msg.type === 'ai' ? (
                        <div style={{ lineHeight: '1.6', fontSize: '1rem' }}>
                           <ReactMarkdown components={{
                               ul: ({node, ...props}) => <ul style={{ marginLeft: '1.5rem', listStyleType: 'disc' }} {...props} />,
                               ol: ({node, ...props}) => <ol style={{ marginLeft: '1.5rem', listStyleType: 'decimal' }} {...props} />,
                               strong: ({node, ...props}) => <strong style={{ color: '#b45309', fontWeight: '800' }} {...props} />,
                             }}>
                             {msg.text}
                           </ReactMarkdown>
                        </div>
                      ) : (
                        <p>{msg.text}</p>
                      )}
                      
                      {msg.source && (
                        <div style={{ marginTop: '0.75rem', paddingTop: '0.5rem', borderTop: '1px solid #fcd34d', fontSize: '0.75rem', color: '#d97706' }}>
                          📍 Context: {msg.source.substring(0, 80)}...
                        </div>
                      )}
                    </div>
                  </div>
                ))}
                {loading && (
                   <div style={{ display: 'flex', justifyContent: 'flex-start' }}>
                    <div style={{ padding: '1rem', borderRadius: '16px', background: 'white', border: '1px solid #fcd34d' }}>
                      <span style={{color: '#b45309'}}>Thinking...</span>
                    </div>
                   </div>
                )}
                <div ref={messagesEndRef} />
              </>
            )}
          </div>

          <div style={{ padding: '1rem', background: 'rgba(255, 255, 255, 0.8)', backdropFilter: 'blur(10px)', borderTop: '1px solid #fcd34d' }}>
            <div style={{ display: 'flex', gap: '0.75rem', maxWidth: '80rem', margin: '0 auto' }}>
              <input
                value={input} onChange={(e) => setInput(e.target.value)}
                onKeyPress={(e) => e.key === 'Enter' && !loading && sendMessage(null)}
                disabled={loading}
                style={{
                  flex: 1, padding: '0.75rem 1.25rem', borderRadius: '12px', border: '2px solid #fcd34d',
                  outline: 'none', background: 'white', fontSize: '1rem', opacity: loading ? 0.5 : 1
                }}
                placeholder="Ask a question..."
              />
              <button
                onClick={() => sendMessage(null)} disabled={!input.trim() || loading}
                style={{
                  padding: '0.75rem 1.5rem', borderRadius: '12px', fontWeight: '600',
                  background: (!input.trim() || loading) ? '#d1d5db' : 'linear-gradient(to right, #fbbf24, #f59e0b)',
                  border: 'none', cursor: (!input.trim() || loading) ? 'not-allowed' : 'pointer', color: '#78350f'
                }}>
                ➤
              </button>
            </div>
          </div>
        </section>

        {/* Right Sidebar - Context */}
        <aside style={{ width: '20%', minWidth: '280px', background: 'white', borderLeft: '1px solid #fcd34d', padding: '1.25rem' }}>
          <h3 style={{ fontWeight: '700', color: '#78350f', marginBottom: '1rem' }}>📄 Source Context</h3>
          <div style={{ overflowY: 'auto', height: '90%' }}>
            {sourceContext ? (
              <div>
                <h4 style={{ fontSize: '0.875rem', fontWeight: '700', color: '#b45309', marginBottom: '0.5rem' }}>{sourceContext.title}</h4>
                <div style={{ padding: '1rem', background: '#fffbeb', borderRadius: '8px', border: '1px solid #fcd34d', fontSize: '0.85rem', color: '#4b5563', whiteSpace: 'pre-wrap' }}>
                  {sourceContext.content}
                </div>
              </div>
            ) : (
              <p style={{ fontSize: '0.875rem', color: '#f59e0b', textAlign: 'center' }}>Context will appear here.</p>
            )}
          </div>
        </aside>

      </div>
    </div>
  );
}