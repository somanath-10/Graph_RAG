import React, { useEffect, useMemo, useState } from 'react';
import { createRoot } from 'react-dom/client';
import './styles.css';

const env = import.meta.env;
const API_BASE = env.VITE_API_URL || `${window.location.protocol}//${window.location.hostname}:8000/api`;
const APP_TITLE = env.VITE_APP_TITLE || 'Patent Accuracy RAG';
const APP_SUBTITLE = env.VITE_APP_SUBTITLE || 'Evidence GraphRAG vs SproutRAG on the same patent evidence';
const DEFAULT_QUESTION = env.VITE_DEFAULT_QUESTION || 'Which examples support claim 1?';
const QUERY_TOP_K = intEnv(env.VITE_QUERY_TOP_K, 12);
const GRAPH_LIMIT = intEnv(env.VITE_GRAPH_LIMIT, 120);
const SOURCE_PREVIEW_CHARS = intEnv(env.VITE_SOURCE_PREVIEW_CHARS, 300);
const FACT_PREVIEW_CHARS = intEnv(env.VITE_FACT_PREVIEW_CHARS, 220);
const MINI_GRAPH_EDGE_LIMIT = intEnv(env.VITE_MINIGRAPH_EDGE_LIMIT, 12);
const API_KEY = env.VITE_API_KEY || '';
const API_KEY_HEADER = env.VITE_API_KEY_HEADER || 'X-API-Key';
const EXAMPLE_QUESTIONS = listEnv(env.VITE_EXAMPLE_QUESTIONS, [
  'What does claim 1 describe?',
  'Which examples support claim 1?',
  'Summarize the invention step by step.',
  'What measurements, ranges, or conditions are disclosed?',
  'What problem does the invention solve?'
]);

