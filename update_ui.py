import re
import os

NEW_HTML_CODE = '''html_code = """
<!DOCTYPE html>
<html>
<head>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
  body {
    margin: 0;
    padding: 0;
    font-family: 'Inter', sans-serif;
    background: transparent;
  }
  .voice-card {
    background: linear-gradient(145deg, #ffffff, #f8fafc);
    border: 1px solid #e2e8f0;
    border-radius: 16px;
    padding: 24px;
    box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.05), 0 8px 10px -6px rgba(0, 0, 0, 0.01);
    display: flex;
    flex-direction: column;
    align-items: center;
    transition: transform 0.2s ease, box-shadow 0.2s ease;
  }
  .voice-card:hover {
    box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04);
  }
  .controls {
    display: flex;
    gap: 12px;
    margin-bottom: 20px;
  }
  .btn {
    border: none;
    padding: 10px 20px;
    font-size: 15px;
    font-weight: 600;
    border-radius: 9999px;
    cursor: pointer;
    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
    display: flex;
    align-items: center;
    gap: 8px;
    font-family: 'Inter', sans-serif;
  }
  .btn:disabled {
    opacity: 0.5;
    cursor: not-allowed;
    transform: scale(1) !important;
  }
  .btn-primary {
    background: linear-gradient(135deg, #0ea5e9 0%, #2563eb 100%);
    color: white;
    box-shadow: 0 4px 14px 0 rgba(37, 99, 235, 0.39);
  }
  .btn-primary:hover:not(:disabled) {
    transform: translateY(-2px);
    box-shadow: 0 6px 20px rgba(37, 99, 235, 0.4);
  }
  .btn-danger {
    background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%);
    color: white;
    box-shadow: 0 4px 14px 0 rgba(239, 68, 68, 0.39);
  }
  .btn-danger:hover:not(:disabled) {
    transform: translateY(-2px);
    box-shadow: 0 6px 20px rgba(239, 68, 68, 0.4);
  }
  .btn-secondary {
    background: white;
    color: #4b5563;
    border: 1px solid #d1d5db;
  }
  .btn-secondary:hover:not(:disabled) {
    background: #f9fafb;
    color: #111827;
  }
  .status-container {
    display: flex;
    align-items: center;
    gap: 8px;
    background: #f1f5f9;
    padding: 8px 16px;
    border-radius: 9999px;
    font-size: 13px;
    color: #475569;
    font-weight: 500;
    margin-bottom: 16px;
    border: 1px solid #e2e8f0;
  }
  .pulse-dot {
    height: 10px;
    width: 10px;
    background-color: #94a3b8;
    border-radius: 50%;
    display: inline-block;
  }
  .is-active .pulse-dot {
    background-color: #22c55e;
    animation: pulse-green 1.5s infinite;
  }
  .is-listening .pulse-dot {
    background-color: #ef4444;
    animation: pulse-red 1.5s infinite;
  }
  @keyframes pulse-green {
    0% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(34, 197, 94, 0.7); }
    70% { transform: scale(1.1); box-shadow: 0 0 0 6px rgba(34, 197, 94, 0); }
    100% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(34, 197, 94, 0); }
  }
  @keyframes pulse-red {
    0% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(239, 68, 68, 0.7); }
    70% { transform: scale(1.2); box-shadow: 0 0 0 8px rgba(239, 68, 68, 0); }
    100% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(239, 68, 68, 0); }
  }
  .transcript-box {
    width: 100%;
    background: white;
    border-radius: 12px;
    padding: 16px;
    min-height: 90px;
    max-height: 150px;
    overflow-y: auto;
    border: 1px solid #e5e7eb;
    box-sizing: border-box;
    display: flex;
    flex-direction: column;
    gap: 8px;
  }
  .message {
    line-height: 1.5;
    font-size: 14px;
  }
  .msg-you { color: #64748b; }
  .msg-ai { color: #0f172a; font-weight: 500; }
  .msg-error {
    color: #ef4444;
    background: #fef2f2;
    padding: 12px;
    border-radius: 8px;
    font-size: 13px;
    border: 1px solid #fecaca;
  }
</style>
</head>
<body>
<div class="voice-card">
  <div class="controls">
    <button id="startBtn" class="btn btn-primary">
      <svg width="18" height="18" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z"></path></svg>
      Start Voice Mode
    </button>
    <button id="stopBtn" class="btn btn-secondary" disabled>Stop</button>
    <button id="bargeInBtn" class="btn btn-danger" disabled>
      <svg width="18" height="18" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 10a1 1 0 011-1h4a1 1 0 011 1v4a1 1 0 01-1 1h-4a1 1 0 01-1-1v-4z"></path></svg>
      Interrupt
    </button>
  </div>
  
  <div id="statusContainer" class="status-container">
    <span id="pulseDot" class="pulse-dot"></span>
    <span id="status">Disconnected</span>
  </div>
  
  <div class="transcript-box" id="transcriptBox">
    <div class="message msg-you" style="text-align: center; margin-top: 10px;">Ready to chat! Press Start Voice Mode.</div>
  </div>
</div>

<script>
  let ws = null, audioContext = null, mediaStream = null, processor = null, isRecording = false;
  const startBtn = document.getElementById('startBtn'), stopBtn = document.getElementById('stopBtn'),
        bargeInBtn = document.getElementById('bargeInBtn'), statusDiv = document.getElementById('status'),
        transcriptBox = document.getElementById('transcriptBox'), statusContainer = document.getElementById('statusContainer');
        
  function addMessage(text, type) {
    if (transcriptBox.innerHTML.includes("Ready to chat!")) transcriptBox.innerHTML = "";
    if (type === "error") {
      transcriptBox.innerHTML = `<div class="message msg-error">${text}</div>`;
    } else if (type === "you") {
      transcriptBox.innerHTML += `<div class="message msg-you"><strong>You:</strong> ${text}</div>`;
    } else if (type === "ai") {
      transcriptBox.innerHTML += `<div class="message msg-ai"><strong>AI:</strong> ${text}</div>`;
    }
    transcriptBox.scrollTop = transcriptBox.scrollHeight;
  }
        
  function setStatus(text, state) {
    statusDiv.innerText = text;
    statusContainer.className = 'status-container ' + state;
  }
        
  startBtn.onclick = async () => {
    try {
      ws = new WebSocket('ws://localhost:8000/ws/audio');
      ws.onopen = () => {
        setStatus("Connected. Listening...", "is-listening");
        startBtn.disabled = true; stopBtn.disabled = false; bargeInBtn.disabled = false;
        startRecording();
      };
      ws.onmessage = async (event) => {
        if (typeof event.data === "string") {
          let data = JSON.parse(event.data);
          if (data.type === "status") {
             if (data.message.includes("Speaking")) setStatus(data.message, "is-active");
             else if (data.message.includes("Listening") || data.message.includes("Thinking")) setStatus(data.message, "is-listening");
             else setStatus(data.message, "");
          }
          else if (data.type === "transcript") addMessage(data.text, "you");
          else if (data.type === "response") addMessage(data.text, "ai");
          else if (data.type === "error") addMessage(data.message, "error");
        } else {
          playAudio(event.data);
        }
      };
      ws.onclose = () => {
        setStatus("Disconnected", "");
        startBtn.disabled = false; stopBtn.disabled = true; bargeInBtn.disabled = true;
        stopRecording();
      };
    } catch (e) { setStatus("Error connecting", ""); addMessage("Could not connect to backend", "error"); }
  };
  stopBtn.onclick = () => { if (ws) ws.close(); };
  bargeInBtn.onclick = () => {
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({type: "barge_in"}));
      setStatus("Interrupted. Listening again...", "is-listening");
    }
  };
  async function startRecording() {
    mediaStream = await navigator.mediaDevices.getUserMedia({ audio: true, video: false });
    audioContext = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: 16000 });
    const source = audioContext.createMediaStreamSource(mediaStream);
    processor = audioContext.createScriptProcessor(4096, 1, 1);
    processor.onaudioprocess = (e) => {
      if (!ws || ws.readyState !== WebSocket.OPEN) return;
      const inputData = e.inputBuffer.getChannelData(0);
      const pcmData = new Int16Array(inputData.length);
      for (let i = 0; i < inputData.length; i++) {
        let s = Math.max(-1, Math.min(1, inputData[i]));
        pcmData[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
      }
      ws.send(pcmData.buffer);
    };
    source.connect(processor); processor.connect(audioContext.destination);
  }
  function stopRecording() {
    if (processor) { processor.disconnect(); processor = null; }
    if (mediaStream) { mediaStream.getTracks().forEach(t => t.stop()); mediaStream = null; }
    if (audioContext) { audioContext.close(); audioContext = null; }
  }
  async function playAudio(blob) {
    const audioUrl = URL.createObjectURL(blob);
    const audio = new Audio(audioUrl);
    audio.play();
  }
</script>
</body>
</html>
"""
    components.html(html_code, height=360)'''

