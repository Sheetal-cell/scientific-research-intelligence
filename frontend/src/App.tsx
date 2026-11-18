import { useEffect, useMemo, useState } from "react";
import {
  Activity, ArrowDownToLine, ArrowRight, BookOpen, BrainCircuit, Check,
  ChevronDown, CircleHelp, Clock3, Command, FileText, FlaskConical,
  LayoutDashboard, Library, LoaderCircle, Menu, Microscope, Network,
  Search, Settings2, ShieldCheck, Sparkles, X, AlertCircle, ExternalLink,
} from "lucide-react";

const API_URL = (import.meta.env.VITE_API_URL || "http://localhost:8000").replace(/\/$/, "");

type Stage = { name: string; status: string; message: string; metrics?: Record<string, unknown> };
type Paper = { paper_id?: string; title?: string; authors?: string[]; publication_year?: number | null; doi?: string | null; paper_url?: string | null; source?: string; abstract?: string | null };
type Workflow = {
  status: string; research_title: string; stages: Stage[];
  research_plan?: { research_question?: string; research_scope?: string; tasks?: { title: string; description: string; search_keywords?: string[] }[] };
  filtering?: { total_papers_evaluated?: number; total_relevant?: number; results?: { papers?: { paper: Paper; relevant: boolean; relevance_score?: number; reason?: string }[] }[] };
  pdf_processing?: { successful_downloads?: number; successful_extractions?: number; results?: { paper_id: string; extraction_status: string }[] };
  evidence_extraction?: { successfully_analyzed?: number; partially_analyzed?: number; failed?: number; results?: { paper?: Paper; paper_id?: string; extraction_status?: string; evidence?: { claim?: string; evidence?: string; page_number?: number; evidence_type?: string }[] }[] };
  synthesis?: { total_insights?: number; total_papers_used?: number; total_evidence_items?: number; insights?: { title?: string; description?: string; supporting_papers?: string[] }[] };
  report?: { executive_summary?: string; sections?: { title?: string; content?: string }[]; citations?: { citation_id?: string; paper_title?: string; doi?: string; url?: string }[]; conclusion?: string; warnings?: string[]; total_papers_used?: number; total_citations?: number };
  quality_evaluation?: { overall_score?: number; citation_integrity_score?: number; total_citations_checked?: number; verified_citations?: number; invalid_citations?: number; warnings?: string[] };
  pdf_filename?: string;
};

const navItems = [
  { label: "Overview", icon: LayoutDashboard },
  { label: "Research workspace", icon: Microscope },
  { label: "Paper library", icon: Library },
  { label: "Research analytics", icon: Activity },
];

function Metric({ label, value, note, icon: Icon }: { label: string; value: string | number; note: string; icon: typeof BookOpen }) {
  return <div className="metric-card"><div className="metric-top"><span>{label}</span><span className="metric-icon"><Icon size={17}/></span></div><strong>{value}</strong><small>{note}</small></div>;
}

