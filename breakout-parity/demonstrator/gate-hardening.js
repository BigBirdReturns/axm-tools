"use strict";

function computeGate(commit=true){
  const margin=truthMinMargin(),risk=estimatedRisk(margin),restore=restorationRate(),load=capacityLoad();
  let gateState="operate",reason="Portfolio remains inside the qualified envelope.",pass=true;
  if(state.knownHoldouts>0||detectHiddenHoldout()){gateState="baseline_incomplete";reason=state.knownHoldouts?"A strategically relevant holdout is outside the baseline.":"Baseline confidence remains unresolved; a hidden holdout may exist.";pass=false;}
  if(margin<6){gateState="hold";reason=`Adverse portfolio margin is ${margin.toFixed(1)} months, below the six-month floor.`;pass=false;}
  if(risk>.05){gateState="hold";reason=`Estimated breach risk is ${pct(risk)}, above the five-percent ceiling.`;pass=false;}
  if(restore<.95){gateState="hold";reason=`Restoration performance is ${pct(restore)}, below the 95-percent floor.`;pass=false;}
  if(state.n1Occurred&&!state.n1Passed){gateState="hold";reason="N-1 capacity has not been demonstrated after the critical-node loss.";pass=false;}
  if(load>1.45){gateState="hold";reason=`Portfolio load is ${load.toFixed(2)}x, beyond the certified saturation boundary.`;pass=false;}
  if(state.falseActions>0){gateState="hold";reason=`${state.falseActions} blocked authority or precondition violation${state.falseActions===1?" was":"s were"} recorded; continued operation is not creditable.`;pass=false;}
  if(state.holdDeclared){gateState="hold";reason="The gate authority declared a HOLD pending reinforcement and recertification.";pass=false;}
  if(activeReal().some(t=>t.breached)){gateState="fail";reason="At least one threat reached coercive advantage before control.";pass=false;}
  state.gate={state:gateState,reason,pass,metrics:{margin,risk,restore,load,n1:state.n1Occurred?state.n1Passed:null,holdouts:state.knownHoldouts}};
  if(commit)log("Gate evaluated",`${gateState.toUpperCase()}: ${reason}`,pass?"good":"warn");
  return state.gate;
}