function App() {
  const [health, setHealth] = useState(null);
  const [status, setStatus] = useState('Ready');
  const [file, setFile] = useState(null);
  const [document, setDocument] = useState(null);
  const [question, setQuestion] = useState(DEFAULT_QUESTION);
  const [loading, setLoading] = useState(false);
  const [graphResult, setGraphResult] = useState(null);
  const [sproutResult, setSproutResult] = useState(null);
  const [comparison, setComparison] = useState(null);
  const [graph, setGraph] = useState({ nodes: [], edges: [] });

  useEffect(() => {
    fetch(`${API_BASE}/health`).then(r => r.json()).then(setHealth).catch(() => setHealth({ status: 'offline' }));
  }, []);

  async function ingestSample() {
    setLoading(true);
    setStatus('Indexing included patent with shared SourceUnits, GraphRAG, and SproutRAG...');
    try {
      const data = await request(`${API_BASE}/documents/ingest-sample`, { method: 'POST', headers: authHeaders() });
      setDocument({ document_id: data.document_id, filename: data.filename || 'sample patent' });
      setStatus(indexStatus(data));
      await loadGraph(data.document_id);
    } catch (e) {
      setStatus(`Sample indexing failed: ${e.message}`);
    } finally {
      setLoading(false);
    }
  }

  async function uploadPdf() {
    if (!file) return setStatus('Choose a PDF first.');
    setLoading(true);
    setStatus('Uploading patent PDF...');
    try {
      const form = new FormData();
      form.append('file', file);
      const data = await request(`${API_BASE}/documents/upload`, { method: 'POST', headers: authHeaders(), body: form });
      setDocument(data);
      setGraphResult(null);
      setSproutResult(null);
      setComparison(null);
      setStatus(`Uploaded ${data.filename}. Build indexes next.`);
    } catch (e) {
      setStatus(`Upload failed: ${e.message}`);
    } finally {
      setLoading(false);
    }
  }

  async function buildIndexes(mode = 'both') {
    if (!document?.document_id) return setStatus('Upload or ingest a patent first.');
    setLoading(true);
    setStatus(`Building ${mode} indexes for ${document.filename || document.document_id}...`);
    try {
      const data = await request(`${API_BASE}/documents/${document.document_id}/index`, {
        method: 'POST',
        headers: jsonHeaders(),
        body: JSON.stringify({ mode })
      });
      setStatus(indexStatus(data));
      await loadGraph(document.document_id);
    } catch (e) {
      setStatus(`Indexing failed: ${e.message}`);
    } finally {
      setLoading(false);
    }
  }

  async function ask(method) {
    const q = question.trim();
    if (!q) return;
    if (!document?.document_id) return setStatus('Upload or ingest a patent before asking.');
    setLoading(true);
    setStatus(`Running ${method === 'graph' ? 'GraphRAG' : 'SproutRAG'} retrieval...`);
    try {
      const data = await request(`${API_BASE}/query`, {
        method: 'POST',
        headers: jsonHeaders(),
        body: JSON.stringify({ question: q, top_k: QUERY_TOP_K, document_id: document.document_id, method })
      });
      if (method === 'graph') setGraphResult(data);
      else setSproutResult(data);
      setComparison(null);
      setStatus(`${method === 'graph' ? 'GraphRAG' : 'SproutRAG'} answer generated.`);
    } catch (e) {
      setStatus(`Query failed: ${e.message}`);
    } finally {
      setLoading(false);
    }
  }

  async function compareBoth() {
    const q = question.trim();
    if (!q) return;
    if (!document?.document_id) return setStatus('Upload or ingest a patent before comparing.');
    setLoading(true);
    setStatus('Comparing GraphRAG and SproutRAG...');
    try {
      const data = await request(`${API_BASE}/query/compare`, {
        method: 'POST',
        headers: jsonHeaders(),
        body: JSON.stringify({ question: q, top_k: QUERY_TOP_K, document_id: document.document_id })
      });
      setGraphResult(data.graph_rag);
      setSproutResult(data.sprout_rag);
      setComparison(data);
      setStatus(`Comparison complete. Winner: ${labelWinner(data.winner)}.`);
    } catch (e) {
      setStatus(`Comparison failed: ${e.message}`);
    } finally {
      setLoading(false);
    }
  }

  async function loadGraph(documentId = document?.document_id) {
    try {
      const suffix = documentId ? `&document_id=${encodeURIComponent(documentId)}` : '';
      const data = await request(`${API_BASE}/graph?limit=${GRAPH_LIMIT}${suffix}`, { headers: authHeaders() });
      setGraph(data);
    } catch (e) {
      setStatus(`Could not load graph: ${e.message}`);
    }
  }

  return (
    <div className="page">
      <header className="topbar">
        <div>
          <h1>{APP_TITLE}</h1>
          <p>{APP_SUBTITLE}</p>
        </div>
        <div className={`pill ${health?.status === 'ok' ? 'ok' : 'bad'}`}>API {health?.status || 'checking'}</div>
      </header>

      <main className="workspace">
        <section className="controls panel">
          <div className="sectionHeader">
            <h2>Patent</h2>
            <button disabled={loading} onClick={ingestSample}>Ingest sample</button>
          </div>
          <input type="file" accept="application/pdf" onChange={e => setFile(e.target.files?.[0] || null)} />
          <div className="buttonRow">
            <button disabled={loading || !file} onClick={uploadPdf}>Upload</button>
            <button disabled={loading || !document} onClick={() => buildIndexes('both')}>Build both</button>
          </div>
          <div className="buttonRow subtle">
            <button disabled={loading || !document} onClick={() => buildIndexes('graph')}>Build GraphRAG</button>
            <button disabled={loading || !document} onClick={() => buildIndexes('sprout')}>Build SproutRAG</button>
          </div>
          <DocumentBadge document={document} />
          <div className="status">{status}</div>

          <h2>Question</h2>
          <textarea value={question} onChange={e => setQuestion(e.target.value)} placeholder="Ask about claims, embodiments, examples, figures, ranges, or measured values." />
          <div className="buttonRow">
            <button disabled={loading || !document} onClick={() => ask('graph')}>Ask GraphRAG</button>
            <button disabled={loading || !document} onClick={() => ask('sprout')}>Ask SproutRAG</button>
            <button disabled={loading || !document} onClick={compareBoth}>Compare both</button>
          </div>
          <ExampleQuestions setQuestion={setQuestion} />
        </section>

        <section className="results">
          <ComparisonBanner comparison={comparison} />
          <div className="answerGrid">
            <AnswerPanel title="GraphRAG Answer" result={graphResult} score={comparison?.graph_score} accent="graph" />
            <AnswerPanel title="SproutRAG Answer" result={sproutResult} score={comparison?.sprout_score} accent="sprout" />
          </div>
        </section>

        <aside className="inspector panel">
          <div className="sectionHeader">
            <h2>Graph Snapshot</h2>
            <button disabled={loading} onClick={() => loadGraph()}>Refresh</button>
          </div>
          <GraphSummary graph={graph} />
          <h2>Graph Facts</h2>
          <FactList facts={graphResult?.graph_facts || []} />
          <h2>Sprout Tree Path</h2>
          <TreePath path={sproutResult?.tree_path || []} />
        </aside>
      </main>
    </div>
  );
}

