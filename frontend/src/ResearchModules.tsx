import { useEffect, useMemo, useState } from "react";
import {
  ArrowRight, Check, Download, FileSearch, FileText,
  LoaderCircle, Play, RefreshCw, ShieldCheck, Sparkles, AlertCircle
} from "lucide-react";

const API_URL = (import.meta.env.VITE_API_URL || "http://localhost:8000").replace(/\/$/, "");

type Props = {
  question: string;
  setQuestion: (value: string) => void;
  workflow: any;
  onWorkflowUpdate: (updates: Record<string, any>) => void;
  onRunAll: () => void;
  runAllLoading: boolean;
  onReset: () => void;
};

type Module = {
  key: string;
  label: string;
  description: string;
  endpoint: string;
  needs: string[];
  outputKey: string;
};

const MODULES: Module[] = [
  { key: "plan", label: "Research planning", description: "Turn your question into research objectives, tasks, and search terms.", endpoint: "/research/plan", needs: [], outputKey: "research_plan" },
  { key: "discover", label: "Literature discovery", description: "Search OpenAlex and arXiv for relevant scientific papers.", endpoint: "/research/discover", needs: ["plan"], outputKey: "discovery" },
  { key: "filter", label: "Paper filtering", description: "Assess paper relevance and select papers for full-text review.", endpoint: "/research/filter", needs: ["plan", "discover"], outputKey: "filtering" },
  { key: "pdf", label: "PDF extraction", description: "Download accessible PDFs and extract their text.", endpoint: "/research/process-pdfs", needs: ["filter"], outputKey: "pdf_processing" },
  { key: "evidence", label: "Evidence extraction", description: "Extract methods, datasets, results, limitations, and page evidence.", endpoint: "/research/extract-evidence", needs: ["pdf"], outputKey: "evidence_extraction" },
  { key: "synthesis", label: "Cross-paper synthesis", description: "Compare findings and identify agreements, contradictions, and research gaps.", endpoint: "/research/synthesize", needs: ["evidence"], outputKey: "synthesis" },
  { key: "report", label: "Research report", description: "Generate a structured report from the extracted evidence.", endpoint: "/research/generate-report", needs: ["plan", "evidence", "synthesis"], outputKey: "report" },
  { key: "quality", label: "Quality & citation check", description: "Review report support and verify citations against extracted source text.", endpoint: "/research/evaluate-report", needs: ["report", "evidence"], outputKey: "quality_evaluation" },
];

const STAGE_NAMES: Record<string, string> = {
  plan: "Research Planning",
  discover: "Paper Discovery",
  filter: "Relevance Filtering",
  pdf: "PDF Collection and Extraction",
  evidence: "Scientific Evidence Extraction",
  synthesis: "Cross-Paper Synthesis",
  report: "Research Report Generation",
  quality: "Citation and Quality Evaluation",
};

