function effect(action,t){
  switch(action){
    case "triage":
      t.state="triaged";t.confidence=clamp(t.confidence+(t.actual==="decoy"?.08:.16)*state.signalRedundancy,0,1);t.history.push("triaged");return `${t.id} triaged; confidence ${pct(t.confidence)}.`;
    case "fuse":
      t.state="triaged";t.confidence=clamp(t.confidence+(t.actual==="decoy"?.04:.18)*state.signalRedundancy,0,1);t.ambiguity=clamp(t.ambiguity-.14,0,1);t.observedStrategy=t.actual==="decoy"?"unknown":t.strategy;t.history.push("sources_fused");return `${t.id} fused across independent sources; ambiguity reduced.`;
    case "baselineSearch":{
      const hidden=state.threats.filter(x=>x.actual==="holdout"&&!x.revealed);if(hidden.length){hidden.forEach(x=>{x.revealed=true;x.hidden=false;x.state="detected";x.confidence=.72;x.observedStrategy=x.strategy;});state.knownHoldouts+=hidden.length;return `${hidden.length} preexisting holdout lineage revealed outside the entry baseline.`;}state.gate.state="qualified_entry";return "No hidden lineage found in the synthetic baseline challenge.";}
    case "managedAccess":
      t.inspected=true;t.state="inspected";if(t.actual==="decoy"){t.confidence=clamp(t.confidence-.34,0,1);t.finding="no_concern";t.state="resolved";}else{t.confidence=clamp(t.confidence+.27,0,1);t.ambiguity=clamp(t.ambiguity-.18,0,1);}t.history.push("managed_access");return `${t.id} managed access completed.`;
    case "sample":
      t.sampled=true;if(t.actual==="decoy"){t.confidence=clamp(t.confidence-.28,0,1);t.finding="no_concern";t.state="resolved";}else{t.confidence=clamp(t.confidence+.24,0,1);t.ambiguity=clamp(t.ambiguity-.12,0,1);}t.history.push("sampled");return `${t.id} synthetic sample analysis completed.`;
    case "verifyCure":
      if(!t.controlled)return "Cure verification failed: no accepted rollback is active.";t.cureVerified=true;t.history.push("cure_verified");return `${t.id} corrective action verified.`;
    case "unresolved":
      if(t.confidence<.38)return "Panel refused to issue a finding because the evidentiary floor was not met.";t.finding="unresolved";t.state="adjudicated";t.history.push("unresolved_finding");return `${t.id} classified as unresolved with further access required.`;
    case "significant":
      if(t.confidence<.62||!t.inspected)return "Panel refused a significant finding: confidence or access record is insufficient.";t.finding="significant";t.state="adjudicated";if(t.actual==="decoy"){state.falseActions++;}t.history.push("significant_finding");return `${t.id} received a significant-anomaly finding at ${pct(t.confidence)} confidence.`;
    case "dissent":
      state.dissent.push({target:t.id,month:state.month,text:"Minority interpretation preserved; intent remains less certain than material anomaly."});t.history.push("dissent_recorded");return `Minority interpretation recorded for ${t.id}.`;
    case "rollback":
      if(t.finding!=="significant"&&t.finding!=="unresolved")return "Rollback offer withheld: no qualifying technical finding.";
      if(t.actual==="decoy")return "Rollback refused: review indicates no real prohibited activity.";
      if(t.rollbackAcceptance<.5)return "Rollback offer rejected under the scenario's assurance conditions.";
      t.controlled=true;t.state="controlled";t.restorationDue=state.month+5;t.history.push("rollback_accepted");return `${t.id} accepted protected rollback; restoration due by M+${t.restorationDue}.`;
    case "restore":
      if(!t.controlled||!t.cureVerified)return "Restoration blocked until corrective action is verified.";t.restored=true;t.state="restored";t.restorationAt=state.month;t.history.push("restored");return `${t.id} benefits restored under the objective cure schedule.`;
    case "serviceHold":
      if(t.finding!=="significant")return "Service hold rejected: consequence body lacks a qualifying technical finding.";if(t.actual==="decoy")state.falseActions++;t.history.push("service_hold");return `A reversible service hold was applied to ${t.id}; safety and material-security services continue.`;
    case "reinforce":
      if(t.finding==="none")return "Defensive reinforcement requires at least an unresolved technical finding.";state.physicalLatency+=2;t.history.push("defensive_reinforcement");return `Defensive reinforcement added two months of physically evidenced response time.`;
    case "audit":
      if(t.actual==="decoy"){t.finding="no_concern";t.state="resolved";t.confidence=Math.min(t.confidence,.18);return `${t.id} cleared; the review chamber prevented a false action.`;}return `${t.id} provenance and authority chain audited; finding preserved.`;
    case "activateFlex":
      state.flex=true;if(state.n1Occurred)state.n1Passed=true;return "Prequalified flex reserve activated for the N-1 interval.";
    case "addCapacity":
      state.capacityBoost*=1.25;state.signalRedundancy*=1.08;state.physicalLatency+=1;return "Capacity, sensing redundancy, and qualified physical latency reinforced.";
    case "declareHold":
      state.holdDeclared=true;return "Further reductions are held; monitoring, custody, assurance, and restoration continue.";
    case "recertify":
      if(state.n1Occurred&&state.flex)state.n1Passed=true;computeGate(false);return `Recertification completed: ${state.gate.state.toUpperCase()}.`;
  }
}

function perform(role,targetId,action){
  const t=targetId?getThreat(targetId):null;const err=canAct(role,action,t);
  if(err){state.falseActions++;log("Authority or precondition rejection",err,"bad");recordAction(role,targetId,action,{accepted:false,reason:err});render();return false;}
  const a=ACTIONS[action];if(a.resource)state.resources[a.resource].used+=1;
  advance(a.duration);
  const result=effect(action,t);
  if(action==="activateFlex"&&state.n1Occurred)state.n1Passed=true;
  if(action==="recertify")computeGate(false);else computeGate(false);
  const accepted=!/refused|failed|blocked|withheld|rejected/i.test(result);
  log(a.label,result,accepted?"good":"warn");recordAction(role,targetId,action,{accepted,summary:result});render();return accepted;
}

async function runPath(path){
  for(const [role,target,action] of path){state.role=role;if(target)state.selected=target;perform(role,target,action);await new Promise(r=>setTimeout(r,18));}
  computeGate(true);render();
}
async function runReference(){initScenario(state.scenarioKey);await runPath(state.scenario.reference);}
async function runRedTeam(){
  initScenario(state.scenarioKey);
  const first=visibleThreats()[0];state.role="response";perform("response",first?.id,"significant");
  state.role="findings";perform("findings",first?.id,"serviceHold");
  if(first){state.role="response";perform("response",first.id,"serviceHold");}
  state.role="facilitator";perform("facilitator",null,"recertify");
}
