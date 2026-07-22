"use strict";

const FIELD_SYNONYMS = {
  item_id: ["item_id","part_id","nsn","niin","sku","material","material_id","part_number","part_no","pn","item_or_part_id_masked","part_or_item_id_masked","required_part_id_masked","linked_part_id_masked","nsn_sku_or_part_token","national_stock_number","national_item_identification_number","stock_number"],
  asset_id: ["asset_id","tail_number","tail_no","tail_num","tail","equipment_id","equipment_number","serial_number","serial_no","sn","vehicle_id","node_id","aircraft_id","aircraft_tail","end_item","asset_id_masked","asset_or_equipment_id_masked"],
  location: ["location","loc","site","warehouse","warehouse_code","warehouse_location","bin","bin_location","supply_node","supply_point","shop","base","base_code","location_or_node_masked","origin_node_masked","destination_node_masked"],
  on_hand: ["on_hand","qty_on_hand","quantity_on_hand","count","stock_on_hand","oh","oh_bal","on_hand_balance","balance_on_hand","stock_balance","qty_oh","on_hand_qty","quantity_on_hand"],
  serviceable_qty: ["serviceable_qty","serviceable","svc","svc_qty","serviceable_balance","available_qty","available_balance","ready_qty","usable_qty","ready_for_issue","rfi_qty","issuable_qty","serviceable_on_hand_qty"],
  allocated_qty: ["allocated_qty","allocated","alloc","alloc_qty","reserved_qty","reserved","committed_qty","committed","commit_qty","due_out","due_out_qty","pegged_qty","due_out_qty"],
  due_in_qty: ["due_in_qty","due_in","di_qty","incoming_qty","inbound_qty","scheduled_receipts"],
  as_of_date: ["as_of_date","as_of","snapshot_date","snapshot_ts","timestamp","date","recorded_at","updated_at","last_update","last_updated","report_date","event_or_status_date","status_date","export_or_capture_date","capture_date","last_count_date"],
  work_order_id: ["work_order_id","work_order","wo_id","wo","job_id","jcn","job_control_number","job_control_no","maintenance_id","maintenance_action_id","mx_id","ticket_id","work_order_or_ticket_id","linked_work_order_id"],
  status: ["status","state","work_status","job_status","maintenance_status","mx_status","condition","mission_capable_status","nmc_status","supply_status","awp_nmcs","status_or_event","availability_status","condition_code_or_status","mission_capable_or_ready_flag"],
  required_part_id: ["required_part_id","required_niin","niin_required","required_nsn","needed_part","part_required","part_needed","material_required","part_or_item_id_masked","required_part_id_masked","linked_part_id_masked","part_id","nsn","niin","material_id"],
  blocking_reason: ["blocking_reason","reason","delay_reason","delay_code","nmc_reason","nmcs_reason","awp_reason","hold_reason","hold_code","awaiting_part_reason","blocking_reason_or_constraint","nmc_or_block_reason","blocked_by"],
  requisition_id: ["requisition_id","requisition_number","req_id","due_in_id","po_id","order_id","document_number","doc_number","milstrip_doc_no","due_in_document","movement_or_duein_id","requisition_order_or_transfer_id"],
  quantity: ["quantity","qty","request_qty","req_qty","ordered_qty","order_qty"],
  due_date: ["due_date","eta","edd","estimated_delivery_date","estimated_ship_date","projected_delivery_date","delivery_date","need_by_date","required_delivery_date","sdd"],
  source_record_id: ["source_record_id","record_id","record_key","transaction_id","source_id","document_id","file_id","report_id","report_row_id","row_id","maintenance_record_id","inventory_record_id","status_record_id","movement_or_duein_id","finding_or_review_id","surface_record_id"],
  claim: ["claim","claimed_state","statement","finding","claim_or_question","what_should_axm_check"],
  evidence_pointer: ["evidence_pointer","row_ref","cell_ref","page","line","url","screenshot_ref"],
  reviewer_role: ["reviewer_role","reviewer","actor_role","role"],
  disposition: ["disposition","decision","review_status"],
  reason: ["reason","rationale","comment","notes","reason_or_limitation"]
};

