import { useNavigate } from "@tanstack/react-router";
import { useCallback, useEffect, useMemo, useState } from "react";
import { EVENTS, Joyride, STATUS, type Step } from "react-joyride";
import { useMedia } from "@/hooks/use-media";
import { storage } from "@/lib/storage";
import { tour } from "./tour-store";
import { TourTooltip } from "./tour-tooltip";

const SEEN = "ts.tourSeen"; // same key as the first viewer, so people who saw that tour aren't shown it again

/** Wait until `selector` is in the page and visible (results and charts load asynchronously). */
function waitFor(selector: string, ms = 6000) {
  return new Promise<void>((resolve) => {
    const t0 = Date.now();
    const tick = () => {
      const el = document.querySelector<HTMLElement>(selector);
      // getClientRects is empty for display:none; works for body and fixed/sticky elements too.
      if ((el && el.getClientRects().length > 0) || Date.now() - t0 > ms) return resolve();
      setTimeout(tick, 100);
    };
    tick();
  });
}

const P = ({ children }: { children: React.ReactNode }) => <p>{children}</p>;

/** First-visit walkthrough of both screens; replay from the "?" button in the top bar. */
export function GuidedTour() {
  const navigate = useNavigate();
  const phone = !useMedia("(min-width: 640px)");
  const [run, setRun] = useState(false);

  // Steps switch screens in their `before` hook; Joyride waits for it.
  const on = useCallback(
    (view: "overview" | "explore", selector: string) => async () => {
      const onExplore = window.location.pathname.endsWith("/explore");
      if (view === "explore" && !onExplore) await navigate({ to: "/explore", search: {} });
      if (view === "overview" && onExplore) await navigate({ to: "/", search: {} });
      await waitFor(selector);
    },
    [navigate],
  );

  const steps = useMemo<Step[]>(() => {
    const s = (
      view: "overview" | "explore",
      selector: string,
      title: string,
      content: React.ReactNode,
      extra: Partial<Step> = {},
    ): Step => ({
      target: selector,
      title,
      content,
      before: on(view, selector),
      ...extra,
    });
    return [
      s(
        "overview",
        "body",
        "Welcome to Talent Seed",
        <>
          <P>Find the most active open-source crypto developers by chain, project and cohort.</P>
          <P>This one-minute tour shows you around. Replay it any time from the ? button.</P>
        </>,
        { placement: "center" },
      ),
      s(
        "overview",
        "[data-tour=cohort-cards]",
        "Priority cohorts",
        <>
          <P>
            P1 is who to look at first: full-time developers with over a year of tenure. HOLD is mostly people not
            active lately.
          </P>
          <P>Click a card to see the people in it.</P>
        </>,
      ),
      s(
        "overview",
        phone ? "[data-tour=chains-head]" : "[data-tour=chains]",
        "Developers per chain",
        <P>Active developers on each chain, with the P1 share in dark blue. Click a bar to explore that chain.</P>,
        { placement: phone ? "bottom" : "right" },
      ),
      s(
        "overview",
        "[data-tour=heatmap]",
        "Tenure × activity",
        <P>
          How experienced and how active people are. Each cell names the cohort it feeds; click one to see those people.
        </P>,
      ),
      s(
        "overview",
        "[data-tour=notes]",
        "Draft data, read the notes",
        <P>
          Cohorts are a draft until the client confirms them, and emails are unverified. The snapshot date and data
          credit live here.
        </P>,
      ),
      s("explore", "[data-tour=cohorts]", "Pick a cohort", <P>Switch between cohorts, or see P1–P3 together.</P>),
      s(
        "explore",
        "[data-tour=search]",
        "Search",
        <P>Search by name, GitHub login, an exact email, or a person id. Press / from anywhere to jump here.</P>,
      ),
      s(
        "explore",
        "[data-tour=filter]",
        "Filter",
        <P>
          Narrow by chain or project (e.g. Uniswap, Anza), activity, tenure, exclusivity or country. Filters stay in the
          URL, so you can bookmark or share a view.
        </P>,
      ),
      s(
        "explore",
        "[data-tour=sort]",
        "Sort",
        <P>
          Results sort by days active in the last 84 days. Commit counts are inflated by forks, so use them with care.
        </P>,
      ),
      s(
        "explore",
        "[data-tour=results] > :first-child",
        "Open a profile",
        <>
          <P>
            Each card shows why the person is in their cohort. Click it for chains, top repos and contact details; ← →
            step through people.
          </P>
          <P>The ★ adds them to your shortlist.</P>
        </>,
      ),
      s(
        "explore",
        "[data-tour=shortlist]",
        "Your shortlist",
        <P>Starred people collect here and are kept in this browser.</P>,
      ),
      s(
        "explore",
        "[data-tour=export]",
        "Export for outreach",
        <P>
          Download the current filter or your shortlist as CSV. The caveats (unverified emails, draft cohorts,
          attribution) travel with every row.
        </P>,
      ),
    ];
  }, [on, phone]);

  const start = useCallback(() => {
    setRun(false);
    requestAnimationFrame(() => setRun(true));
  }, []);

  useEffect(() => tour.onStart(start), [start]);

  // First visit: start once, unless the link opened a specific profile.
  useEffect(() => {
    if (storage.get(SEEN, false) || new URLSearchParams(window.location.search).has("p")) return;
    const t = setTimeout(start, 900);
    return () => clearTimeout(t);
  }, [start]);

  return (
    <Joyride
      run={run}
      steps={steps}
      continuous
      scrollToFirstStep
      tooltipComponent={TourTooltip}
      locale={{
        back: "Back",
        close: "Close",
        last: "Done",
        next: "Next",
        nextWithProgress: "Next",
        skip: "Close the tour",
      }}
      floatingOptions={{ hideArrow: true }}
      options={{
        skipBeacon: true,
        showProgress: true,
        scrollOffset: 80,
        spotlightPadding: 6,
        spotlightRadius: 12,
        overlayColor: "rgba(15, 15, 25, 0.45)",
        overlayClickAction: false,
        zIndex: 60,
      }}
      onEvent={(data) => {
        if (import.meta.env.DEV || localStorage.getItem("ts.tourDebug"))
          console.info("tour", data.type, data.index, data.status, data.lifecycle);
        if (data.type === EVENTS.TOUR_END || data.status === STATUS.FINISHED || data.status === STATUS.SKIPPED) {
          setRun(false);
          storage.set(SEEN, "1");
        }
      }}
    />
  );
}
