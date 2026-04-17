import React, { useMemo, useState } from "react";

/**
 * Pre‑Game Coach — Quick Input Tool (single file)
 * Jono can pick a mode, add a few pre‑game facts, and get an instant plan.
 * No images. All strategy logic is baked in.
 *
 * Tech: Tailwind only. No external data.
 */

// ---------- Mini UI Primitives ----------
const Card: React.FC<{ title?: string; children: React.ReactNode; className?: string }>
  = ({ title, children, className }) => (
  <div className={`rounded-2xl border border-slate-700 bg-slate-900/70 shadow-xl p-4 ${className||""}`}>
    {title && <h3 className="text-white font-semibold mb-3">{title}</h3>}
    {children}
  </div>
);

const Label: React.FC<{ children: React.ReactNode }>
  = ({ children }) => <div className="text-sm text-slate-300 mb-1">{children}</div>;

const Select: React.FC<{ value: string; onChange: (v:string)=>void; options: string[] }>
  = ({ value, onChange, options }) => (
  <select value={value} onChange={e=>onChange(e.target.value)}
    className="w-full rounded-xl bg-slate-800 border border-slate-700 p-2 text-slate-100">
    {options.map(o => <option key={o} value={o}>{o}</option>)}
  </select>
);

const Toggle: React.FC<{ checked: boolean; onChange: (b:boolean)=>void; label: string }>
  = ({ checked, onChange, label }) => (
  <label className="flex items-center gap-3 cursor-pointer select-none">
    <span className={`inline-flex w-11 h-6 rounded-full transition-colors ${checked?"bg-emerald-500":"bg-slate-600"}`}
      onClick={()=>onChange(!checked)}>
      <span className={`h-6 w-6 rounded-full bg-white shadow transform transition-transform ${checked?"translate-x-5":"translate-x-0"}`}/>
    </span>
    <span className="text-slate-200 text-sm">{label}</span>
  </label>
);

const TextOut: React.FC<{ children: React.ReactNode }>
  = ({ children }) => <div className="text-sm text-slate-200 leading-6 whitespace-pre-wrap">{children}</div>;

// ---------- Shared helpers ----------
const circleOptions = ["North", "East", "South", "West"] as const;
const planeOptions = [
  "W→E", "E→W", "N→S", "S→N", "NW→SE", "SE→NW", "NE→SW", "SW→NE"
] as const;
const styleOptions = ["Aggro", "Balanced", "Safer"] as const;

