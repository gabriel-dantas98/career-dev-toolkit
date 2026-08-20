import React from "react";
import {
  AbsoluteFill,
  Easing,
  interpolate,
  Series,
  spring,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";

import {EVAL_STAGES, SCENES} from "./content.mjs";

const colors = {
  background: "#071014",
  panel: "#0D1A20",
  panelStrong: "#11252C",
  border: "#24404A",
  text: "#F2F7F5",
  muted: "#93A7A8",
  cyan: "#61D7C6",
  green: "#8BE0A4",
  amber: "#F4C56A",
  red: "#FF7B72",
};

const fontSans =
  'Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif';
const fontMono =
  '"SFMono-Regular", Consolas, "Liberation Mono", Menlo, monospace';

const clamp = {
  extrapolateLeft: "clamp",
  extrapolateRight: "clamp",
};

const enter = (frame, fps, delay = 0) =>
  spring({
    frame: Math.max(0, frame - delay),
    fps,
    config: {damping: 18, stiffness: 110, mass: 0.8},
    durationInFrames: 24,
  });

const fadeForScene = (frame, duration) =>
  interpolate(frame, [0, 10, duration - 10, duration], [0, 1, 1, 0], {
    ...clamp,
    easing: Easing.inOut(Easing.ease),
  });

const Grid = () => (
  <AbsoluteFill
    style={{
      backgroundImage:
        "linear-gradient(rgba(97,215,198,0.045) 1px, transparent 1px), linear-gradient(90deg, rgba(97,215,198,0.045) 1px, transparent 1px)",
      backgroundSize: "64px 64px",
      maskImage: "linear-gradient(to bottom, black, transparent 92%)",
    }}
  />
);

const StatusPill = ({children, tone = "cyan"}) => {
  const toneColor = {
    amber: colors.amber,
    cyan: colors.cyan,
    green: colors.green,
    red: colors.red,
  }[tone];

  return (
    <div
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 10,
        border: `1px solid ${toneColor}55`,
        borderRadius: 999,
        padding: "8px 14px",
        color: toneColor,
        background: `${toneColor}10`,
        fontFamily: fontMono,
        fontSize: 18,
        fontWeight: 700,
        letterSpacing: "0.04em",
      }}
    >
      <span
        style={{
          width: 8,
          height: 8,
          borderRadius: "50%",
          background: toneColor,
          boxShadow: `0 0 16px ${toneColor}`,
        }}
      />
      {children}
    </div>
  );
};

const SceneShell = ({scene, index, children}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const titleProgress = enter(frame, fps, 2);
  const contentProgress = enter(frame, fps, 10);

  return (
    <AbsoluteFill
      style={{
        backgroundColor: colors.background,
        color: colors.text,
        fontFamily: fontSans,
        opacity: fadeForScene(frame, scene.duration),
      }}
    >
      <Grid />
      <div
        style={{
          position: "absolute",
          top: 54,
          left: 72,
          right: 72,
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          fontFamily: fontMono,
          fontSize: 16,
          letterSpacing: "0.14em",
          color: colors.muted,
        }}
      >
        <span>CAREEROS / ENGINEERING WALKTHROUGH</span>
        <span>{String(index + 1).padStart(2, "0")} / 07</span>
      </div>

      <div
        style={{
          position: "absolute",
          top: 132,
          left: 120,
          right: 120,
          opacity: titleProgress,
          transform: `translateY(${(1 - titleProgress) * 24}px)`,
        }}
      >
        <div
          style={{
            color: colors.cyan,
            fontFamily: fontMono,
            fontSize: 20,
            fontWeight: 700,
            letterSpacing: "0.16em",
            marginBottom: 18,
          }}
        >
          {scene.eyebrow}
        </div>
        <h1
          style={{
            margin: 0,
            maxWidth: 1440,
            fontSize: 70,
            lineHeight: 1.05,
            fontWeight: 620,
            letterSpacing: "-0.035em",
          }}
        >
          {scene.title}
        </h1>
      </div>

      <div
        style={{
          position: "absolute",
          left: 120,
          right: 120,
          top: 344,
          bottom: 110,
          opacity: contentProgress,
          transform: `translateY(${(1 - contentProgress) * 30}px)`,
        }}
      >
        {children}
      </div>

      <div
        style={{
          position: "absolute",
          bottom: 45,
          left: 72,
          right: 72,
          height: 2,
          background: colors.border,
        }}
      >
        <div
          style={{
            width: `${((index + interpolate(frame, [0, scene.duration], [0, 1], clamp)) / 7) * 100}%`,
            height: "100%",
            background: colors.cyan,
          }}
        />
      </div>
    </AbsoluteFill>
  );
};

