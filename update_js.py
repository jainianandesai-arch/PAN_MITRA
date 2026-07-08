import re

NEW_JS = """
  async function playAudio(data) {
    try {
      if (!audioContext) {
         audioContext = new (window.AudioContext || window.webkitAudioContext)();
      }
      if (audioContext.state === 'suspended') {
         await audioContext.resume();
      }
      const arrayBuffer = await new Blob([data]).arrayBuffer();
      const audioBuffer = await audioContext.decodeAudioData(arrayBuffer);
      const source = audioContext.createBufferSource();
      source.buffer = audioBuffer;
      source.connect(audioContext.destination);
      source.start(0);
    } catch (e) {
      console.error("Web Audio API failed, falling back to HTML5 Audio:", e);
      try {
        const blob = new Blob([data], { type: 'audio/mpeg' });
        const audioUrl = URL.createObjectURL(blob);
        const audio = new Audio(audioUrl);
        await audio.play();
      } catch (err) {
        addMessage("Speaker blocked by browser. Please click anywhere on the page to enable audio.", "error");
      }
    }
  }
</script>
"""

def patch_js(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    pattern = re.compile(r'async function playAudio\(data\) \{[\s\S]*?\}[\s\S]*?</script>', re.MULTILINE)
    
    if pattern.search(content):
        new_content = pattern.sub(NEW_JS, content)
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(new_content)
        print(f"Patched JS in {filepath}")
    else:
        print(f"Pattern not found in {filepath}")

patch_js(r"c:\Users\Dell\Desktop\csc-mitra-ai1\streamlit_app.py")
patch_js(r"c:\Users\Dell\Desktop\csc-mitra-ai1\pages\1_CSC_Assistant.py")
