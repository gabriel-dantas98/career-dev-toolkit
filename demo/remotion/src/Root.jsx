import React from "react";
import {Composition} from "remotion";

import {CareerOSDemo} from "./CareerOSDemo.jsx";
import {COMPOSITION} from "./content.mjs";

export const RemotionRoot = () => (
  <Composition
    id={COMPOSITION.id}
    component={CareerOSDemo}
    durationInFrames={COMPOSITION.durationInFrames}
    fps={COMPOSITION.fps}
    width={COMPOSITION.width}
    height={COMPOSITION.height}
  />
);
