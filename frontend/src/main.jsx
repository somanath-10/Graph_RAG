import React, { useEffect, useMemo, useState } from 'react';
import { createRoot } from 'react-dom/client';
import './styles.css';

const env = import.meta.env;
const API_BASE = env.VITE_API_URL || `${window.location.protocol}//${window.location.hostname}:8000/api`;
const APP_TITLE = env.VITE_APP_TITLE || 'Patent GraphRAG';
const APP_SUBTITLE = env.VITE_APP_SUBTITLE || 'React + FastAPI + OpenAI small models + Qdrant + Neo4j';
const DEFAULT_QUESTION = env.VITE_DEFAULT_QUESTION || 'What is the invention disclosed in this patent?';
const QUERY_TOP_K = intEnv(env.VITE_QUERY_TOP_K, 12);
const GRAPH_LIMIT = intEnv(env.VITE_GRAPH_LIMIT, 120);
const SOURCE_PREVIEW_CHARS = intEnv(env.VITE_SOURCE_PREVIEW_CHARS, 260);
const FACT_PREVIEW_CHARS = intEnv(env.VITE_FACT_PREVIEW_CHARS, 220);
const MINI_GRAPH_EDGE_LIMIT = intEnv(env.VITE_MINIGRAPH_EDGE_LIMIT, 12);
const EXAMPLE_QUESTIONS = listEnv(env.VITE_EXAMPLE_QUESTIONS, [
  'What is the invention in this patent?',
  'Who are the inventors and assignee?',
  'Summarize independent claim 1.',
  'List the main embodiments or examples.',
  'What measurements, ranges, or conditions are disclosed?'
]);

function App() {
  const [health, setHealth] = useState(null);
  const [status, setStatus] = useState('Ready');
  const [file, setFile] = useState(null);
  const [question, setQuestion] = useState(DEFAULT_QUESTION);
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(false);
  const [graph, setGraph] = useState({ nodes: [], edges: [] });

  useEffect(() => {
    fetch(`${API_BASE}/health`).then(r => r.json()).then(setHealth).catch(() => setHealth({ status: 'offline' }));
  }, []);

  async function ingestSample() {
    setLoading(true);
    setStatus('Ingesting sample patent. This calls OpenAI for embeddings and graph extraction...');
    try {
      const res = await fetch(`${API_BASE}/documents/ingest-sample`, { method: 'POST' });
      const data = await parseResponse(res);
      setStatus(`Ingested ${data.document_id}: ${data.chunks} chunks, ${data.graph_entities} entities, ${data.graph_relationships} relationships.`);
      await loadGraph();
    } catch (e) {
      setStatus(`Ingestion failed: ${e.message}`);
    } finally {
      setLoading(false);
    }
  }

  async function uploadPdf() {
    if (!file) return setStatus('Choose a PDF first.');
    setLoading(true);
    setStatus('Uploading and ingesting PDF...');
    try {
      const form = new FormData();
      form.append('file', file);
      const res = await fetch(`${API_BASE}/documents/upload`, { method: 'POST', body: form });
      const data = await parseResponse(res);
      setStatus(`Ingested ${data.document_id}: ${data.chunks} chunks, ${data.graph_entities} entities, ${data.graph_relationships} relationships.`);
      await loadGraph();
    } catch (e) {
      setStatus(`Upload failed: ${e.message}`);
    } finally {
      setLoading(false);
    }
  }

  async function askQuestion(e) {
    e?.preventDefault();
    const q = question.trim();
    if (!q) return;
    setMessages(prev => [...prev, { role: 'user', text: q }]);
    setLoading(true);
    setStatus('Retrieving context, evaluating it, and generating answer...');
    try {
      const res = await fetch(`${API_BASE}/query`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question: q, top_k: QUERY_TOP_K })
      });
      const data = await parseResponse(res);
      setMessages(prev => [...prev, { role: 'assistant', text: data.answer, sources: data.sources, facts: data.graph_facts, kept: data.kept_contexts }]);
      setStatus('Answer generated.');
    } catch (e) {
      setMessages(prev => [...prev, { role: 'assistant', text: `Error: ${e.message}` }]);
      setStatus('Query failed.');
    } finally {
      setLoading(false);
    }
  }

  async function loadGraph() {
    try {
      const res = await fetch(`${API_BASE}/graph?limit=${GRAPH_LIMIT}`);
      const data = await parseResponse(res);
      setGraph(data);
    } catch (e) {
      setStatus(`Could not load graph: ${e.message}`);
    }
  }

  const latestAssistant = [...messages].reverse().find(m => m.role === 'assistant');

  return (
    <div className="page">
      <header className="topbar">
        <div>
          <h1>{APP_TITLE}</h1>
          <p>{APP_SUBTITLE}</p>
        </div>
        <div className={`pill ${health?.status === 'ok' ? 'ok' : 'bad'}`}>API: {health?.status || 'checking'}</div>
      </header>

      <main className="layout">
        <section className="left panel">
          <h2>1. Ingest PDF</h2>
          <p className="muted">Use the included patent PDF or upload another patent PDF.</p>
          <button disabled={loading} onClick={ingestSample}>Ingest included sample patent</button>
          <div className="upload">
            <input type="file" accept="application/pdf" onChange={e => setFile(e.target.files?.[0] || null)} />
            <button disabled={loading || !file} onClick={uploadPdf}>Upload and ingest</button>
          </div>
          <div className="status">{status}</div>

          <h2>2. Ask</h2>
          <form onSubmit={askQuestion} className="askForm">
            <textarea value={question} onChange={e => setQuestion(e.target.value)} placeholder="Ask about claims, embodiments, examples, figures, ranges, or measured values..." />
            <button disabled={loading} type="submit">Ask GraphRAG</button>
          </form>

          <ExampleQuestions setQuestion={setQuestion} />
        </section>

        <section className="center panel chat">
          <h2>Answer</h2>
          {messages.length === 0 && <EmptyState />}
          {messages.map((m, idx) => <Message key={idx} message={m} />)}
        </section>

        <section className="right panel">
          <h2>Graph snapshot</h2>
          <button onClick={loadGraph} disabled={loading}>Refresh graph</button>
          <GraphSummary graph={graph} />
          <h2>Latest sources</h2>
          <SourceList sources={latestAssistant?.sources || []} />
          <h2>Latest graph facts</h2>
          <FactList facts={latestAssistant?.facts || []} />
        </section>
      </main>
    </div>
  );
}