const ProblemScene = ({scene, index}) => {
  const frame = useCurrentFrame();
  const sweep = interpolate(frame, [18, 90], [0, 1], clamp);

  return (
    <SceneShell scene={scene} index={index}>
      <div style={{display: "grid", gridTemplateColumns: "0.9fr 1.1fr", gap: 72}}>
        <div>
          <div
            style={{
              fontFamily: fontMono,
              fontSize: 86,
              fontWeight: 760,
              color: colors.amber,
              letterSpacing: "-0.06em",
              marginBottom: 12,
            }}
          >
            {scene.lead}
          </div>
          <div style={{fontSize: 24, color: colors.muted, marginBottom: 34}}>
            {scene.note}
          </div>
          <div style={{fontSize: 30, lineHeight: 1.42, maxWidth: 690}}>
            {scene.detail}
          </div>
        </div>
        <div
          style={{
            border: `1px solid ${colors.border}`,
            borderRadius: 20,
            padding: 34,
            background: colors.panel,
          }}
        >
          {["Collect bounded evidence", "Normalize + deduplicate", "Enforce privacy + consent", "Reconcile external projection"].map(
            (label, itemIndex) => (
              <div
                key={label}
                style={{
                  display: "grid",
                  gridTemplateColumns: "42px 1fr",
                  gap: 18,
                  alignItems: "center",
                  padding: "20px 0",
                  borderBottom:
                    itemIndex === 3 ? "none" : `1px solid ${colors.border}`,
                  opacity: interpolate(
                    sweep,
                    [itemIndex * 0.18, itemIndex * 0.18 + 0.28],
                    [0.25, 1],
                    clamp,
                  ),
                }}
              >
                <div
                  style={{
                    width: 34,
                    height: 34,
                    borderRadius: 8,
                    border: `1px solid ${colors.cyan}88`,
                    display: "grid",
                    placeItems: "center",
                    color: colors.cyan,
                    fontFamily: fontMono,
                    fontSize: 15,
                  }}
                >
                  {String(itemIndex + 1).padStart(2, "0")}
                </div>
                <div style={{fontSize: 25}}>{label}</div>
              </div>
            ),
          )}
        </div>
      </div>
    </SceneShell>
  );
};

const pipelineNodes = [
  ["HARVEST", "bounded"],
  ["VALIDATE", "rule IDs"],
  ["SQLCIPHER", "canonical"],
  ["RAW WRITE", "authorized"],
  ["READ-BACK", "exact"],
  ["OUTPUTS", "deploy"],
];

const ArchitectureScene = ({scene, index}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();

  return (
    <SceneShell scene={scene} index={index}>
      <div style={{fontFamily: fontMono, color: colors.muted, fontSize: 19, marginBottom: 34}}>
        {scene.lead}
      </div>
      <div style={{display: "flex", alignItems: "stretch", gap: 10}}>
        {pipelineNodes.map(([label, sublabel], nodeIndex) => {
          const progress = enter(frame, fps, 12 + nodeIndex * 4);
          return (
            <React.Fragment key={label}>
              <div
                style={{
                  flex: 1,
                  minWidth: 0,
                  height: 160,
                  border: `1px solid ${nodeIndex === 2 ? colors.cyan : colors.border}`,
                  borderRadius: 14,
                  background:
                    nodeIndex === 2
                      ? `linear-gradient(145deg, ${colors.panelStrong}, ${colors.cyan}12)`
                      : colors.panel,
                  padding: "28px 18px",
                  opacity: progress,
                  transform: `scale(${0.94 + progress * 0.06})`,
                }}
              >
                <div
                  style={{
                    color: nodeIndex === 2 ? colors.cyan : colors.text,
                    fontFamily: fontMono,
                    fontSize: 20,
                    fontWeight: 700,
                    marginBottom: 20,
                  }}
                >
                  {label}
                </div>
                <div style={{color: colors.muted, fontSize: 19}}>{sublabel}</div>
              </div>
              {nodeIndex < pipelineNodes.length - 1 ? (
                <div
                  style={{
                    alignSelf: "center",
                    color: colors.cyan,
                    fontFamily: fontMono,
                    fontSize: 24,
                    opacity: progress,
                  }}
                >
                  →
                </div>
              ) : null}
            </React.Fragment>
          );
        })}
      </div>
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginTop: 38,
          borderTop: `1px solid ${colors.border}`,
          paddingTop: 28,
        }}
      >
        <div style={{fontSize: 25, color: colors.muted}}>{scene.detail}</div>
        <StatusPill>{scene.note}</StatusPill>
      </div>
    </SceneShell>
  );
};