function App() {
  const [activeNav, setActiveNav] = useState("Overview");
  const [question, setQuestion] = useState("");
  const [workflow, setWorkflow] = useState<Workflow | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [apiHealthy, setApiHealthy] = useState<boolean | null>(null);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [expanded, setExpanded] = useState<number | null>(0);

  useEffect(() => {
    let active = true;
    fetch(`${API_URL}/health`).then((r) => r.ok).then((ok) => { if (active) setApiHealthy(ok); }).catch(() => { if (active) setApiHealthy(false); });
    return () => { active = false; };
  }, []);

  const papers = useMemo(() => {
    const fromFilter = workflow?.filtering?.results?.flatMap((group) => group.papers || []).filter((item) => item.relevant).map((item) => item.paper) || [];
    if (fromFilter.length) return fromFilter;
    return workflow?.evidence_extraction?.results?.map((item) => item.paper).filter((paper): paper is Paper => Boolean(paper)) || [];
  }, [workflow]);

  const visiblePapers = papers.filter((paper) => `${paper.title || ""} ${paper.authors?.join(" ") || ""}`.toLowerCase().includes(query.toLowerCase()));

  async function runResearch(event: React.FormEvent) {
    event.preventDefault();
    if (question.trim().length < 15) {
      setError("Please enter a research question with at least 15 characters.");
      return;
    }
    setLoading(true);
    setError("");
    setWorkflow(null);
    setActiveNav("Research workspace");
    try {
      const response = await fetch(`${API_URL}/research/run`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: question.trim() }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(typeof data.detail === "string" ? data.detail : "The research workflow could not be completed. Check the API logs and try again.");
      setWorkflow(data as Workflow);
      setExpanded(0);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unexpected error. Please try again.");
    } finally {
      setLoading(false);
    }
  }

  function downloadReport() {
    if (workflow?.pdf_filename) window.open(`${API_URL}/research/download/${encodeURIComponent(workflow.pdf_filename)}`, "_blank", "noopener,noreferrer");
  }

  const completedStages = workflow?.stages.filter((stage) => stage.status === "success").length || 0;

  return (
    <div className="app-shell">
      <aside className={`sidebar ${mobileOpen ? "sidebar-open" : ""}`}>
        <div className="brand"><div className="brand-mark"><FlaskConical size={21}/></div><div><b>SCI<span>INTEL</span></b><small>RESEARCH STUDIO</small></div><button className="mobile-close" onClick={() => setMobileOpen(false)} aria-label="Close menu"><X size={18}/></button></div>
        <div className="workspace-switch"><div className="workspace-avatar">SR</div><div><b>Research workspace</b><small>Personal environment</small></div><ChevronDown size={15}/></div>
        <div className="nav-label">WORKSPACE</div>
        <nav>{navItems.map(({ label, icon: Icon }) => <button key={label} className={activeNav === label ? "nav-item active" : "nav-item"} onClick={() => { setActiveNav(label); setMobileOpen(false); }}><Icon size={18}/><span>{label}</span>{label === "Research workspace" && workflow && <i className="nav-dot"/>}</button>)}</nav>
        <div className="sidebar-bottom"><div className="help-card"><div className="help-icon"><CircleHelp size={17}/></div><b>Need a hand?</b><p>Explore how the research pipeline works and what each stage produces.</p><a href="https://github.com/Sheetal-cell/scientific-research-intelligence" target="_blank" rel="noreferrer">Project documentation <ArrowRight size={13}/></a></div><div className="profile"><div className="profile-avatar">SB</div><div><b>Researcher</b><small>Independent workspace</small></div><Settings2 size={17}/></div></div>
      </aside>

      <main className="main-area">
        <header className="topbar"><button className="mobile-menu" onClick={() => setMobileOpen(true)} aria-label="Open menu"><Menu/></button><div className="breadcrumb">Workspace <span>/</span> <b>{activeNav}</b></div><div className="top-actions"><div className={`api-status ${apiHealthy ? "online" : apiHealthy === false ? "offline" : ""}`}><span/>{apiHealthy === null ? "Connecting" : apiHealthy ? "API connected" : "API unavailable"}</div><button className="icon-button" title="Project repository" onClick={() => window.open("https://github.com/Sheetal-cell/scientific-research-intelligence", "_blank", "noopener,noreferrer")}><Command size={17}/></button><div className="top-avatar">SB</div></div></header>

        <div className="page-content">
          <section className="welcome-row"><div><div className="eyebrow"><span className="eyebrow-line"/> AI-POWERED RESEARCH ENVIRONMENT</div><h1>Turn research questions<br/><em>into scientific insight.</em></h1><p className="welcome-copy">Discover literature, extract verifiable evidence, and build structured research reports — all in one workspace.</p></div><div className="welcome-art"><div className="orbit orbit-one"/><div className="orbit orbit-two"/><div className="art-core"><BrainCircuit size={37}/></div><span className="art-node node-a"><BookOpen size={15}/></span><span className="art-node node-b"><Network size={15}/></span><span className="art-node node-c"><ShieldCheck size={15}/></span></div></section>

          <section className="metrics-grid">
            <Metric label="Papers discovered" value={workflow?.filtering?.total_papers_evaluated ?? "—"} note="Evaluated in latest run" icon={BookOpen}/>
            <Metric label="Relevant papers" value={workflow?.filtering?.total_relevant ?? papers.length || "—"} note="Selected for evidence review" icon={Library}/>
            <Metric label="Research insights" value={workflow?.synthesis?.total_insights ?? "—"} note="Cross-paper synthesis" icon={Network}/>
            <Metric label="Citation integrity" value={workflow?.quality_evaluation?.citation_integrity_score != null ? `${workflow.quality_evaluation.citation_integrity_score}%` : "—"} note="Verified citation score" icon={ShieldCheck}/>
          </section>

          <section className="work-grid">
            <div className="panel research-panel"><div className="panel-heading"><div><div className="section-kicker">START A NEW INVESTIGATION</div><h2>Research brief</h2></div><span className="panel-icon"><Sparkles size={18}/></span></div><p className="panel-description">Describe the scientific problem you want to explore. The multi-agent workflow will plan the investigation and build an evidence-backed report.</p><form onSubmit={runResearch}><label htmlFor="research-question">YOUR RESEARCH QUESTION</label><textarea id="research-question" value={question} onChange={(e) => setQuestion(e.target.value)} placeholder="e.g. How do Vision Transformers compare with convolutional neural networks for medical image classification, and what are their current limitations?" maxLength={500} minLength={15}/><div className="input-meta"><span>Be specific about the domain, method, or outcome.</span><span>{question.length}/500</span></div>{error && <div className="error-message"><AlertCircle size={16}/>{error}</div>}<button className="primary-button" type="submit" disabled={loading || apiHealthy === false}>{loading ? <><LoaderCircle className="spin" size={17}/> Running research pipeline</> : <>Launch research workflow <ArrowRight size={16}/></>}</button><div className="privacy-note"><ShieldCheck size={14}/> Your API key stays on the backend. Never add secrets to the browser.</div></form></div>
            <div className="panel pipeline-panel"><div className="panel-heading"><div><div className="section-kicker">AUTOMATED WORKFLOW</div><h2>Research pipeline</h2></div><span className="pipeline-count">{workflow ? `${completedStages}/${workflow.stages.length}` : "09"} <small>STAGES</small></span></div><div className="pipeline-list">{["Research planning","Paper discovery","Relevance filtering","PDF collection & extraction","Scientific evidence extraction","Cross-paper synthesis","Report generation","Citation & quality review","PDF report export"].map((label, i) => { const stage = workflow?.stages[i]; return <div className={`pipeline-step ${stage?.status === "success" ? "step-done" : stage?.status === "failed" ? "step-failed" : ""}`} key={label}><div className="step-marker">{stage?.status === "success" ? <Check size={13}/> : <span>{String(i + 1).padStart(2, "0")}</span>}</div><div className="step-copy"><b>{label}</b>{stage && <small>{stage.message}</small>}</div>{stage && <span className={`step-state ${stage.status}`}>{stage.status === "success" ? "Done" : stage.status}</span>}</div>; })}</div><div className="pipeline-foot"><span><i className="legend-dot done"/> Completed</span><span><i className="legend-dot pending"/> Awaiting run</span></div></div>
          </section>

          {workflow && <section className="results-section"><div className="results-header"><div><div className="section-kicker">LATEST INVESTIGATION</div><h2>{workflow.research_title || "Research results"}</h2><p>{workflow.status === "success" ? "Your research report is ready." : "The workflow completed with some limitations. Review the stage details below."}</p></div><button className="download-button" onClick={downloadReport} disabled={!workflow.pdf_filename}><ArrowDownToLine size={16}/> Download report</button></div>
            <div className="result-tabs"><span className="tab-active"><FileText size={15}/> Report</span><span><Library size={15}/> Papers ({papers.length})</span><span><Activity size={15}/> Quality review</span></div>
            <div className="result-layout"><div className="panel report-panel"><div className="report-label"><FileText size={16}/> EXECUTIVE SUMMARY</div><p className="summary-text">{workflow.report?.executive_summary || "The report summary was not returned. Review the workflow status and backend logs."}</p>{workflow.report?.sections?.map((section, i) => <div className="report-section" key={i}><h3>{section.title || `Section ${i + 1}`}</h3><p>{section.content}</p></div>)}{workflow.report?.conclusion && <div className="report-section"><h3>Conclusion</h3><p>{workflow.report.conclusion}</p></div>}</div>
              <div className="panel quality-panel"><div className="panel-heading"><div><div className="section-kicker">TRUST & TRACEABILITY</div><h3>Quality review</h3></div><ShieldCheck size={20} className="green-icon"/></div><div className="score-ring" style={{ "--score": `${workflow.quality_evaluation?.overall_score || 0}%` } as React.CSSProperties}><div><b>{workflow.quality_evaluation?.overall_score ?? "—"}</b><small>OVERALL</small></div></div><div className="quality-stats"><div><span>Citation integrity</span><b>{workflow.quality_evaluation?.citation_integrity_score ?? "—"}{workflow.quality_evaluation?.citation_integrity_score != null ? "%" : ""}</b></div><div><span>Verified citations</span><b>{workflow.quality_evaluation?.verified_citations ?? "—"}</b></div><div><span>Invalid citations</span><b>{workflow.quality_evaluation?.invalid_citations ?? "—"}</b></div></div>{(workflow.quality_evaluation?.warnings || workflow.report?.warnings || []).map((warning, i) => <div className="warning" key={i}><AlertCircle size={14}/>{warning}</div>)}</div></div>
          </section>}

          <section className="library-section"><div className="library-heading"><div><div className="section-kicker">LITERATURE REVIEW</div><h2>Selected research papers</h2><p>Sources retained by the relevance and evidence pipeline.</p></div><div className="search-box"><Search size={16}/><input placeholder="Search papers" value={query} onChange={(e) => setQuery(e.target.value)}/></div></div>{visiblePapers.length ? <div className="paper-list">{visiblePapers.map((paper, i) => <article className="paper-card" key={paper.paper_id || i}><div className="paper-icon"><BookOpen size={18}/></div><div className="paper-info"><h3>{paper.title || "Untitled paper"}</h3><p>{paper.authors?.slice(0, 4).join(", ") || "Authors not available"}{paper.publication_year ? ` · ${paper.publication_year}` : ""}</p><div className="paper-tags"><span>{paper.source || "Research source"}</span>{paper.doi && <span>DOI indexed</span>}</div></div>{paper.paper_url && <a className="paper-link" href={paper.paper_url} target="_blank" rel="noreferrer" aria-label="Open paper"><ExternalLink size={17}/></a>}</article>)}</div> : <div className="empty-library"><div className="empty-icon"><Library size={22}/></div><b>No papers to display yet</b><p>Run a research investigation to populate this literature library with discovered and assessed papers.</p></div>}</section>
          <footer className="footer"><span>SCIINTEL · Scientific Research Intelligence</span><span>Built for reproducible, evidence-aware exploration</span></footer>
        </div>
      </main>
      {mobileOpen && <button className="mobile-scrim" onClick={() => setMobileOpen(false)} aria-label="Close navigation"/>}
    </div>
  );
}

export default App;