const SURFACE_RULES = {
  inventory: {requiredAny:[["item_id"],["on_hand","serviceable_qty"]],recommended:["location","allocated_qty","as_of_date"],tier:"inventory_snapshot",passesAs:"Physical availability candidate: inventory position"},
  maintenance: {requiredAny:[["work_order_id"],["asset_id"],["status"]],recommended:["required_part_id","blocking_reason","as_of_date"],tier:"maintenance_event",passesAs:"Physical availability candidate: maintenance/work-order state"},
  due_in: {requiredAny:[["requisition_id"],["item_id","required_part_id"],["quantity"]],recommended:["due_date","status","location"],tier:"movement_or_due_in",passesAs:"Constraint candidate: inbound supply / due-in"},
  claim_evidence: {requiredAny:[["claim"],["source_record_id"],["evidence_pointer"]],recommended:["reviewer_role","disposition","reason"],tier:"claim_to_evidence_link",passesAs:"AXM proof candidate: claim linked to source evidence"},
  review: {requiredAny:[["disposition"],["reviewer_role"]],recommended:["claim","reason","source_record_id"],tier:"human_review_record",passesAs:"Human review candidate: attention routing, not truth adjudication"}
};

const IMG_EXTS = new Set(["png","jpg","jpeg","webp","bmp","gif","tiff","svg"]);
const TEXT_EXTS = new Set(["txt","md","log","xml","yaml","yml","html","htm","eml","rtf"]);
const CSV_EXTS = new Set(["csv","tsv"]);
const JSON_EXTS = new Set(["json","jsonl"]);
const XLSX_EXTS = new Set(["xlsx","xlsm"]);
const DOC_EXTS = new Set(["pdf","docx","pptx","odt"]);
const BINARY_EXPORT_EXTS = new Set(["parquet","sqlite","sqlite3","db","zip","gz","tar"]);
const MAX_FILE_BYTES = 64 * 1024 * 1024;
const MAX_FILES = 50;
const MAX_TOTAL_BYTES = 256 * 1024 * 1024;

const state = {tab:"finding",files:[],results:[],findings:[],findingNote:null,isDemo:true,busy:false,theme:"light"};
const TITLES = {
  finding:["Finding","physical availability tested against the record"],
  surfaces:["Surface acceptance","what passed, what failed, and why"],
  evidence:["Evidence chain","every clause pinned to file · row · SHA-256"],
  asks:["What we need to get started","gaps turned into the smallest next asks"],
  data:["Load data","runs offline · nothing leaves this machine"],
  about:["About","boundary, method, and deployment posture"]
};
const SEV_ORDER = {masked_shortage:0,shortage:1,unknown_availability:2,no_inventory_match:3,no_part_link:4,supportable:5};
const SEV_META = {
  masked_shortage:{label:"Administrative stock masks a physical shortage",color:"red"},
  shortage:{label:"Physical shortage",color:"red"},
  unknown_availability:{label:"Availability cannot be computed from these fields",color:"amber"},
  no_inventory_match:{label:"No inventory record for the blocking part",color:"amber"},
  no_part_link:{label:"Blocked work without part linkage",color:"amber"},
  supportable:{label:"Supportable from stock on record",color:"green"}
};

const $ = id => document.getElementById(id);
const esc = s => String(s ?? "").replace(/[&<>"']/g,m=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[m]));
const getExt = name => {const p=String(name).split(".");return p.length>1?p.pop().toLowerCase():""};
const stem = name => String(name).replace(/\.[^.]+$/ ,"");
const formatBytes = n => n < 1024 ? n+" B" : n < 1048576 ? (n/1024).toFixed(1)+" KB" : (n/1048576).toFixed(1)+" MB";
const normId = v => String(v ?? "").trim().toUpperCase();
const toNum = v => {if(v===null||v===undefined||String(v).trim()==="")return null;const n=parseFloat(String(v).replace(/,/g,""));return Number.isFinite(n)?n:null};