// ---------- VERDANSK BR ----------
function VerdanskBR() {
  const [circle, setCircle] = useState<(typeof circleOptions)[number]>("North");
  const [plane, setPlane] = useState<(typeof planeOptions)[number]>("W→E");
  const [style, setStyle] = useState<(typeof styleOptions)[number]>("Balanced");
  const [uav, setUav] = useState(true);
  const [durable, setDurable] = useState(false);
  const [sr, setSr] = useState("Mix (placement + elims)");

  type Plan = { drop: string, alts: string[], first90: string[], buy: string[], rotation: string[], tips: string[] };

  const matrix: Record<string, Plan> = {
    North: {
      drop: "Storage north rows",
      alts: ["Boneyard west wall", "Airport ATC ridge", "TV Station overlook"],
      first90: [
        "Land one‑building apart (IGL/Entry/Anchor).",
        "Loot fast → armor → first fight by 1:00–1:15.",
        "If plane path favors west, cut to Boneyard for early picks.",
      ],
      buy: [
        "Buy 1: UAV + plates" + (durable?" + durable":""),
        "If cash shy, stack a Safecracker/Scav before rotating.",
      ],
      rotation: [
        "Storage → Boneyard → Stadium/TV (height) → Airport ridge/Military edge.",
      ],
      tips: [
        "Vehicles only to flip elevation or cover‑to‑cover; bail if next 80 m is open/uphill.",
        "SR: prioritize third‑parties off popped UAVs.",
      ]
    },
    East: {
      drop: "Train Station west lots",
      alts: ["Downtown bank block", "Park memorial", "Port ridge"],
      first90: ["Loot two buildings, take first even fight", "Clear roof lines with nades before ladder"],
      buy: ["Buy 1: UAV + precision (or durable)", "Split 2 push / 1 anchor"],
      rotation: ["Train → Downtown roofs (zip) → Park → Port ridge"],
      tips: ["Edge long side; don’t center early", "If zone hard‑east, take Port cranes before Gas 3"],
    },
    South: {
      drop: "Promenade West apartments",
      alts: ["Hills south apts (safer)", "Farmland hedges", "Prison cliffs"],
      first90: ["Avoid long open crosses; wrap via cover", "Take first fight under 75 s"],
      buy: ["Buy 1: UAV + plates", "Rotate to Hospital/Stadium outer if broke"],
      rotation: ["Promenade → Hills → Farmland → Prison cliffs wrap"],
      tips: ["Gas 4+: never raw ladder; use rappel/smoke"],
    },
    West: {
      drop: "Quarry south scaffolds (balanced)",
      alts: ["Lumber ridge", "Farmland", "Boneyard mid (hot)"] ,
      first90: ["Grab cover guns, clear close buildings then rotate high"],
      buy: ["Buy 1: UAV + precision (if SR=placement, choose durable instead)"],
      rotation: ["Quarry high → Dam overlook → Airport outskirts"],
      tips: ["If plane was E→W, expect mirror teams at Lumber — take height first"],
    },
  };

  const chosen = matrix[circle];

  // Style tweaks
  const dropByStyle = useMemo(() => {
    if (style === "Aggro") return [chosen.drop, ...chosen.alts].find(d => /Boneyard|Superstore|Downtown|Stadium/i.test(d)) || chosen.drop;
    if (style === "Safer") return [chosen.drop, ...chosen.alts].find(d => /Hills|Farmland|Prison|Port|ridge|a?pts|cranes/i.test(d)) || chosen.drop;
    return chosen.drop;
  }, [style, chosen]);

  const planText = `Drop: ${dropByStyle}\n\nFirst 90s:\n• ${chosen.first90.join("\n• ")}\n\nFirst Buy:\n• ${chosen.buy.join("\n• ")}\n${uav?"• Pop UAV instantly; hunt isolated pings.":"• If no UAV, take natural power then fish for audio/info."}\n\nRotation:\n• ${chosen.rotation.join("\n• ")}\n\nTips:\n• ${chosen.tips.join("\n• ")}`;

  return (
    <div className="space-y-4">
      <div className="grid md:grid-cols-3 gap-4">
        <Card title="Inputs">
          <div className="space-y-3">
            <div>
              <Label>Circle pull</Label>
              <Select value={circle} onChange={v=>setCircle(v as any)} options={[...circleOptions]} />
            </div>
            <div>
              <Label>Plane path</Label>
              <Select value={plane} onChange={setPlane as any} options={[...planeOptions]} />
            </div>
            <div>
              <Label>Style</Label>
              <Select value={style} onChange={setStyle as any} options={[...styleOptions]} />
            </div>
            <div className="flex flex-col gap-2 mt-1">
              <Toggle checked={uav} onChange={setUav} label="We can afford a UAV at first Buy" />
              <Toggle checked={durable} onChange={setDurable} label="We’ll likely have a durable early" />
            </div>
            <div>
              <Label>SR goal</Label>
              <Select value={sr} onChange={setSr} options={["Placement", "Elims", "Mix (placement + elims)"]} />
            </div>
          </div>
        </Card>
        <Card title="Your Plan" className="md:col-span-2">
          <TextOut>{planText}</TextOut>
        </Card>
      </div>
      <Card title="Checklist (copy to notes)">
        <TextOut>{`[ ] Land one‑building apart (IGL/Entry/Anchor)\n[ ] First Buy by 1:10–1:30  \n[ ] ${uav?"Pop UAV → split 2 push / 1 anchor":"Take natural height → gather info"}\n[ ] Edge long side of zone\n[ ] Final 3 circles: height + headies; gas only with plan`}</TextOut>
      </Card>
    </div>
  );
}