const HarvestScene = ({scene, index}) => {
  const frame = useCurrentFrame();
  const mergeProgress = interpolate(frame, [30, 78], [0, 1], {
    ...clamp,
    easing: Easing.inOut(Easing.cubic),
  });

  return (
    <SceneShell scene={scene} index={index}>
      <div style={{display: "grid", gridTemplateColumns: "1fr 140px 1fr", alignItems: "center"}}>
        <div style={{display: "grid", gap: 16}}>
          {[
            ["THREAD", "thread:delivery-017", "action + result"],
            ["GITHUB", "github:pr-204", "change + review"],
            ["GOOGLE", "google:event-88", "bounded calendar window"],
          ].map(([source, id, evidence], sourceIndex) => (
            <div
              key={source}
              style={{
                border: `1px solid ${colors.border}`,
                borderRadius: 16,
                padding: 18,
                background: colors.panel,
                transform: `translateX(${mergeProgress * (sourceIndex === 0 ? 16 : 28)}px)`,
              }}
            >
              <div style={{fontFamily: fontMono, color: colors.cyan, fontSize: 17}}>
                {source}
              </div>
              <div style={{fontFamily: fontMono, fontSize: 24, margin: "12px 0"}}>{id}</div>
              <div style={{color: colors.muted, fontSize: 19}}>{evidence}</div>
            </div>
          ))}
        </div>
        <div
          style={{
            textAlign: "center",
            color: colors.cyan,
            fontFamily: fontMono,
            fontSize: 42,
            opacity: mergeProgress,
          }}
        >
          →
        </div>
        <div
          style={{
            border: `1px solid ${colors.cyan}`,
            borderRadius: 18,
            padding: 30,
            background: `linear-gradient(145deg, ${colors.panelStrong}, ${colors.cyan}10)`,
            opacity: 0.25 + mergeProgress * 0.75,
            transform: `scale(${0.96 + mergeProgress * 0.04})`,
          }}
        >
          <div style={{display: "flex", justifyContent: "space-between"}}>
            <span style={{fontFamily: fontMono, color: colors.cyan, fontSize: 17}}>
              CANONICAL RECORD
            </span>
            <StatusPill tone="green">VALIDATED</StatusPill>
          </div>
          <div style={{fontFamily: fontMono, fontSize: 27, margin: "26px 0"}}>
            record:delivery-017
          </div>
          <div style={{color: colors.muted, lineHeight: 1.7, fontSize: 19}}>
            provenance: [thread, github, google]
            <br />
            merged_source_ids: 3
            <br />
            evidence_gaps: explicit
          </div>
        </div>
      </div>
      <div style={{marginTop: 28, display: "flex", justifyContent: "space-between"}}>
        <span style={{fontSize: 23, color: colors.muted}}>{scene.detail}</span>
        <StatusPill>{scene.note}</StatusPill>
      </div>
    </SceneShell>
  );
};

