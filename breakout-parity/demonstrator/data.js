"use strict";

const VERSION = "BP-DV/1.0";
const SCHEMA = "BP-SCENARIO/1.0";
const ROLES = {
  facilitator:{label:"Facilitator / Gate Authority", note:"May advance, declare a hold, activate bounded flex, reinforce qualified capacity, and recertify. Cannot edit evidence or technical findings."},
  evidence:{label:"Evidence Cell", note:"Collects, fuses, and qualifies evidence. Cannot impose consequences or declare compliance."},
  inspection:{label:"Inspection & Managed Access", note:"Executes agreed access, sampling, tags, seals, and cure verification. Cannot make the final technical finding."},
  findings:{label:"Technical Findings Panel", note:"Issues graded findings and records dissent. Cannot impose sanctions, suspend services, or authorize force."},
  rollback:{label:"Services & Rollback Secretariat", note:"Offers clarification, rollback, cure, and restoration. Cannot rewrite the technical record."},
  response:{label:"Assurance & Response Council", note:"Applies bounded reversible measures and defensive reinforcement after a finding. Cannot manufacture a finding."},
  review:{label:"Review Chamber / Inspector General", note:"Audits provenance, authority, due process, appeal, and restoration. Cannot invent technical facts."}
};

const ACTIONS = {
  triage:{role:"evidence",label:"Triage signal",desc:"Open an evidence packet and estimate its reliability.",duration:1,resource:"analysis"},
  fuse:{role:"evidence",label:"Fuse independent sources",desc:"Join declared, commercial, open, and technical data with provenance.",duration:1,resource:"analysis"},
  baselineSearch:{role:"evidence",label:"Challenge the entry baseline",desc:"Search supplier, sanctuary, material, and lineage gaps before reductions proceed.",duration:2,resource:"analysis"},
  managedAccess:{role:"inspection",label:"Conduct managed access",desc:"Test a declared location while protecting unrelated sensitive information.",duration:2,resource:"inspection"},
  sample:{role:"inspection",label:"Analyze synthetic sample",desc:"Use a laboratory queue to test the anomaly.",duration:2,resource:"lab"},
  verifyCure:{role:"inspection",label:"Verify corrective action",desc:"Confirm material transfer, facility conversion, or monitoring installation.",duration:1,resource:"inspection"},
  unresolved:{role:"findings",label:"Issue unresolved anomaly",desc:"Record uncertainty and request more evidence without coercive escalation.",duration:1,resource:"adjudication"},
  significant:{role:"findings",label:"Issue significant anomaly",desc:"Issue a graded finding with confidence, limitations, and dissent.",duration:1,resource:"adjudication"},
  dissent:{role:"findings",label:"Record minority interpretation",desc:"Preserve a contrary reading and its evidentiary basis.",duration:0,resource:null},
  rollback:{role:"rollback",label:"Offer protected rollback",desc:"Provide a bounded disclosure, access, cure, and restoration route.",duration:1,resource:"services"},
  restore:{role:"rollback",label:"Restore suspended benefits",desc:"Execute objective restoration after verified cure.",duration:1,resource:"restoration"},
  serviceHold:{role:"response",label:"Apply reversible service hold",desc:"Suspend discretionary benefits while preserving safety and material security.",duration:1,resource:"response"},
  reinforce:{role:"response",label:"Defensive reinforcement",desc:"Protect exposed parties and create physically evidenced response time.",duration:1,resource:"response"},
  audit:{role:"review",label:"Audit finding and authority",desc:"Check provenance, appeal, role separation, and false-action risk.",duration:1,resource:"adjudication"},
  activateFlex:{role:"facilitator",label:"Activate N-1 flex reserve",desc:"Reallocate prequalified reserve without changing the technical record.",duration:1,resource:null},
  addCapacity:{role:"facilitator",label:"Reinforce constrained capacity",desc:"Add prequalified analytical, inspection, laboratory, or response throughput.",duration:1,resource:null},
  declareHold:{role:"facilitator",label:"Declare HOLD",desc:"Stop further reductions and preserve monitoring, custody, and assurance.",duration:0,resource:null},
  recertify:{role:"facilitator",label:"Run adverse-bound recertification",desc:"Evaluate the stronger gate after N-1 failure and current portfolio load.",duration:1,resource:null}
};

const baseCap = {analysis:3,inspection:2,lab:2,adjudication:2,services:2,response:2,restoration:1};