function EmptyState() {
  return <div className="empty">Ingest the patent, then ask a question. Good first question: "{DEFAULT_QUESTION}"</div>;
}

function Message({ message }) {
  return (
    <div className={`message ${message.role}`}>
      <div className="role">{message.role === 'user' ? 'You' : 'Assistant'}</div>
      <div className="text">{message.text}</div>
      {message.kept?.length > 0 && (
        <details>
          <summary>Context evaluation</summary>
          <pre>{JSON.stringify(message.kept, null, 2)}</pre>
        </details>
      )}
    </div>
  );
}

function SourceList({ sources }) {
  if (!sources.length) return <p className="muted">No sources yet.</p>;
  return <div className="list">{sources.slice(0, 6).map(s => (
    <div className="card" key={s.chunk_id}>
      <strong>{s.section || 'Section'} - page {s.page_start ?? '?'}</strong>
      <small>{s.chunk_id} - score {typeof s.score === 'number' ? s.score.toFixed(3) : 'n/a'}</small>
      <p>{truncate(s.text, SOURCE_PREVIEW_CHARS)}</p>
    </div>
  ))}</div>;
}

function FactList({ facts }) {
  if (!facts.length) return <p className="muted">No graph facts yet.</p>;
  return <div className="list">{facts.slice(0, 8).map((f, i) => (
    <div className="card" key={i}>
      <strong>{f.source} -&gt; {f.target}</strong>
      <small>{f.relation} - page {f.page ?? '?'}</small>
      <p>{truncate(f.evidence, FACT_PREVIEW_CHARS)}</p>
    </div>
  ))}</div>;
}

function GraphSummary({ graph }) {
  const nodeTypes = useMemo(() => {
    const counts = {};
    for (const n of graph.nodes || []) counts[n.type || 'GraphNode'] = (counts[n.type || 'GraphNode'] || 0) + 1;
    return Object.entries(counts).sort((a, b) => b[1] - a[1]);
  }, [graph]);
  return <div>
    <p className="muted">{graph.nodes?.length || 0} nodes - {graph.edges?.length || 0} edges</p>
    <div className="chips">{nodeTypes.map(([type, count]) => <span key={type}>{type}: {count}</span>)}</div>
    <div className="miniGraph">
      {(graph.edges || []).slice(0, MINI_GRAPH_EDGE_LIMIT).map((e, i) => {
        const s = graph.nodes.find(n => n.id === e.source)?.name || e.source;
        const t = graph.nodes.find(n => n.id === e.target)?.name || e.target;
        return <div key={i} className="edge"><b>{truncate(s, 32)}</b><em>{e.relation}</em><b>{truncate(t, 32)}</b></div>;
      })}
    </div>
  </div>;
}

function ExampleQuestions({ setQuestion }) {
  return <div className="examples">
    <h3>Example questions</h3>
    {EXAMPLE_QUESTIONS.map(q => <button key={q} onClick={() => setQuestion(q)}>{q}</button>)}
  </div>;
}

async function parseResponse(res) {
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || res.statusText);
  return data;
}

function truncate(text = '', n = 120) {
  return text && text.length > n ? `${text.slice(0, n)}...` : text;
}

function intEnv(value, fallback) {
  const parsed = Number.parseInt(value, 10);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : fallback;
}

function listEnv(value, fallback) {
  if (!value) return fallback;
  return value.split('||').map(item => item.trim()).filter(Boolean);
}

createRoot(document.getElementById('root')).render(<App />);
