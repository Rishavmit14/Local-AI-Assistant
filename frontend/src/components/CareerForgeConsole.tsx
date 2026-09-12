import { useCallback, useEffect, useMemo, useState } from "react";

import { FridayRuntimeClient } from "../runtime";
import type { CareerForgeJourney } from "../runtime";

const projects = [
  "FraudShield",
  "Neural Systems Lab",
  "Local Knowledge Assistant",
  "Production AI Platform",
];

function displayMastery(mastery: string): string {
  return mastery.replaceAll("_", " ").toUpperCase();
}

export function CareerForgeConsole() {
  const client = useMemo(() => new FridayRuntimeClient(), []);
  const [journey, setJourney] = useState<CareerForgeJourney | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [starting, setStarting] = useState(false);
  const [linking, setLinking] = useState(false);

  const refresh = useCallback(async (signal?: AbortSignal) => {
    try {
      setJourney(await client.getCareerJourney(signal));
      setError(null);
    } catch (reason) {
      if (!signal?.aborted) {
        setError(reason instanceof Error ? reason.message : "Career Forge is unavailable");
      }
    }
  }, [client]);

  useEffect(() => {
    const controller = new AbortController();
    const timer = window.setTimeout(() => void refresh(controller.signal), 0);
    return () => {
      window.clearTimeout(timer);
      controller.abort();
    };
  }, [refresh]);

  const startMission = async () => {
    setStarting(true);
    try {
      await client.startCareerMission();
      await refresh();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not start the mission");
    } finally {
      setStarting(false);
    }
  };

  const verified = journey?.competencies.filter(
    (item) => item.mastery !== "unverified",
  ).length ?? 0;
  const activeProject = journey?.current_mission
    ? journey.competencies.find(
      (item) => item.competency.competency_id === journey.current_mission?.competency_id,
    )?.competency.project_family
    : null;
  const activeMissionLinked = journey?.current_mission
    ? journey.project_links.some((item) => item.mission_id === journey.current_mission?.mission_id)
    : false;

  const linkProject = async () => {
    if (!journey?.current_mission) return;
    setLinking(true);
    try {
      await client.linkCareerMissionProject(journey.current_mission.mission_id);
      await refresh();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not connect this mission");
    } finally {
      setLinking(false);
    }
  };

  return (
    <aside className="career-forge-console" aria-label="Career Forge">
      <div className="career-forge-heading">
        <span>CAREER FORGE</span>
        <small>ML / AI ENGINEER</small>
      </div>

      <section className="career-forge-section" aria-label="Learn">
        <h2>LEARN</h2>
        {journey?.current_mission ? (
          <>
            <strong>{journey.current_mission.title}</strong>
            <p>Resume point is preserved in your local Learner Twin.</p>
            {activeProject && !activeMissionLinked ? <button type="button" onClick={() => void linkProject()} disabled={linking}>
              {linking ? "LINKING" : `CONNECT ${activeProject.toUpperCase()}`}
            </button> : null}
          </>
        ) : journey?.recommended_mission ? (
          <>
            <strong>{journey.recommended_mission.title}</strong>
            <p>{journey.recommended_mission.why_it_matters}</p>
            <button type="button" onClick={() => void startMission()} disabled={starting}>
              {starting ? "STARTING" : "BEGIN MISSION"}
            </button>
          </>
        ) : <p>Loading your dependency-aware mission…</p>}
      </section>

      <section className="career-forge-section" aria-label="Map">
        <h2>MAP</h2>
        <p>{journey?.competencies.length ?? "—"} competencies · evidence-backed only</p>
        <div className="career-forge-map">
          {journey?.competencies.slice(0, 5).map((item) => (
            <span key={item.competency.competency_id} title={item.competency.title}>
              {item.competency.title}: {displayMastery(item.mastery)}
            </span>
          ))}
        </div>
      </section>

      <section className="career-forge-section" aria-label="Projects">
        <h2>PROJECTS</h2>
        <div className="career-forge-projects">
          {projects.map((project) => <span key={project}>{project} · {journey?.project_links.filter((item) => item.project_name === project).length ?? 0} linked</span>)}
        </div>
      </section>

      <section className="career-forge-section" aria-label="Progress">
        <h2>PROGRESS</h2>
        <p>{verified} verified · {journey?.progress.evidence.length ?? 0} evidence records · no percentage is inferred.</p>
        {journey?.progress.unresolved_retries.length ? <p>Retry remains: {journey.progress.unresolved_retries[0].question_id}</p> : null}
        {journey?.progress.assistance.length ? <p>Latest help: {displayMastery(journey.progress.assistance[0].level)}</p> : null}
        {journey?.progress.history.length ? <p>Latest: {journey.progress.history[0].summary}</p> : null}
        <p>Next: {journey?.progress.next_action ?? "Loading recorded learning state…"}</p>
        <p>Independence, retention, and public evidence await recorded proof.</p>
      </section>

      {error ? <p className="career-forge-error">{error}</p> : null}
    </aside>
  );
}
