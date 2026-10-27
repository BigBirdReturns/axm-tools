/* Abstract, non-weaponized 2D measurement/control quality harness. No product qualification. */
(function (root) {
  'use strict';
  const version = '1.0.0';
  const scope = 'Browser reference experiment: abstract industrial 2D motion and measurement quality only. Not a flight model, product integration, field qualification, or real-customer acceptance.';
  const limits = Object.freeze({ maxError: 0.28, rmsError: 0.12, finalError: 0.12, staleExpirySeconds: 1.8 });
  const developmentSeeds = Object.freeze([42, 73, 109]);
  const freshSeeds = Object.freeze([307, 509, 887]);
  function canonical(value) {
    if (value === null || typeof value !== 'object') {
      if (typeof value === 'number' && !Number.isFinite(value)) throw new TypeError('Non-finite evidence');
      if (value === undefined || typeof value === 'function') throw new TypeError('Unsupported evidence value');
      return JSON.stringify(value);
    }
    if (Array.isArray(value)) return '[' + value.map(canonical).join(',') + ']';
    return '{' + Object.keys(value).sort().map(k => JSON.stringify(k) + ':' + canonical(value[k])).join(',') + '}';
  }
  function rng(seed) {
    let a = seed >>> 0;
    return () => { a += 0x6D2B79F5; let t = a; t = Math.imul(t ^ t >>> 15, t | 1); t ^= t + Math.imul(t ^ t >>> 7, t | 61); return ((t ^ t >>> 14) >>> 0) / 4294967296; };
  }
  function target(t) {
    return { x: 1.4 * Math.sin(0.48 * t), y: 0.8 * Math.sin(0.72 * t), vx: 0.672 * Math.cos(0.48 * t), vy: 0.576 * Math.cos(0.72 * t) };
  }
  function run(options = {}) {
    const config = { seed: options.seed === undefined ? 42 : options.seed, controller: options.controller || 'reactive', fault: options.fault || 'none', ticks: options.ticks === undefined ? 240 : options.ticks, dt: options.dt === undefined ? 0.05 : options.dt };
    if (!Number.isInteger(config.seed) || config.seed < 0 || config.seed > 4294967295) throw new RangeError('seed must be a uint32');
    if (!['reactive', 'supported'].includes(config.controller)) throw new RangeError('Unknown controller');
    if (!['none', 'dropout', 'delay', 'bias'].includes(config.fault)) throw new RangeError('Unknown fault');
    if (!Number.isInteger(config.ticks) || config.ticks < 120 || config.ticks > 4000 || !Number.isFinite(config.dt) || config.dt < 0.01 || config.dt > 0.1) throw new RangeError('Use 120–4000 ticks and dt 0.01–0.1');
    const random = rng(config.seed), frames = [], positions = [];
    let x = 0, y = 0, obs = { x: 0, y: 0, sourceTick: 0 }, maxError = 0, sumSquare = 0, expiredTicks = 0, faultTicks = 0;
    // Fault windows scale with test duration, so every supported configuration exercises its named perturbation.
    const start = Math.floor(config.ticks * 0.3), end = Math.floor(config.ticks * 0.44);
    const delayTicks = Math.max(1, Math.round(0.6 / config.dt));
    for (let tick = 0; tick < config.ticks; tick++) {
      const t = tick * config.dt, goal = target(t), active = config.fault !== 'none' && tick >= start && tick < end;
      positions.push({ x, y });
      if (active) faultTicks++;
      const delivered = !(active && config.fault === 'dropout');
      if (delivered) {
        const sourceTick = active && config.fault === 'delay' ? Math.max(0, tick - delayTicks) : tick;
        const p = positions[sourceTick];
        obs = { x: p.x + (random() - 0.5) * 0.006 + (active && config.fault === 'bias' ? 0.48 : 0), y: p.y + (random() - 0.5) * 0.006, sourceTick };
      }
      const staleSeconds = (tick - obs.sourceTick) * config.dt;
      const expired = staleSeconds > limits.staleExpirySeconds;
      if (expired) expiredTicks++;
      // Known commanded displacement since the measurement timestamp is a deliberately explicit toy-model predictor.
      // It assumes ideal actuation; it does not infer unknown bias or prove robustness to unmodeled dynamics.
      const source = positions[obs.sourceTick];
      const estimateX = config.controller === 'supported' ? obs.x + x - source.x : obs.x;
      const estimateY = config.controller === 'supported' ? obs.y + y - source.y : obs.y;
      const error = Math.hypot(x - goal.x, y - goal.y);
      maxError = Math.max(maxError, error); sumSquare += error * error;
      let vx = goal.vx + 3 * (goal.x - estimateX), vy = goal.vy + 3 * (goal.y - estimateY);
      const speed = Math.hypot(vx, vy), speedLimit = 1.6;
      if (speed > speedLimit) { vx *= speedLimit / speed; vy *= speedLimit / speed; }
      if (config.controller === 'supported' && expired) { vx = 0; vy = 0; }
      frames.push({ tick, t, x, y, observedX: obs.x, observedY: obs.y, targetX: goal.x, targetY: goal.y, estimateX, estimateY, vx, vy, supported: config.controller === 'supported', error, sourceTick: obs.sourceTick, staleSeconds, measurementDelivered: delivered, faultActive: active, staleExpired: expired });
      x += vx * config.dt; y += vy * config.dt;
    }
    const metrics = { maxError, rmsError: Math.sqrt(sumSquare / config.ticks), finalError: frames[frames.length - 1].error, expiredTicks, faultTicks, tickCount: frames.length, durationSeconds: (config.ticks - 1) * config.dt, maxStaleSeconds: Math.max(...frames.map(f => f.staleSeconds)) };
    const checks = [
      { id: 'finite-evidence', label: 'Complete finite trajectory', actual: frames.length, limit: config.ticks, passed: frames.length === config.ticks && frames.every(f => Object.values(f).every(v => typeof v !== 'number' || Number.isFinite(v))) },
      { id: 'peak-error', label: 'Peak tracking error ≤ 0.28 abstract units', actual: metrics.maxError, limit: limits.maxError, passed: metrics.maxError <= limits.maxError },
      { id: 'rms-error', label: 'RMS tracking error ≤ 0.12 abstract units', actual: metrics.rmsError, limit: limits.rmsError, passed: metrics.rmsError <= limits.rmsError },
      { id: 'final-error', label: 'Final tracking error ≤ 0.12 abstract units', actual: metrics.finalError, limit: limits.finalError, passed: metrics.finalError <= limits.finalError },
      { id: 'measurement-age', label: 'No measurement older than 1.8 seconds', actual: metrics.expiredTicks, limit: 0, passed: metrics.expiredTicks === 0 }
    ];
    return { id: `sim-${version}-${config.seed}-${config.controller}-${config.fault}-${config.ticks}-${config.dt}`, version, config, frames, metrics, checks, passed: checks.every(c => c.passed), scope, criteria: { ...limits }, model: 'Ideal velocity actuator; smooth known path; noisy position observations; time-stamped fault injection. Supported controller predicts known commanded displacement and stops on expired measurements. Bias remains unobservable.' };
  }
  function runSuite(options = {}) {
    const seeds = options.seeds || freshSeeds, faults = options.faults || ['none', 'dropout', 'delay', 'bias'];
    if (!Array.isArray(seeds) || !seeds.length || !Array.isArray(faults) || !faults.length || seeds.length * faults.length > 100) throw new RangeError('Suite requires 1–100 cases');
    const runs = seeds.flatMap(seed => faults.map(fault => run({ seed, fault, controller: options.controller || 'supported', ticks: options.ticks, dt: options.dt })));
    const passed = runs.filter(r => r.passed).length;
    return { version, runs, passed, total: runs.length, allPassed: passed === runs.length, controller: options.controller || 'supported', seeds: [...seeds], faults: [...faults], cohort: seeds.every(s => !developmentSeeds.includes(s)) ? 'fresh-seed evaluation (not proof of unseen scenario generalization)' : 'contains development seeds', scope, criteria: { ...limits } };
  }
  function evidence(runRecord) {
    // Bind all decision-bearing fields, complete frames, declared predicates, and version to the digest.
    const { integrity, ...payload } = runRecord;
    return payload;
  }
  // FIPS 180-4 SHA-256 fallback for local files and insecure preview origins.
  // Same canonical UTF-8 bytes and same digest as Web Crypto; no weaker admission path.
  function sha256Bytes(input) {
    const K = [0x428a2f98,0x71374491,0xb5c0fbcf,0xe9b5dba5,0x3956c25b,0x59f111f1,0x923f82a4,0xab1c5ed5,0xd807aa98,0x12835b01,0x243185be,0x550c7dc3,0x72be5d74,0x80deb1fe,0x9bdc06a7,0xc19bf174,0xe49b69c1,0xefbe4786,0x0fc19dc6,0x240ca1cc,0x2de92c6f,0x4a7484aa,0x5cb0a9dc,0x76f988da,0x983e5152,0xa831c66d,0xb00327c8,0xbf597fc7,0xc6e00bf3,0xd5a79147,0x06ca6351,0x14292967,0x27b70a85,0x2e1b2138,0x4d2c6dfc,0x53380d13,0x650a7354,0x766a0abb,0x81c2c92e,0x92722c85,0xa2bfe8a1,0xa81a664b,0xc24b8b70,0xc76c51a3,0xd192e819,0xd6990624,0xf40e3585,0x106aa070,0x19a4c116,0x1e376c08,0x2748774c,0x34b0bcb5,0x391c0cb3,0x4ed8aa4a,0x5b9cca4f,0x682e6ff3,0x748f82ee,0x78a5636f,0x84c87814,0x8cc70208,0x90befffa,0xa4506ceb,0xbef9a3f7,0xc67178f2];
    const length=Math.ceil((input.length+9)/64)*64, bytes=new Uint8Array(length), dv=new DataView(bytes.buffer), w=new Uint32Array(64);
    bytes.set(input);bytes[input.length]=0x80;dv.setUint32(length-8,Math.floor(input.length/0x20000000));dv.setUint32(length-4,(input.length*8)>>>0);
    const h=new Uint32Array([0x6a09e667,0xbb67ae85,0x3c6ef372,0xa54ff53a,0x510e527f,0x9b05688c,0x1f83d9ab,0x5be0cd19]),rotr=(x,n)=>(x>>>n)|(x<<(32-n));
    for(let offset=0;offset<length;offset+=64){
      for(let i=0;i<16;i++)w[i]=dv.getUint32(offset+i*4);
      for(let i=16;i<64;i++){const x=w[i-15],y=w[i-2];w[i]=(w[i-16]+(rotr(x,7)^rotr(x,18)^(x>>>3))+w[i-7]+(rotr(y,17)^rotr(y,19)^(y>>>10)))>>>0;}
      let [a,b,c,d,e,f,g,j]=h;
      for(let i=0;i<64;i++){const t1=(j+(rotr(e,6)^rotr(e,11)^rotr(e,25))+((e&f)^(~e&g))+K[i]+w[i])>>>0,t2=((rotr(a,2)^rotr(a,13)^rotr(a,22))+((a&b)^(a&c)^(b&c)))>>>0;j=g;g=f;f=e;e=(d+t1)>>>0;d=c;c=b;b=a;a=(t1+t2)>>>0;}
      const result=[a,b,c,d,e,f,g,j];for(let i=0;i<8;i++)h[i]=(h[i]+result[i])>>>0;
    }
    return Array.from(h,x=>x.toString(16).padStart(8,'0')).join('');
  }
  async function digest(runRecord) {
    const bytes = new TextEncoder().encode(canonical(evidence(runRecord)));
    if (root.crypto && root.crypto.subtle) {
      const hash = await root.crypto.subtle.digest('SHA-256', bytes);
      return Array.from(new Uint8Array(hash), x => x.toString(16).padStart(2, '0')).join('');
    }
    return sha256Bytes(bytes);
  }
  async function seal(runRecord) {
    runRecord.integrity = { algorithm: 'SHA-256', digest: await digest(runRecord), coverage: 'All run fields except integrity, including complete frames, configuration, criteria, metrics and checks', meaning: 'Record integrity only; not proof of correctness, provenance, qualification or external attestation.' };
    return runRecord;
  }
  async function verify(runRecord) {
    if (!runRecord || !runRecord.integrity || runRecord.integrity.algorithm !== 'SHA-256') return false;
    try { return runRecord.integrity.digest === await digest(runRecord); } catch (_) { return false; }
  }
  root.SimEngine = Object.freeze({ version, scope, limits, developmentSeeds, freshSeeds, run, runSuite, canonical, seal, verify, integrity: Object.freeze({ verify }) });
})(globalThis);
