/* Proposed camera-log interchange inspection. No camera-to-Pi clock mapping is assumed. */
(function (root) {
  'use strict';
  const MAX_BYTES = 5 * 1024 * 1024, MAX_ROWS = 20000, LIST_LIMIT = 100;
  const required = ['frame_seq', 'camera_timestamp_ns', 'camera_clock_id', 'pi_received_monotonic_ns', 'consumer_seen_monotonic_ns', 'status', 'image_ref'];
  function parseCSV(text) {
    if (typeof text !== 'string') throw new TypeError('CSV input must be text');
    if (new TextEncoder().encode(text).length > MAX_BYTES) throw new RangeError('CSV exceeds 5 MiB limit');
    if (text.charCodeAt(0) === 0xFEFF) text = text.slice(1);
    const records = []; let record = [], field = '', quoted = false, closed = false, started = false;
    function endField() { record.push(field); field = ''; closed = false; started = false; }
    function endRecord() {
      endField();
      if (!(record.length === 1 && record[0] === '')) records.push(record);
      record = [];
      if (records.length > MAX_ROWS + 1) throw new RangeError('CSV exceeds 20000 data rows');
    }
    for (let i = 0; i < text.length; i++) {
      const c = text[i];
      if (quoted) {
        if (c === '"') {
          if (text[i + 1] === '"') { field += '"'; i++; }
          else { quoted = false; closed = true; }
        } else field += c;
      } else if (c === ',') endField();
      else if (c === '\n' || c === '\r') { if (c === '\r' && text[i + 1] === '\n') i++; endRecord(); }
      else if (closed) throw new SyntaxError('Unexpected text after closing CSV quote at character ' + i);
      else if (c === '"') { if (started || field.length) throw new SyntaxError('Quote inside unquoted CSV field at character ' + i); quoted = true; started = true; }
      else { field += c; started = true; }
    }
    if (quoted) throw new SyntaxError('Unclosed CSV quoted field');
    if (record.length || field.length || closed || started) endRecord();
    if (!records.length) throw new SyntaxError('CSV is empty');
    const headers = records.shift().map(h => h.trim());
    if (headers.some(h => !h) || new Set(headers).size !== headers.length) throw new SyntaxError('CSV headers must be nonempty and unique');
    const rows = records.map((values, index) => {
      if (values.length !== headers.length) throw new SyntaxError('CSV record ' + (index + 2) + ' has ' + values.length + ' fields; expected ' + headers.length);
      const row = Object.create(null); headers.forEach((key, i) => { row[key] = values[i]; }); return row;
    });
    Object.defineProperty(rows, 'headers', { value: headers, enumerable: false });
    return rows;
  }
  function integer(value) {
    if (typeof value === 'number' && !Number.isSafeInteger(value)) return null;
    const text = String(value === undefined || value === null ? '' : value).trim();
    if (!/^\d{1,40}$/.test(text)) return null;
    return BigInt(text);
  }
  const compare = (a, b) => a < b ? -1 : a > b ? 1 : 0;
  function milliseconds(ns) { return Number(ns / 1000000n) + Number(ns % 1000000n) / 1000000; }
  function analyze(rows) {
    if (!Array.isArray(rows)) throw new TypeError('Frames must be an array');
    if (rows.length > MAX_ROWS) throw new RangeError('Frames exceed 20000 rows');
    if (rows.length && required.some(h => !(h in rows[0]))) throw new SyntaxError('Missing required headers: ' + required.filter(h => !(h in rows[0])).join(', '));
    const sessions = new Map(), invalidRows = [], queueSamples = [], sequenceGapRanges = [], lateArrivalDetails = [], duplicateSequenceIds = [], cameraClockIds = new Set();
    let receivedFrames = 0, explicitMissing = 0, sequenceGaps = 0n, lateArrivals = 0;
    rows.forEach((row, index) => {
      const rowNumber = index + 2, reasons = [], seq = integer(row.frame_seq), sessionId = String(row.session_id || '(unspecified session)');
      if (seq === null) reasons.push('Invalid nonnegative integer frame_seq');
      const status = String(row.status || '').trim();
      const missing = status === 'absent_in_sequence';
      const camera = String(row.camera_timestamp_ns || '').trim(), clock = String(row.camera_clock_id || '').trim();
      if (camera && integer(camera) === null) reasons.push('Invalid camera_timestamp_ns');
      if (camera && !clock) reasons.push('Camera timestamp has no camera_clock_id');
      if (clock) cameraClockIds.add(clock);
      const piText = String(row.pi_received_monotonic_ns || '').trim(), consumerText = String(row.consumer_seen_monotonic_ns || '').trim();
      const pi = integer(piText), consumer = integer(consumerText);
      if (missing) {
        explicitMissing++;
        if (piText || consumerText) reasons.push('Explicit absent row also contains receipt/consumer timestamps');
      } else {
        if (!status) reasons.push('Missing status');
        if (pi === null) reasons.push('Missing or invalid pi_received_monotonic_ns');
        if (consumer === null) reasons.push('Missing or invalid consumer_seen_monotonic_ns');
        if (pi !== null && seq !== null) receivedFrames++;
        if (pi !== null && consumer !== null) {
          const delta = consumer - pi;
          if (delta < 0n) reasons.push('Negative Pi-to-consumer queue latency; timestamp ordering or clock assumption invalid');
          else queueSamples.push({ row: rowNumber, sessionId, frameSeq: seq === null ? String(row.frame_seq) : seq.toString(), latencyNs: delta.toString(), latencyMs: milliseconds(delta) });
        }
      }
      if (seq !== null) {
        if (!sessions.has(sessionId)) sessions.set(sessionId, { ids: new Map(), arrivals: [] });
        const session = sessions.get(sessionId), key = seq.toString();
        if (!session.ids.has(key)) session.ids.set(key, { seq, rows: [] });
        session.ids.get(key).rows.push(rowNumber);
        if (!missing && pi !== null) session.arrivals.push({ seq, pi, row: rowNumber });
      }
      if (reasons.length) invalidRows.push({ row: rowNumber, reasons });
    });
    for (const [sessionId, session] of sessions) {
      const ids = Array.from(session.ids.values()).sort((a, b) => compare(a.seq, b.seq));
      for (let i = 0; i < ids.length; i++) {
        if (ids[i].rows.length > 1 && duplicateSequenceIds.length < LIST_LIMIT) duplicateSequenceIds.push({ sessionId, frameSeq: ids[i].seq.toString(), rows: ids[i].rows.slice(0, LIST_LIMIT) });
        if (i && ids[i].seq > ids[i - 1].seq + 1n) {
          const count = ids[i].seq - ids[i - 1].seq - 1n; sequenceGaps += count;
          if (sequenceGapRanges.length < LIST_LIMIT) sequenceGapRanges.push({ sessionId, from: (ids[i - 1].seq + 1n).toString(), to: (ids[i].seq - 1n).toString(), count: count.toString() });
        }
      }
      // Compute inversions from actual Pi receipt order, independent of CSV row order or status labels.
      session.arrivals.sort((a, b) => compare(a.pi, b.pi) || a.row - b.row);
      let high = null;
      for (let i = 0; i < session.arrivals.length;) {
        let end = i + 1; while (end < session.arrivals.length && session.arrivals[end].pi === session.arrivals[i].pi) end++;
        for (let j = i; j < end; j++) {
          const arrival = session.arrivals[j];
          if (high !== null && arrival.seq < high) { lateArrivals++; if (lateArrivalDetails.length < LIST_LIMIT) lateArrivalDetails.push({ sessionId, frameSeq: arrival.seq.toString(), row: arrival.row, piReceivedMonotonicNs: arrival.pi.toString(), newerSequenceAlreadyReceived: high.toString() }); }
        }
        for (let j = i; j < end; j++) if (high === null || session.arrivals[j].seq > high) high = session.arrivals[j].seq;
        i = end;
      }
    }
    const sorted = queueSamples.map(s => s.latencyMs).sort((a, b) => a - b), n = sorted.length;
    return { rowCount: rows.length, receivedFrames, explicitMissing, sequenceGaps: sequenceGaps <= BigInt(Number.MAX_SAFE_INTEGER) ? Number(sequenceGaps) : sequenceGaps.toString(), sequenceGapsExact: sequenceGaps.toString(), sequenceGapRanges, lateArrivals, lateArrivalDetails, duplicateSequenceIds, queueLatencyMs: { count: n, min: n ? sorted[0] : null, median: n ? (n % 2 ? sorted[(n - 1) / 2] : (sorted[n / 2 - 1] + sorted[n / 2]) / 2) : null, p95: n ? sorted[Math.ceil(n * 0.95) - 1] : null, max: n ? sorted[n - 1] : null }, queueSamples, invalidRows, cameraClockIds: [...cameraClockIds], clockBoundary: 'Only consumer_seen_monotonic_ns minus pi_received_monotonic_ns is calculated, assuming both use the same Pi monotonic clock. Camera timestamps are preserved as strings and never subtracted from Pi timestamps; no clock mapping or synchronization evidence is supplied.', limitations: ['Sequence gaps are counted only between observed IDs within each session; capture-start/end loss and sequence resets cannot be inferred.', 'Explicit absent rows occupy their sequence ID and are not double-counted as unrepresented sequence gaps.', 'Missing sequence IDs or explicit absence do not locate the point of loss.', 'Late arrivals use strictly earlier Pi receipt timestamps; equal-time ordering is unknown.', 'Latency nanosecond differences use BigInt exactly; millisecond summaries are floating point. P95 uses the nearest-rank definition.', 'Diagnostic lists and duplicate row lists are capped at ' + LIST_LIMIT + '; aggregate gap and late counts remain complete.'], listLimit: LIST_LIMIT, valid: invalidRows.length === 0 };
  }
  function inspectFrames(text) {
    const rows = parseCSV(text);
    if (required.some(h => !rows.headers.includes(h))) throw new SyntaxError('Missing required frame headers');
    return analyze(rows);
  }
  const api = Object.freeze({ parseCSV, inspectFrames, analyze, limits: { maxBytes: MAX_BYTES, maxRows: MAX_ROWS, listLimit: LIST_LIMIT } });
  root.SDcapture = api;
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
})(globalThis);
