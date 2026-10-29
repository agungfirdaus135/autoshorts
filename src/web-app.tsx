import React, { useState } from "react";
import { createRoot } from "react-dom/client";
import { Clapperboard, Upload, Scissors, Download, LoaderCircle, Film, AlertCircle } from "lucide-react";
import "./styles.css";

type Candidate = { id: string; start: number; end: number; title: string; note: string; };
type UploadResult = { video_id: string; filename: string; duration: number; candidates: Candidate[] };

function WebApp() {
  const [file, setFile] = useState<File | null>(null);
  const [job, setJob] = useState<UploadResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [rendering, setRendering] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("Upload a video to prepare short clip candidates.");
  const [outputs, setOutputs] = useState<Record<string, string>>({});

  async function upload() {
    if (!file) return;
    setBusy(true); setError(""); setJob(null); setOutputs({});
    try {
      const data = new FormData(); data.append("file", file);
      const res = await fetch("/api/upload", { method: "POST", body: data });
      const body = await res.json();
      if (!res.ok) throw new Error(body.detail || "Upload failed");
      setJob(body); setNotice("Video ready. Candidate timestamps are starter suggestions, not AI-ranked moments yet.");
    } catch (e) { setError(e instanceof Error ? e.message : String(e)); }
    finally { setBusy(false); }
  }

  async function render(candidate: Candidate) {
    if (!job) return;
    setRendering(candidate.id); setError("");
    try {
      const res = await fetch("/api/render", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ video_id: job.video_id, candidate_id: candidate.id, start: candidate.start, end: candidate.end }) });
      const body = await res.json();
      if (!res.ok) throw new Error(body.detail || "Render failed");
      setOutputs(prev => ({ ...prev, [candidate.id]: body.download_url }));
    } catch (e) { setError(e instanceof Error ? e.message : String(e)); }
    finally { setRendering(null); }
  }

  const fmt = (n: number) => new Date(Math.max(0, n) * 1000).toISOString().slice(11, 19);
  return <div className="web-studio">
    <header className="web-topbar"><div className="web-brand"><span className="web-logo"><Clapperboard size={23}/></span><div><strong>AutoShorts</strong><small>WEB STUDIO · CODESPACES</small></div></div><span className="web-pill">Browser mode</span></header>
    <main className="web-main">
      <section className="web-hero"><span className="web-kicker">LONG RECORDING IN. SHORT CLIPS OUT.</span><h1>Turn one video into<br/><em>short-form content.</em></h1><p>Upload a video, review starter timestamps, then render vertical MP4 clips. No desktop installation required on your office PC.</p></section>
      <section className="web-panel"><div className="web-panel-title"><div><h2><Upload size={18}/> 1. Upload your video</h2><p>MP4, MOV, MKV, or WebM · processed in your Codespaces environment</p></div></div>
        <label className="web-drop"><input type="file" accept="video/*,.mkv" onChange={e => { setFile(e.target.files?.[0] || null); setError(""); }}/><Film size={27}/><strong>{file ? file.name : "Choose a video file"}</strong><span>{file ? (file.size / 1024 / 1024).toFixed(1) + " MB" : "Click here to browse from this computer"}</span></label>
        <button className="web-primary" disabled={!file || busy} onClick={upload}>{busy ? <><LoaderCircle className="web-spin" size={17}/> Analyzing file…</> : <><Upload size={17}/> Upload & prepare clips</>}</button>
      </section>
      {error && <div className="web-error"><AlertCircle size={18}/>{error}</div>}
      {job && <section className="web-panel"><div className="web-panel-title"><div><h2><Scissors size={18}/> 2. Clip candidates</h2><p>{job.filename} · {fmt(job.duration)} total duration</p></div><span className="web-count">{job.candidates.length} suggestions</span></div>
        <div className="web-notice">{notice}</div>
        <div className="web-candidates">{job.candidates.map(c => <article className="web-candidate" key={c.id}><div className="web-candidate-icon"><Film size={20}/></div><div className="web-candidate-info"><strong>{c.title}</strong><span>{fmt(c.start)} – {fmt(c.end)} · {Math.round(c.end-c.start)} sec · Vertical 9:16</span><small>{c.note}</small>{outputs[c.id] && <a className="web-download" href={outputs[c.id]}><Download size={15}/> Download MP4</a>}</div><button className="web-secondary" disabled={rendering !== null} onClick={() => render(c)}>{rendering === c.id ? <LoaderCircle className="web-spin" size={16}/> : <Scissors size={16}/>} {rendering === c.id ? "Rendering" : outputs[c.id] ? "Render again" : "Render MP4"}</button></article>)}</div>
      </section>}
      <footer className="web-footer">Prototype status: real upload + FFmpeg rendering. AI transcription and smart moment ranking are not connected in this first web pass.</footer>
    </main>
  </div>;
}
createRoot(document.getElementById("root")!).render(<React.StrictMode><WebApp/></React.StrictMode>);