// ---------- REBIRTH ----------
function Rebirth() {
  const [opener, setOpener] = useState("Auto (choose for me)");
  const [style, setStyle] = useState<(typeof styleOptions)[number]>("Balanced");
  const [sweaty, setSweaty] = useState(false);
  const [respawnDisabledSoon, setRespawnDisabledSoon] = useState(false);

  const decideOpener = useMemo(() => {
    if (opener !== "Auto (choose for me)") return opener;
    if (respawnDisabledSoon) return "Coast Chain"; // safer cash path pre‑disable
    if (style === "Aggro") return sweaty?"Anchor Split":"Roof Chain";
    if (style === "Safer") return "Coast Chain";
    return sweaty?"Anchor Split":"Roof Chain";
  }, [opener, style, sweaty, respawnDisabledSoon]);

  const plans: Record<string, { steps: string[], fights: string[], end: string[] }> = {
    "Roof Chain": {
      steps: ["Prison Roof → HQ (hit UAV) → Control → wrap to Industry"],
      fights: ["Stun → hip‑fire chow; anchor holds off‑lane", "When teammate at 8–12 s, play corners to protect timer"],
      end: ["Stay roof edge; pre‑plan two off‑roof drops", "Rappels only with smoke/stuns after Gas 4"],
    },
    "Coast Chain": {
      steps: ["Docks → Harbor → take Factory roof → late gondola/zip to Prison"],
      fights: ["Farm cash and isolated picks; avoid roof chaos early"],
      end: ["Rotate to roof edge late; keep one semtex + one stun for drops"],
    },
    "Anchor Split": {
      steps: ["Stronghold anchor + 2 hit Living Quarters → collapse on HQ"],
      fights: ["Anchor never chases; 2 push trade every chow"],
      end: ["Convert to BR rules when respawn disabled (height > center)"],
    }
  };

  const p = plans[decideOpener];
  const md = `Opener: ${decideOpener}\n\nRoute:\n• ${p.steps.join("\n• ")}\n\nFight Rules:\n• ${p.fights.join("\n• ")}\n\nEnd‑Game:\n• ${p.end.join("\n• ")}`;

  return (
    <div className="space-y-4">
      <div className="grid md:grid-cols-3 gap-4">
        <Card title="Inputs">
          <div className="space-y-3">
            <div>
              <Label>Opener</Label>
              <Select value={opener} onChange={setOpener}
                options={["Auto (choose for me)", "Roof Chain", "Coast Chain", "Anchor Split"]}/>
            </div>
            <div>
              <Label>Style</Label>
              <Select value={style} onChange={setStyle as any} options={[...styleOptions]} />
            </div>
            <div className="flex flex-col gap-2 mt-1">
              <Toggle checked={sweaty} onChange={setSweaty} label="Lobbies look sweaty (avoid day‑1 roof brawls)" />
              <Toggle checked={respawnDisabledSoon} onChange={setRespawnDisabledSoon} label="Respawn disable incoming soon" />
            </div>
          </div>
        </Card>
        <Card title="Your Plan" className="md:col-span-2">
          <TextOut>{md}</TextOut>
        </Card>
      </div>
      <Card title="Checklist">
        <TextOut>{`[ ] First fight within 45–60 s  \n[ ] Don’t wipe early (1 anchors, 2 push)  \n[ ] Protect 8–12 s respawn windows  \n[ ] Roof edge late; avoid raw ladders without util`}</TextOut>
      </Card>
    </div>
  );
}

// ---------- BO6 Ranked ----------
const bo6Maps = ["Hacienda", "Red Card", "Rewind", "Protocol", "Vault", "Dealership"] as const;
const bo6Modes = ["Hardpoint", "Search & Destroy", "Control"] as const;