function AnswerPanel({ title, result, score, accent }) {
  return (
    <section className={`panel answerPanel ${accent}`}>
      <div className="sectionHeader">
        <h2>{title}</h2>
        <MetricLine result={result} score={score} />
      </div>
      {!result ? (
        <div className="empty">Run this method or compare both to see an answer.</div>
      ) : (
        <>
          <div className="answerText">{result.answer}</div>
          <SourceList sources={result.sources || []} />
        </>
      )}
    </section>
  );
}

function MetricLine({ result, score }) {
  if (!result) return null;
  return <div className="metrics">
    <span>{Math.round(result.latency_ms || 0)} ms</span>
    <span>{result.sources?.length || 0} sources</span>
    {score && <span>score {score.score}</span>}
  </div>;
}

function ComparisonBanner({ comparison }) {
  if (!comparison) return <div className="comparison muted">Compare both methods to choose a winner based on cited evidence.</div>;
  return (
    <div className="comparison">
      <strong>Winner: {labelWinner(comparison.winner)}</strong>
      <span>{comparison.reason}</span>
    </div>
  );
}

function DocumentBadge({ document }) {
  if (!document) return <p className="muted">No patent selected.</p>;
  return <div className="documentBadge">
    <strong>{document.filename || document.document_id}</strong>
    <small>{document.document_id}</small>
  </div>;
}

function SourceList({ sources }) {
  if (!sources.length) return <p className="muted">No sources yet.</p>;
  return <div className="sourceList">{sources.slice(0, 8).map(s => (
    <article className="sourceItem" key={s.source_id || s.chunk_id}>
      <strong>{s.section || 'Section'} · page {s.page_start ?? '?'}</strong>
      <small>{s.source_id || s.chunk_id} · {s.retrieval_channel || 'retrieval'} · score {typeof s.score === 'number' ? s.score.toFixed(3) : 'n/a'}</small>
      <p>{truncate(s.text, SOURCE_PREVIEW_CHARS)}</p>
    </article>
  ))}</div>;
}

function FactList({ facts }) {
  if (!facts.length) return <p className="muted">No graph facts in the latest GraphRAG answer.</p>;
  return <div className="sourceList">{facts.slice(0, 8).map((f, i) => (
    <article className="sourceItem" key={i}>
      <strong>{f.source} -&gt; {f.target}</strong>
      <small>{f.relation} · page {f.page ?? '?'}</small>
      <p>{truncate(f.evidence, FACT_PREVIEW_CHARS)}</p>
    </article>
  ))}</div>;
}

function TreePath({ path }) {
  if (!path.length) return <p className="muted">No Sprout tree path in the latest SproutRAG answer.</p>;
  return <div className="sourceList">{path.slice(0, 8).map((p, i) => (
    <article className="sourceItem" key={`${p.tree_node_id}-${i}`}>
      <strong>{p.section || 'Section'}</strong>
      <small>{p.source_id} · score {typeof p.score === 'number' ? p.score.toFixed(2) : 'n/a'}</small>
    </article>
  ))}</div>;
}

function GraphSummary({ graph }) {
  const nodeTypes = useMemo(() => {
    const counts = {};
    for (const n of graph.nodes || []) counts[n.type || 'GraphNode'] = (counts[n.type || 'GraphNode'] || 0) + 1;
    return Object.entries(counts).sort((a, b) => b[1] - a[1]);
  }, [graph]);
  return <div>
    <p className="muted">{graph.nodes?.length || 0} nodes · {graph.edges?.length || 0} edges</p>
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
    <h3>Examples</h3>
    {EXAMPLE_QUESTIONS.map(q => <button key={q} onClick={() => setQuestion(q)}>{q}</button>)}
  </div>;
}

async function request(url, options) {
  const res = await fetch(url, options);
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || res.statusText);
  return data;
}

function authHeaders(extra = {}) {
  return API_KEY ? { ...extra, [API_KEY_HEADER]: API_KEY } : extra;
}

function jsonHeaders() {
  return authHeaders({ 'Content-Type': 'application/json' });
}

function indexStatus(data) {
  return `Indexed ${data.document_id}: ${data.source_units} source units, ${data.vector_units} vector units, ${data.graph_entities} graph entities, ${data.graph_relationships} graph facts, ${data.sprout_nodes} Sprout nodes.`;
}

function labelWinner(winner) {
  return winner === 'graph_rag' ? 'GraphRAG' : winner === 'sprout_rag' ? 'SproutRAG' : 'Tie';
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
