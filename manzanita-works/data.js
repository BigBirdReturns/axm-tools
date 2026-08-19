window.MW_DREAMBOARD_CONFIG={
 release:'mw-operating-dreamboard-v0.2.0',
 inputs:[
  {id:'toolshare',label:'ToolShare / MyTurn',target:['tools'],programs:['essential-tools'],resolution:'Physical inventory, reservation, checkout, return, and fee mechanics remain a bounded adapter around Manzanita-owned member, policy, project, and custody references.'},
  {id:'timebank',label:'time-bank sketch',target:['time'],programs:['essential-time'],resolution:'Verified contribution, acceptance, sponsorship, and credit clearing belong to a governed commons rather than a bilateral swap spreadsheet.'},
  {id:'pilotage',label:'pilotage',target:['pilotage','knowledge'],programs:['essential-pilotage'],resolution:'Human navigation and hand-holding become an admitted capacity class while accountable providers retain the substantive service.'},
  {id:'ebike',label:'e-bike project',target:['mobility','tools'],programs:['mobility'],resolution:'Mobility draws on equipment, repair capacity, instruction, local authority, custody, money, and later hardware adapters.'},
  {id:'workshops',label:'workshops',target:['time','talent','space','knowledge'],programs:['prevention'],resolution:'Workshops are projects that consume space, tools, instructors, volunteers, knowledge, money, and participant handoff.'},
  {id:'support',label:'prevention & support',target:['time','talent','pilotage','knowledge'],programs:['prevention'],resolution:'Purpose-limited support requires privacy, safety, referral, authority, evidence, and acceptance boundaries before it enters a commons.'},
  {id:'fundraising',label:'fundraising',target:['money'],programs:['money'],resolution:'Fundraising is one resource and reporting lens. It cannot become the identity system, project ledger, volunteer system, tool ledger, or organizational memory.'},
  {id:'volunteers',label:'volunteers',target:['time','talent','pilotage'],programs:['essential-time','essential-pilotage','prevention'],resolution:'Volunteers provide capacity only when scope, eligibility, performance, acceptance, evidence, and handoff remain explicit.'},
  {id:'stripe',label:'Stripe concern',target:['money'],programs:['money'],resolution:'Processor dependence is managed by adapters, exportability, reconciliation, and replacement tests rather than by allowing a payment rail to define the institution.'},
  {id:'oss',label:'OSS / community sweep',target:['knowledge','talent'],programs:['essential-time','money'],resolution:'Every missing function is first searched as adopt, adapt, wrap, donor, or hold. Build only the irreducibly organization-specific layer.'},
  {id:'space',label:'rooms & shared space',target:['space'],programs:['prevention','essential-tools'],resolution:'Space is a capacity class with access, scheduling, safety, custody, and program-purpose rules.'},
  {id:'hardware',label:'hardware later',target:['tools','mobility'],programs:['mobility','essential-tools'],resolution:'Lockers, e-bikes, sensors, and mesh nodes remain physical-edge adapters that emit governed custody and condition events.'}
 ],
 capacities:[
  {id:'tools',label:'Tools',icon:'🔧',desc:'Physical equipment and custody.'},
  {id:'time',label:'Time',icon:'◷',desc:'Verified human contribution.'},
  {id:'talent',label:'Talent',icon:'◎',desc:'Skills and accountable service.'},
  {id:'pilotage',label:'Pilotage',icon:'◉',desc:'Navigation and bounded handoff.'},
  {id:'money',label:'Money',icon:'＄',desc:'Dues, rentals, donations, grants.'},
  {id:'mobility',label:'Mobility',icon:'♢',desc:'Transport, repair, access.'},
  {id:'knowledge',label:'Knowledge',icon:'▤',desc:'Procedures, teaching, institutional memory.'},
  {id:'space',label:'Space',icon:'⌂',desc:'Rooms, storage, workshops, land.'}
 ],
 jobs:[
  {id:'classify',icon:'⌘',label:'Classify the institutional object',summary:'Separate the organization, its programs, and its suppliers before choosing software.',mechanism:'Name the shared functions, records, obligations, authorities, and failure modes.',receipt:'Operating Fabric ontology and program map.'},
  {id:'map',icon:'⌬',label:'Map people, authority, information, technology, physical resources, and money as one system',summary:'Keep neighboring layers distinct so an implementation cannot quietly own a fact it merely processes.',mechanism:'Actor, role, authority, evidence, project, resource, supplier, event, receipt, and handoff remain separate objects.',receipt:'Architecture layers and control questions.'},
  {id:'own',icon:'♢',label:'Decide what Manzanita must own versus what vendors can provide',summary:'The organization owns identity, authority, semantics, accepted events, and durable records.',mechanism:'Every external system receives an adopt, adapt, wrap, donor, hold, or build disposition.',receipt:'Commodity-perimeter registry and replacement tests.'},
  {id:'prototype',icon:'⟳',label:'Turn fragmented programs into an operating model, then into a falsifiable prototype',summary:'Move from conversation to canonical model, working surface, adversarial test, and bounded handoff.',mechanism:'Prototype only after the authority and evidence model is explicit; reject states the institution would refuse.',receipt:'Live place fabric, Essential Attention, and governed exchange candidate.'}
 ],
 programs:[
  {id:'essential-tools',label:'Essential Tools',icon:'🔧',note:'tool custody',capacities:['tools','space','money'],own:'Program purpose, member relationship, local policy, canonical tool references, accepted custody receipts.',commodity:'MyTurn or another inventory system performs reservations, checkout, return, and fees.',next:'Define the exact export and reconciliation contract.'},
  {id:'essential-time',label:'Essential Time',icon:'◷',note:'contribution and credits',capacities:['time','talent','pilotage'],own:'Credit policy, eligible performance, acceptance authority, named participant accounts, portable receipts.',commodity:'Time-bank workflow donors may inform interface and operations.',next:'Operate one real low-consequence contribution chain.'},
  {id:'essential-pilotage',label:'Essential Pilotage',icon:'◉',note:'human navigation and handoff',capacities:['pilotage','time','knowledge'],own:'Scope, referral boundary, accepted service, contribution recognition, next accountable provider.',commodity:'Scheduling, messaging, forms, maps, and directories remain replaceable.',next:'Define recipient acknowledgement and steward acceptance.'},
  {id:'mobility',label:'Mobility / E-bike',icon:'♢',note:'repair and access',capacities:['mobility','tools','talent','money'],own:'Project purpose, participants, eligibility, safety, local authority, condition and custody semantics.',commodity:'Tool custody now; hardware and mesh adapters later.',next:'Map repair, access, custody, and instruction events.'},
  {id:'prevention',label:'Prevention & Support',icon:'♢',note:'purpose-limited service',capacities:['time','talent','pilotage','space','knowledge'],own:'Purpose limitation, privacy, safety, service authority, acceptance, referral and evidence boundary.',commodity:'Forms, scheduling, messaging, donor tooling, and specialist systems remain replaceable.',next:'Admit only bounded capacity needs into the commons.'},
  {id:'stewardship',label:'Stewardship / Place',icon:'▲',note:'evidence and safe action',capacities:['knowledge','tools','time','money'],own:'Place interpretation, evidence class, purpose firewall, safe-action logic, local authority and handoff.',commodity:'External data and provider services remain bounded inputs.',next:'Carry qualified needs into Attention or the commons.'},
  {id:'money',label:'Money / Fundraising',icon:'＄',note:'dues, rentals, donations, restrictions',capacities:['money'],own:'Constituent continuity, purpose, project allocation, restrictions, commitments, receipts, durable transaction references.',commodity:'Givebutter, Network for Good, Stripe, Square, and later rails move money or render views.',next:'Build the dashboard as a projection over canonical identity, purpose, project, restriction, processor, and receipt.'}
 ],
 rules:[
  {id:'identity',icon:'◎',label:'Identity',note:'Manzanita owns the relationships and record.',detail:'A vendor account may reference a person or organization, but it does not become the canonical relationship.'},
  {id:'authority',icon:'⚖',label:'Authority',note:'A dashboard does not create standing.',detail:'No interface, model, or processor may manufacture acceptance, obligation, credit, representation, or external effect.'},
  {id:'evidence',icon:'☑',label:'Evidence',note:'Accepted work must be receipted.',detail:'Intent, commitment, performed event, acknowledgement, acceptance, credit, settlement, and custody close remain distinct.'},
  {id:'handoff',icon:'↪',label:'Handoff',note:'Pilotage prepares the next safe action.',detail:'The next accountable provider receives only the bounded context, evidence, purpose, and authority required.'},
  {id:'perimeter',icon:'◌',label:'Commodity perimeter',note:'MyTurn, processors, fundraising platforms, OSS, and hardware are replaceable machinery.',detail:'The organization must be able to reconstruct its own operating record after supplier loss.'}
 ],
 receipts:[
  {id:'place',state:'LIVE',label:'Place & Stewardship',note:'Photographic Manzanita place fabric with apertures, roles, purpose limits, local export, and Essential Attention handoff.',url:'https://bigbirdreturns.github.io/axm-tools/manzanita/'},
  {id:'attention',state:'LIVE',label:'Essential Attention',note:'Local evidence, authority, decision, effect-boundary, replay, and portable handoff runtime.',url:'https://bigbirdreturns.github.io/axm-tools/essential-attention/'},
  {id:'commons',state:'LOCAL',label:'Governed capacity exchange',note:'Seat-authorized event dependencies, per-event receipts, named accounts, and hostile-packet refusal.',url:''},
  {id:'fabric',state:'REVIEW',label:'Operating Fabric',note:'The common institutional model shown on this board, with no live organizational or external effects.',url:''}
 ]
};