const PrivacyScene = ({scene, index}) => {
  const frame = useCurrentFrame();
  const block = interpolate(frame, [25, 55], [0, 1], clamp);

  return (
    <SceneShell scene={scene} index={index}>
      <div style={{display: "grid", gridTemplateColumns: "1fr 1fr", gap: 30}}>
        <div
          style={{
            border: `1px solid ${colors.green}88`,
            borderRadius: 18,
            padding: 34,
            background: `${colors.green}0A`,
          }}
        >
          <StatusPill tone="green">DESTINATION / GRANTED</StatusPill>
          <div style={{fontFamily: fontMono, fontSize: 29, margin: "34px 0 14px"}}>
            sheet:synthetic-brag
          </div>
          <div style={{fontFamily: fontMono, color: colors.muted, fontSize: 20}}>
            scope: write:bragsheet
          </div>
        </div>
        <div
          style={{
            border: `1px solid ${colors.red}`,
            borderRadius: 18,
            padding: 34,
            background: `${colors.red}0D`,
            transform: `translateX(${(1 - block) * 32}px)`,
            opacity: 0.3 + block * 0.7,
          }}
        >
          <StatusPill tone="red">BACKGROUND / BLOCKED</StatusPill>
          <div style={{fontFamily: fontMono, fontSize: 29, margin: "34px 0 14px"}}>
            job:daily
          </div>
          <div style={{fontFamily: fontMono, color: colors.red, fontSize: 20}}>
            {scene.note}
          </div>
        </div>
      </div>
      <div
        style={{
          marginTop: 36,
          display: "flex",
          justifyContent: "space-between",
          alignItems: "end",
        }}
      >
        <div>
          <div style={{fontFamily: fontMono, fontSize: 39, color: colors.amber}}>
            {scene.lead}
          </div>
          <div style={{fontSize: 24, color: colors.muted, marginTop: 16}}>{scene.detail}</div>
        </div>
        <StatusPill tone="red">NO EXTERNAL CALL</StatusPill>
      </div>
    </SceneShell>
  );
};

const SheetGrid = ({values, accent}) => (
  <div
    style={{
      display: "grid",
      gridTemplateColumns: "80px 1.1fr 1fr 1fr",
      borderTop: `1px solid ${colors.border}`,
      borderLeft: `1px solid ${colors.border}`,
      fontFamily: fontMono,
      fontSize: 18,
    }}
  >
    {values.map((value, valueIndex) => (
      <div
        key={`${value}-${valueIndex}`}
        style={{
          minHeight: 60,
          display: "flex",
          alignItems: "center",
          padding: "0 16px",
          color: valueIndex === 1 ? accent : valueIndex < 4 ? colors.muted : colors.text,
          borderRight: `1px solid ${colors.border}`,
          borderBottom: `1px solid ${colors.border}`,
          background: valueIndex === 1 ? `${accent}0D` : colors.panel,
        }}
      >
        {value}
      </div>
    ))}
  </div>
);

const SheetsScene = ({scene, index}) => {
  const frame = useCurrentFrame();
  const readBack = interpolate(frame, [55, 100], [0, 1], clamp);

  return (
    <SceneShell scene={scene} index={index}>
      <div style={{display: "grid", gridTemplateColumns: "1fr 110px 1fr", alignItems: "center"}}>
        <div>
          <div style={{fontFamily: fontMono, color: colors.muted, fontSize: 17, marginBottom: 12}}>
            CANONICAL PROJECTION
          </div>
          <SheetGrid
            accent={colors.amber}
            values={["ROW", "PERIOD", "TITLE", "STATUS", "02", "'03/04/2026", "Synthetic delivery", "ready"]}
          />
        </div>
        <div style={{textAlign: "center", color: colors.cyan, fontSize: 38}}>⇄</div>
        <div style={{opacity: 0.25 + readBack * 0.75}}>
          <div style={{fontFamily: fontMono, color: colors.muted, fontSize: 17, marginBottom: 12}}>
            UNFORMATTED READ-BACK
          </div>
          <SheetGrid
            accent={colors.green}
            values={["ROW", "PERIOD", "TITLE", "STATUS", "02", "'03/04/2026", "Synthetic delivery", "synced"]}
          />
        </div>
      </div>
      <div style={{display: "flex", justifyContent: "space-between", marginTop: 30}}>
        <div>
          <div style={{fontFamily: fontMono, fontSize: 31, color: colors.amber}}>
            {scene.lead}
          </div>
          <div style={{fontSize: 22, color: colors.muted, marginTop: 12}}>{scene.detail}</div>
        </div>
        <StatusPill tone={readBack > 0.95 ? "green" : "cyan"}>
          {readBack > 0.95 ? "EXACT MATCH" : "VERIFYING"}
        </StatusPill>
      </div>
      <div style={{fontFamily: fontMono, color: colors.muted, fontSize: 17, marginTop: 22}}>
        {scene.note}
      </div>
    </SceneShell>
  );
};