function BO6() {
  const [map, setMap] = useState<(typeof bo6Maps)[number]>("Hacienda");
  const [mode, setMode] = useState<(typeof bo6Modes)[number]>("Hardpoint");
  const [spawn, setSpawn] = useState("Default/Unknown");
  const [opp, setOpp] = useState("Balanced");
  const [trophies, setTrophies] = useState(true);

  const opener = useMemo(() => {
    if (mode === "Hardpoint") {
      if (map === "Hacienda") return "Break P1 via Garage pinch + Mid stairs stun dump. Rotate 18–20s early.";
      if (map === "Red Card") return "Ticket Office stun + Outer ramp pinch; anchor for back spawns.";
      if (map === "Rewind") return "Fight for P2 spawns early; late‑wrap through back docks.";
      return "Two‑lane pinch; don’t flood front; anchor deep spawns.";
    }
    if (mode === "Search & Destroy") {
      if (map === "Hacienda") return "A: L‑arch smoke; B: Garage pinch. Info first 60–90s, execute at 0:30.";
      if (map === "Protocol") return "2 outer / 2 short split; save tacs for Vault choke retakes.";
      if (map === "Red Card") return "A: Stands→Stage; B: Main steps smoke; watch Ticket Office flank.";
      if (map === "Rewind") return "Take top‑mid control; burst execute at 0:30.";
      if (map === "Dealership") return "A showroom smoke wall; B service pinch (clear rafters).";
      return "Info plays > first bloods; double‑pronged execs; crossfire post‑plant.";
    }
    // Control
    if (map === "Hacienda") return "Attack 3‑1 to A; on D trophy L‑arch, rotate early to B if down lives.";
    if (map === "Protocol") return "Stack first tick then anchor deep to flip them into long lane; pinch on 2‑tick pushes.";
    if (map === "Vault") return "Double‑nade catwalk to open; spend streaks to deny ticks.";
    return "Attack: 3‑1 for first tick; Defense: nade dump A, rotate early to B when needed.";
  }, [map, mode]);

  const notes = useMemo(() => {
    const arr = [
      `Roles: IGL timings • Entry tac dump • Flex fills • Anchor spawns`,
      `Utility: spread tacs; pre‑nade headies; ${trophies?"use trophies to hold": "value stuns/smokes for retakes"}.`,
      mode==="Hardpoint"?"18–20s early rotates unless streak+trophies advantage.":
        mode==="Search & Destroy"?"60–90s info → 30s execute. Post‑plant crossfires; hold a stun for the stick.":
        "Attack 3‑1; convert to spawn‑trap timing with lives lead."
    ];
    if (opp === "Fast") arr.push("Expect early floods; value crossfires over solo chows.");
    if (opp === "Slow") arr.push("Take space early; don’t donate map control.");
    if (spawn !== "Default/Unknown") arr.push(`Spawn: ${spawn} — set first rotation accordingly.`);
    return arr;
  }, [mode, trophies, opp, spawn]);

  return (
    <div className="space-y-4">
      <div className="grid md:grid-cols-3 gap-4">
        <Card title="Inputs">
          <div className="space-y-3">
            <div>
              <Label>Map</Label>
              <Select value={map} onChange={setMap as any} options={[...bo6Maps]} />
            </div>
            <div>
              <Label>Mode</Label>
              <Select value={mode} onChange={setMode as any} options={[...bo6Modes]} />
            </div>
            <div>
              <Label>Spawn / Side</Label>
              <Select value={spawn} onChange={setSpawn as any} options={["Default/Unknown", "Better‑spawn", "Worse‑spawn", "Attack", "Defense"]} />
            </div>
            <div>
              <Label>Opponent style</Label>
              <Select value={opp} onChange={setOpp as any} options={["Balanced", "Fast", "Slow"]} />
            </div>
            <Toggle checked={trophies} onChange={setTrophies} label="We have trophies ready" />
          </div>
        </Card>
        <Card title="Your Opener" className="md:col-span-2">
          <TextOut>{opener}</TextOut>
          <div className="mt-3 border-t border-slate-700 pt-3">
            <TextOut>{notes.map(n=>`• ${n}`).join("\n")}</TextOut>
          </div>
        </Card>
      </div>
      <Card title="Round Checklist">
        <TextOut>{`[ ] Roles locked  \n[ ] Utility spread (no double‑tac same lane)  \n[ ] ${mode==="Hardpoint"?"Rotate at :18–:20 or set up pinch":"Info → exec with two lanes"}  \n[ ] Win rotation/position, not ego chows`}</TextOut>
      </Card>
    </div>
  );
}

// ---------- Root App ----------
const TABS = ["Verdansk BR", "Rebirth Resurgence", "BO6 Ranked"] as const;
export default function App() {
  const [tab, setTab] = useState<(typeof TABS)[number]>("Verdansk BR");
  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 p-4 md:p-6">
      <div className="max-w-5xl mx-auto space-y-4">
        <header className="flex items-center justify-between">
          <h1 className="text-2xl md:text-3xl font-bold">Pre‑Game Coach</h1>
          <p className="text-slate-400 text-sm">Pick your inputs — get a plan instantly.</p>
        </header>
        <nav className="flex gap-2 flex-wrap">
          {TABS.map(k => (
            <button key={k} onClick={()=>setTab(k)}
              className={`px-3 py-2 rounded-xl border border-slate-700 ${tab===k?"bg-slate-800/70":"bg-slate-900/40"} hover:bg-slate-800/60`}>
              {k}
            </button>
          ))}
        </nav>
        {tab === "Verdansk BR" && <VerdanskBR />}
        {tab === "Rebirth Resurgence" && <Rebirth />}
        {tab === "BO6 Ranked" && <BO6 />}
        <footer className="text-xs text-slate-500 pt-4">Tip: screenshot the plan or copy the checklist before you queue.</footer>
      </div>
    </div>
  );
}