def patch_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # We will use regex to find the html_code assignment and the components.html call
    pattern = re.compile(r'html_code = """[\s\S]*?components\.html\(html_code, height=\d+\)', re.MULTILINE)
    
    if pattern.search(content):
        new_content = pattern.sub(NEW_HTML_CODE.replace('\\', '\\\\'), content)
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(new_content)
        print(f"Patched {filepath}")
    else:
        print(f"Pattern not found in {filepath}")

patch_file(r"c:\Users\Dell\Desktop\csc-mitra-ai1\streamlit_app.py")
patch_file(r"c:\Users\Dell\Desktop\csc-mitra-ai1\pages\1_CSC_Assistant.py")

import mcp_provides_tool_pylanceRunCodeSnippet

# Define your code snippet as a string
code_snippet = """
print("Hello, World!")
"""

# Run the code snippet in the workspace environment
mcp_provides_tool_pylanceRunCodeSnippet.mcp_provides_tool_pylanceRunCodeSnippet(
    workspaceRoot="C:\\Users\\Dell\\Downloads\\chaitcsc-main",
    codeSnippet=code_snippet,
    timeout=30000,  # Optional: set a timeout in milliseconds (default is 30 seconds)
    workingDirectory="C:\\Users\\Dell\\Downloads\\chaitcsc-main"
)