export default function ResearchModules({ question, setQuestion, workflow, onWorkflowUpdate, onRunAll, runAllLoading, onReset }: Props) {
  const [outputs, setOutputs] = useState<Record<string, any>>({});
  const [statuses, setStatuses] = useState<Record<string, { status: string; message: string }>>({});
  const [running, setRunning] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    if (!workflow) return;
    const restored: Record<string, any> = {};
    if (workflow.research_plan) restored.plan = workflow.research_plan;
    if (workflow.discovery) restored.discover = workflow.discovery;
    if (workflow.filtering) restored.filter = workflow.filtering;
    if (workflow.pdf_processing) restored.pdf = workflow.pdf_processing;
    if (workflow.evidence_extraction) restored.evidence = workflow.evidence_extraction;
    if (workflow.synthesis) restored.synthesis = workflow.synthesis;
    if (workflow.report) restored.report = workflow.report;
    if (workflow.quality_evaluation) restored.quality = workflow.quality_evaluation;
    const relevant = (workflow.filtering?.results || []).flatMap((group: any) => group.papers || []).filter((item: any) => item.relevant && item.paper).map((item: any) => item.paper);
    const extractedIds = new Set((workflow.pdf_processing?.results || []).filter((item: any) => item.extraction_status === "success").map((item: any) => item.paper_id));
    if (workflow.pdf_processing) restored.extractedPapers = relevant.filter((paper: any) => extractedIds.has(paper.paper_id));
    if (workflow.evidence_extraction) restored.usableEvidence = (workflow.evidence_extraction.results || []).filter((item: any) => ["success", "partial"].includes(item.extraction_status) && item.evidence?.length);
    setOutputs((current) => ({ ...current, ...restored }));
    if (Array.isArray(workflow.stages)) {
      const next: Record<string, { status: string; message: string }> = {};
      for (const stage of workflow.stages) {
        const key = Object.keys(STAGE_NAMES).find((item) => STAGE_NAMES[item] === stage.name);
        if (key) next[key] = { status: stage.status, message: stage.message };
      }
      setStatuses((current) => ({ ...current, ...next }));
    }
  }, [workflow]);

  const filteredPapers = useMemo(() => {
    const groups = outputs.filter?.results || [];
    const unique = new Map<string, any>();
    for (const group of groups) {
      for (const item of group.papers || []) {
        if (item.relevant && item.paper?.paper_id) unique.set(item.paper.paper_id, item.paper);
      }
    }
    return Array.from(unique.values());
  }, [outputs.filter]);

  function updateStage(key: string, status: string, message: string, data?: Record<string, any>) {
    setStatuses((current) => ({ ...current, [key]: { status, message } }));
    const oldStages = Array.isArray(workflow?.stages) ? workflow.stages.filter((stage: any) => stage.name !== STAGE_NAMES[key]) : [];
    onWorkflowUpdate({
      ...data,
      stages: [...oldStages, { name: STAGE_NAMES[key], status, message, metrics: {} }],
      research_title: outputs.plan?.research_title || workflow?.research_title || question.slice(0, 120),
    });
  }

  async function post(endpoint: string, body: Record<string, any>) {
    const response = await fetch(`${API_URL}${endpoint}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      const detail = typeof data.detail === "string" ? data.detail : `Request failed (${response.status}). Check the backend terminal for details.`;
      throw new Error(detail);
    }
    return data;
  }

  async function runModule(key: string) {
    if (running) return;
    setError("");
    setRunning(key);
    setStatuses((current) => ({ ...current, [key]: { status: "running", message: "Working… this may take a little while." } }));
    try {
      let data: any;
      let workflowData: Record<string, any> = {};

      if (key === "plan") {
        if (question.trim().length < 15) throw new Error("Enter a research question with at least 15 characters.");
        data = await post("/research/plan", { question: question.trim() });
        setOutputs((current) => ({ ...current, plan: data.plan }));
        workflowData = { research_plan: data.plan, research_title: data.plan.research_title, status: "in_progress" };
      } else if (key === "discover") {
        data = await post("/research/discover", outputs.plan);
        setOutputs((current) => ({ ...current, discover: data }));
        workflowData = { discovery: data };
      } else if (key === "filter") {
        data = await post("/research/filter", { tasks: outputs.plan.tasks, results: outputs.discover.results });
        setOutputs((current) => ({ ...current, filter: data }));
        workflowData = { filtering: data };
      } else if (key === "pdf") {
        if (filteredPapers.length < 1) throw new Error("No relevant papers are available. Run paper filtering first.");
        data = await post("/research/process-pdfs", { papers: filteredPapers });
        const extractedIds = new Set((data.results || []).filter((item: any) => item.extraction_status === "success").map((item: any) => item.paper_id));
        const extractedPapers = filteredPapers.filter((paper: any) => extractedIds.has(paper.paper_id));
        setOutputs((current) => ({ ...current, pdf: data, extractedPapers }));
        workflowData = { pdf_processing: data };
      } else if (key === "evidence") {
        if (!outputs.extractedPapers?.length) throw new Error("No PDFs were successfully extracted. Check PDF extraction results.");
        data = await post("/research/extract-evidence", { papers: outputs.extractedPapers });
        const usable = (data.results || []).filter((item: any) => ["success", "partial"].includes(item.extraction_status) && item.evidence?.length);
        setOutputs((current) => ({ ...current, evidence: data, usableEvidence: usable }));
        workflowData = { evidence_extraction: data };
      } else if (key === "synthesis") {
        if ((outputs.usableEvidence || []).length < 2) throw new Error("Synthesis requires usable evidence from at least two papers.");
        data = await post("/research/synthesize", { evidence_reports: outputs.usableEvidence });
        setOutputs((current) => ({ ...current, synthesis: data }));
        workflowData = { synthesis: data };
      } else if (key === "report") {
        if (!outputs.usableEvidence?.length || !outputs.synthesis) throw new Error("Extract evidence and run cross-paper synthesis first.");
        data = await post("/research/generate-report", { research_plan: outputs.plan, evidence_reports: outputs.usableEvidence, synthesis: outputs.synthesis });
        setOutputs((current) => ({ ...current, report: data }));
        workflowData = { report: data };
      } else if (key === "quality") {
        if (!outputs.report || !outputs.usableEvidence?.length) throw new Error("Generate a report and retain its evidence sources first.");
        data = await post("/research/evaluate-report", { report: outputs.report, evidence_reports: outputs.usableEvidence });
        setOutputs((current) => ({ ...current, quality: data }));
        workflowData = { quality_evaluation: data };
      }

      updateStage(key, data?.status === "completed_with_warnings" ? "warning" : "success", data?.message || "Completed successfully.", workflowData);
    } catch (err) {
      const message = err instanceof Error ? err.message : "The module failed unexpectedly.";
      setError(message);
      updateStage(key, "failed", message);
    } finally {
      setRunning("");
    }
  }

  async function exportPDF() {
    if (!outputs.report || !outputs.quality) {
      setError("Generate the report and complete the quality check before exporting.");
      return;
    }
    setRunning("export");
    setError("");
    try {
      const response = await fetch(`${API_URL}/research/export-pdf`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ report: outputs.report, quality_evaluation: outputs.quality }),
      });
      if (!response.ok) {
        const data = await response.json().catch(() => ({}));
        throw new Error(typeof data.detail === "string" ? data.detail : "PDF export failed. Check the backend logs.");
      }
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = `scientific-research-report.pdf`;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      URL.revokeObjectURL(url);
      updateStage("quality", "success", "Quality check completed. PDF report exported.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "PDF export failed.");
    } finally {
      setRunning("");
    }
  }

  const readyCount = MODULES.filter((module) => module.needs.every((need) => Boolean(outputs[need]))).length;
  const paperCount = filteredPapers.length;
  const labels: Record<string, string> = {
    plan: "Research plan", discover: "Discovery results", filter: "Filtering results",
    pdf: "PDF extraction results", evidence: "Evidence reports", synthesis: "Synthesis results",
    report: "Generated report", quality: "Quality evaluation",
  };

  return (
    <section className="modular-workspace">
      <div className="module-brief panel">
        <div className="panel-heading">
          <div><div className="section-kicker">START A NEW INVESTIGATION</div><h2>Research brief</h2></div>
          <span className="panel-icon"><Sparkles size={18}/></span>
        </div>
        <p className="panel-description">Run only the research task you need. Results from completed stages stay available in this workspace, so you can rerun a stage without restarting everything.</p>
        <label htmlFor="research-question">YOUR RESEARCH QUESTION</label>
        <textarea id="research-question" value={question} onChange={(event) => { setQuestion(event.target.value); setOutputs({}); setStatuses({}); setError(""); onReset(); }} placeholder="e.g. How do Vision Transformers compare with convolutional neural networks for medical image classification?" maxLength={500} minLength={15}/>
        <div className="input-meta"><span>Be specific about the domain, method, or outcome.</span><span>{question.length}/500</span></div>
        {error && <div className="error-message"><AlertCircle size={16}/>{error}</div>}
        <div className="module-actions">
          <button className="primary-button" type="button" onClick={onRunAll} disabled={runAllLoading || Boolean(running) || question.trim().length < 15}>
            {runAllLoading ? <><LoaderCircle className="spin" size={17}/> Running all stages</> : <><Play size={15}/> Run all stages <ArrowRight size={16}/></>}
          </button>
          <span className="privacy-note"><ShieldCheck size={14}/> API keys remain on the backend.</span>
        </div>
      </div>

      <div className="module-heading">
        <div><div className="section-kicker">INDIVIDUAL RESEARCH OPERATIONS</div><h2>Run a specific stage</h2><p>Each button calls only its corresponding backend endpoint.</p></div>
        <span className="pipeline-count">{readyCount}/8 <small>AVAILABLE</small></span>
      </div>
      <div className="module-grid">
        {MODULES.map((module, index) => {
          const state = statuses[module.key];
          const ready = module.needs.every((need) => Boolean(outputs[need]));
          const isRunning = running === module.key;
          return (
            <article className={`module-card ${state?.status === "success" ? "module-complete" : state?.status === "failed" ? "module-failed" : ""}`} key={module.key}>
              <div className="module-card-top"><span className="module-number">{String(index + 1).padStart(2, "0")}</span><span className={`module-status ${state?.status || "pending"}`}>{isRunning ? "Running" : state?.status || (ready ? "Ready" : "Locked")}</span></div>
              <h3>{module.label}</h3><p>{module.description}</p>
              {state?.message && <small className="module-message">{state.message}</small>}
              <button className="module-run-button" type="button" onClick={() => runModule(module.key)} disabled={!ready || Boolean(running) || runAllLoading}>
                {isRunning ? <><LoaderCircle className="spin" size={15}/> Running</> : state?.status === "success" ? <><RefreshCw size={14}/> Run again</> : <><Play size={14}/> Run stage</>}
              </button>
              {!ready && <small className="module-hint">Complete the previous required stage(s) first.</small>}
              {state?.status === "success" && outputs[module.key] && <small className="module-result-label"><Check size={12}/> {labels[module.key]} saved in this session</small>}
            </article>
          );
        })}
      </div>

      <div className="module-footer panel">
        <div className="module-footer-icon"><FileText size={19}/></div>
        <div><b>Export the research report</b><p>Available after report generation and quality evaluation.</p></div>
        <button className="download-button" type="button" onClick={exportPDF} disabled={!outputs.report || !outputs.quality || Boolean(running) || runAllLoading}>
          {running === "export" ? <LoaderCircle className="spin" size={15}/> : <Download size={15}/>} Export PDF
        </button>
      </div>
      <div className="module-note"><FileSearch size={14}/> PDF access depends on the publisher. Papers blocked by a 403 response will be reported as unavailable rather than treated as analysed.</div>
    </section>
  );
}