const EvalsScene = ({scene, index}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();

  return (
    <SceneShell scene={scene} index={index}>
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(4, 1fr)",
          gap: 16,
          marginBottom: 28,
        }}
      >
        {EVAL_STAGES.map((stage, stageIndex) => {
          const progress = enter(frame, fps, 8 + stageIndex * 3);
          return (
            <div
              key={stage}
              style={{
                border: `1px solid ${colors.green}66`,
                borderRadius: 14,
                background: `${colors.green}0A`,
                padding: "20px 22px",
                opacity: progress,
                transform: `translateY(${(1 - progress) * 18}px)`,
              }}
            >
              <div style={{fontFamily: fontMono, fontSize: 16, color: colors.muted}}>
                {String(stageIndex + 1).padStart(2, "0")}
              </div>
              <div style={{fontFamily: fontMono, fontSize: 21, margin: "14px 0 18px"}}>
                {stage}
              </div>
              <StatusPill tone="green">PASSED</StatusPill>
            </div>
          );
        })}
      </div>
      <div style={{display: "flex", justifyContent: "space-between", alignItems: "center"}}>
        <div>
          <div style={{fontSize: 29, fontWeight: 650}}>{scene.lead}</div>
          <div style={{fontSize: 21, color: colors.muted, marginTop: 10}}>{scene.detail}</div>
        </div>
        <StatusPill tone="amber">LIVE GOOGLE EXCLUDED</StatusPill>
      </div>
    </SceneShell>
  );
};

const CertificationScene = ({scene, index}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const emphasis = enter(frame, fps, 10);

  return (
    <SceneShell scene={scene} index={index}>
      <div
        style={{
          border: `1px solid ${colors.amber}`,
          borderRadius: 22,
          padding: "44px 52px",
          background: `linear-gradient(120deg, ${colors.amber}0D, ${colors.panel})`,
          display: "grid",
          gridTemplateColumns: "0.75fr 1.25fr",
          gap: 60,
          alignItems: "center",
        }}
      >
        <div>
          <div
            style={{
              fontFamily: fontMono,
              fontSize: 72,
              fontWeight: 800,
              color: colors.amber,
              letterSpacing: "-0.04em",
              transform: `scale(${0.92 + emphasis * 0.08})`,
              transformOrigin: "left center",
            }}
          >
            {scene.lead}
          </div>
          <div style={{fontSize: 22, color: colors.muted, marginTop: 16}}>{scene.note}</div>
        </div>
        <div
          style={{
            borderLeft: `1px solid ${colors.border}`,
            paddingLeft: 48,
            fontSize: 27,
            lineHeight: 1.5,
          }}
        >
          {scene.detail}
        </div>
      </div>
      <div
        style={{
          marginTop: 34,
          fontFamily: fontMono,
          fontSize: 18,
          color: colors.muted,
          display: "flex",
          justifyContent: "space-between",
        }}
      >
        <span>LOCAL CONTRACTS: VERIFIED WITH SYNTHETIC PROVIDERS</span>
        <span style={{color: colors.amber}}>EXTERNAL ACCOUNT: UNTESTED</span>
      </div>
    </SceneShell>
  );
};

const sceneComponents = {
  architecture: ArchitectureScene,
  certification: CertificationScene,
  evals: EvalsScene,
  harvest: HarvestScene,
  privacy: PrivacyScene,
  problem: ProblemScene,
  sheets: SheetsScene,
};

export const CareerOSDemo = () => (
  <AbsoluteFill style={{backgroundColor: colors.background}}>
    <Series>
      {SCENES.map((scene, index) => {
        const Scene = sceneComponents[scene.key];
        return (
          <Series.Sequence key={scene.key} durationInFrames={scene.duration}>
            <Scene scene={scene} index={index} />
          </Series.Sequence>
        );
      })}
    </Series>
  </AbsoluteFill>
);