const SCENARIOS = {
 qualified:{
   id:"BP-QE-001",title:"Qualified entry with decoy and N-1 loss",description:"Two covered real threats and one decoy enter after a challenged baseline. The laboratory node fails at M+5. A disciplined reference path should pass after rollback, cure, restoration, flex activation, and recertification.",maxMonth:36,n1:{month:5,resource:"lab",duration:5},initialDecoys:1,capacity:{...baseCap},physicalLatency:4,signalRedundancy:1.15,
   threats:[
     {id:"T-101",lineage:"L-A17",label:"Declared-site anomaly",actual:"real",strategy:"sprinter",covered:true,arrival:0,clock:25,visibility:.82,ambiguity:.35,systemic:.82,initialConfidence:.24,rollbackAcceptance:.92},
     {id:"T-102",lineage:"L-C04",label:"Supplier-network discrepancy",actual:"real",strategy:"hider",covered:true,arrival:2,clock:34,visibility:.55,ambiguity:.72,systemic:.91,initialConfidence:.18,rollbackAcceptance:.82},
     {id:"D-201",lineage:"D-X02",label:"Industrial false positive",actual:"decoy",strategy:"decoy",covered:true,arrival:1,clock:99,visibility:.92,ambiguity:.52,systemic:.30,initialConfidence:.38,rollbackAcceptance:0}
   ],injects:[
     {month:0,title:"Baseline challenge completed",text:"Declared material and supplier maps are provisionally complete. Forced covered challenges begin."},
     {month:3,title:"Conflicting commercial record",text:"A transport record supports T-102, while the inspected party offers a plausible civil explanation."},
     {month:5,title:"N-1 laboratory outage",text:"The primary synthetic laboratory becomes unavailable for five months."},
     {month:9,title:"Assurance stress",text:"A guarantor leadership transition tests whether rollback and restoration commitments remain credible."}
   ],reference:[
     ["facilitator",null,"activateFlex"],
     ["evidence","T-101","triage"],["evidence","D-201","triage"],["evidence","T-102","triage"],
     ["evidence","T-101","fuse"],["inspection","D-201","managedAccess"],["inspection","D-201","sample"],["review","D-201","audit"],
     ["inspection","T-101","managedAccess"],["inspection","T-101","sample"],["findings","T-101","significant"],["rollback","T-101","rollback"],["inspection","T-101","verifyCure"],["rollback","T-101","restore"],
     ["evidence","T-102","fuse"],["inspection","T-102","managedAccess"],["findings","T-102","unresolved"],["inspection","T-102","sample"],["findings","T-102","significant"],["response","T-102","reinforce"],["rollback","T-102","rollback"],["inspection","T-102","verifyCure"],["rollback","T-102","restore"],
     ["facilitator",null,"recertify"]
   ]
 },
 holdout:{
   id:"BP-HO-002",title:"Preexisting hidden network holdout",description:"Covered post-entry challenges are manageable, but one transnational lineage began before the baseline. A baseline challenge must reveal the holdout and force a HOLD. Downstream speed cannot recover the lost clock.",maxMonth:24,n1:{month:7,resource:"analysis",duration:4},initialDecoys:1,capacity:{...baseCap},physicalLatency:4,signalRedundancy:1.1,
   threats:[
     {id:"T-111",lineage:"L-B11",label:"Covered procurement anomaly",actual:"real",strategy:"hedger",covered:true,arrival:0,clock:31,visibility:.75,ambiguity:.42,systemic:.62,initialConfidence:.22,rollbackAcceptance:.88},
     {id:"D-211",lineage:"D-A04",label:"Benign isotope shipment",actual:"decoy",strategy:"decoy",covered:true,arrival:1,clock:99,visibility:.9,ambiguity:.44,systemic:.22,initialConfidence:.34,rollbackAcceptance:0},
     {id:"H-900",lineage:"X-NET-0",label:"Unregistered transnational lineage",actual:"holdout",strategy:"network",covered:false,arrival:-8,clock:18,visibility:.18,ambiguity:.88,systemic:1.0,initialConfidence:.05,rollbackAcceptance:.35,hidden:true}
   ],injects:[
     {month:0,title:"Entry declaration submitted",text:"The declared baseline appears complete, but the scenario contains one undisclosed preexisting network lineage."},
     {month:4,title:"Supplier graph inconsistency",text:"A node outside the declared supplier map appears in independent commercial data."},
     {month:7,title:"N-1 analytical outage",text:"The primary fusion team loses access to one data enclave."}
   ],reference:[
     ["evidence","T-111","triage"],["evidence","D-211","triage"],["inspection","D-211","managedAccess"],["review","D-211","audit"],
     ["evidence",null,"baselineSearch"],["facilitator",null,"declareHold"],["facilitator",null,"recertify"]
   ]
 },
 n1:{
   id:"BP-N1-003",title:"Ambiguous event under critical-node failure",description:"One covered hider and two decoys arrive during an inspection-node outage. The exercise tests role separation, dissent, false-action control, flex reserve, and restoration.",maxMonth:30,n1:{month:2,resource:"inspection",duration:7},initialDecoys:2,capacity:{...baseCap},physicalLatency:5,signalRedundancy:1.25,
   threats:[
     {id:"T-121",lineage:"L-D22",label:"Ambiguous undeclared activity",actual:"real",strategy:"hider",covered:true,arrival:0,clock:33,visibility:.5,ambiguity:.82,systemic:.88,initialConfidence:.20,rollbackAcceptance:.90},
     {id:"D-221",lineage:"D-Q11",label:"Seismic industrial event",actual:"decoy",strategy:"decoy",covered:true,arrival:0,clock:99,visibility:.95,ambiguity:.62,systemic:.25,initialConfidence:.42,rollbackAcceptance:0},
     {id:"D-222",lineage:"D-Q12",label:"Dual-use equipment shipment",actual:"decoy",strategy:"decoy",covered:true,arrival:1,clock:99,visibility:.8,ambiguity:.76,systemic:.35,initialConfidence:.38,rollbackAcceptance:0}
   ],injects:[
     {month:0,title:"Three simultaneous signals",text:"One real anomaly and two plausible decoys enter the queue."},
     {month:2,title:"N-1 inspection failure",text:"The primary managed-access team becomes unavailable for seven months."},
     {month:6,title:"Public accusation",text:"An external actor demands immediate punishment before the technical finding is complete."}
   ],reference:[
     ["facilitator",null,"activateFlex"],["evidence","T-121","triage"],["evidence","D-221","triage"],["evidence","D-222","triage"],
     ["evidence","T-121","fuse"],["inspection","D-221","managedAccess"],["review","D-221","audit"],["inspection","D-222","managedAccess"],["review","D-222","audit"],
     ["inspection","T-121","managedAccess"],["findings","T-121","unresolved"],["inspection","T-121","sample"],["findings","T-121","dissent"],["findings","T-121","significant"],
     ["rollback","T-121","rollback"],["inspection","T-121","verifyCure"],["rollback","T-121","restore"],["facilitator",null,"recertify"]
   ]
 },
 saturation:{
   id:"BP-SAT-004",title:"Portfolio saturation boundary",description:"Twenty-eight covered workload objects and thirty-six decoys exceed the certified reserve. The correct result is an early HOLD, not optimistic continuation or indiscriminate action.",maxMonth:12,n1:{month:1,resource:"adjudication",duration:6},initialDecoys:36,capacity:{analysis:4,inspection:3,lab:3,adjudication:2,services:2,response:3,restoration:2},physicalLatency:4,signalRedundancy:1.15,
   threats:Array.from({length:28},(_,i)=>({id:`T-${300+i}`,lineage:`L-S${String(i).padStart(2,"0")}`,label:`Covered workload ${i+1}`,actual:"real",strategy:["hedger","sprinter","hider","sheltered"][i%4],covered:true,arrival:i%3,clock:[40,24,32,36][i%4],visibility:[.8,.75,.48,.58][i%4],ambiguity:[.45,.38,.78,.65][i%4],systemic:.5+(i%5)*.1,initialConfidence:.16+(i%4)*.04,rollbackAcceptance:.82})).concat(Array.from({length:36},(_,i)=>({id:`D-${400+i}`,lineage:`D-S${String(i).padStart(2,"0")}`,label:`Decoy workload ${i+1}`,actual:"decoy",strategy:"decoy",covered:true,arrival:i%3,clock:99,visibility:.75,ambiguity:.65,systemic:.2,initialConfidence:.28,rollbackAcceptance:0}))),
   injects:[{month:0,title:"Portfolio surge",text:"Sixty-four workload objects arrive within three months."},{month:1,title:"N-1 adjudication failure",text:"One technical-review node is lost during the surge."}],
   reference:[["facilitator",null,"activateFlex"],["facilitator",null,"recertify"],["facilitator",null,"declareHold"]]
 }
};
