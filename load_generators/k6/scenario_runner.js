import http from 'k6/http';
import { sleep } from 'k6';

const DEFAULT_SCENARIO_FILE = __ENV.FORZIUM_SCENARIO_FILE || '../../scenarios/release_v0_1_4.json';
const SCENARIO_ID = __ENV.FORZIUM_SCENARIO_ID || 'steady-baseline';
const BASE_URL = __ENV.FORZIUM_BASE_URL || 'http://127.0.0.1:8000';
const DURATION_SCALE = __ENV.FORZIUM_DURATION_SCALE ? parseFloat(__ENV.FORZIUM_DURATION_SCALE) : 1.0;
const MAX_REQUESTS = __ENV.FORZIUM_MAX_REQUESTS ? parseInt(__ENV.FORZIUM_MAX_REQUESTS, 10) : null;
const RAMP_RESOLUTION = __ENV.FORZIUM_RAMP_RESOLUTION ? parseFloat(__ENV.FORZIUM_RAMP_RESOLUTION) : 8.0;

const scenarioDocument = JSON.parse(open(DEFAULT_SCENARIO_FILE));
const scenarioData = Array.isArray(scenarioDocument.scenarios)
  ? scenarioDocument.scenarios
  : Array.isArray(scenarioDocument)
  ? scenarioDocument
  : [];
const scenario = scenarioData.find((item) => item.id === SCENARIO_ID || item.name === SCENARIO_ID);
if (!scenario) {
  throw new Error(`Scenario '${SCENARIO_ID}' not present in ${DEFAULT_SCENARIO_FILE}`);
}

class SeededRNG {
  constructor(seed) {
    const normalised = Math.floor(seed) >>> 0;
    this.state = normalised === 0 ? 0x6d2b79f5 : normalised;
    this._gaussSpare = null;
  }

  next() {
    this.state = (1664525 * this.state + 1013904223) >>> 0;
    return (this.state & 0xffffffff) / 0x100000000;
  }

  nextNonZero() {
    const value = this.next();
    return value === 0 ? Number.MIN_VALUE : value;
  }

  expovariate(lambda) {
    if (lambda <= 0) {
      return 0;
    }
    return -Math.log(1 - this.nextNonZero()) / lambda;
  }

  gauss(mu, sigma) {
    if (this._gaussSpare !== null) {
      const spare = this._gaussSpare;
      this._gaussSpare = null;
      return mu + spare * sigma;
    }
    let u1 = 0;
    let u2 = 0;
    while (u1 === 0) {
      u1 = this.next();
      u2 = this.next();
    }
    const mag = Math.sqrt(-2.0 * Math.log(u1));
    const z0 = mag * Math.cos(2.0 * Math.PI * u2);
    const z1 = mag * Math.sin(2.0 * Math.PI * u2);
    this._gaussSpare = z1;
    return mu + z0 * sigma;
  }

  lognormal(mean, sigma) {
    return Math.exp(this.gauss(mean, sigma));
  }

  gammavariate(shape, scale) {
    if (shape <= 0 || scale <= 0) {
      return 0;
    }
    if (shape < 1) {
      const u = this.nextNonZero();
      return this.gammavariate(shape + 1, scale) * Math.pow(u, 1 / shape);
    }
    const d = shape - 1 / 3;
    const c = 1 / Math.sqrt(9 * d);
    while (true) {
      let x = this.gauss(0, 1);
      let v = Math.pow(1 + c * x, 3);
      if (v <= 0) {
        continue;
      }
      const u = this.next();
      if (u < 1 - 0.0331 * Math.pow(x, 4)) {
        return d * v * scale;
      }
      if (Math.log(u) < 0.5 * x * x + d * (1 - v + Math.log(v))) {
        return d * v * scale;
      }
    }
  }
}

const PATH_PARAM_REGEX = /{([^}:]+)(?::[^}]+)?}/g;

function constantStage({ startOffset, duration, targetRps, stage, includeInMetrics, sequenceStart }) {
  const entries = [];
  if (targetRps <= 0 || duration <= 0) {
    return { entries, sequence: sequenceStart };
  }
  const interval = 1.0 / targetRps;
  let elapsed = 0;
  let sequence = sequenceStart;
  while (elapsed < duration) {
    entries.push({
      sequence,
      offset_s: startOffset + elapsed,
      stage,
      include_in_metrics: includeInMetrics,
      demand_rps: targetRps,
    });
    elapsed += interval;
    sequence += 1;
  }
  return { entries, sequence };
}

function poissonStage({ startOffset, duration, lambdaRps, stage, sequenceStart, seed }) {
  const entries = [];
  if (lambdaRps <= 0 || duration <= 0) {
    return { entries, sequence: sequenceStart };
  }
  const rng = new SeededRNG(seed);
  let elapsed = 0;
  let sequence = sequenceStart;
  while (elapsed < duration) {
    elapsed += rng.expovariate(lambdaRps);
    if (elapsed >= duration) {
      break;
    }
    entries.push({
      sequence,
      offset_s: startOffset + elapsed,
      stage,
      include_in_metrics: true,
      demand_rps: lambdaRps,
    });
    sequence += 1;
  }
  return { entries, sequence };
}

function rampStage({ startOffset, duration, startRps, endRps, stage, sequenceStart }) {
  const segments = Math.max(1, Math.round(duration * RAMP_RESOLUTION));
  const segDuration = duration / segments;
  let sequence = sequenceStart;
  const entries = [];
  for (let idx = 0; idx < segments; idx += 1) {
    const frac = (idx + 0.5) / segments;
    const instantRps = startRps + (endRps - startRps) * frac;
    const result = constantStage({
      startOffset: startOffset + idx * segDuration,
      duration: segDuration,
      targetRps: instantRps,
      stage,
      includeInMetrics: true,
      sequenceStart: sequence,
    });
    entries.push(...result.entries);
    sequence = result.sequence;
  }
  return { entries, sequence };
}

function spikeStage({ startOffset, prewarm, spikeDuration, recoveryDuration, spikeRps, recoveryRps, stagePrefix, sequenceStart }) {
  let sequence = sequenceStart;
  const entries = [];
  if (prewarm.duration > 0) {
    const preResult = constantStage({
      startOffset,
      duration: prewarm.duration,
      targetRps: prewarm.rps,
      stage: `${stagePrefix}-prewarm`,
      includeInMetrics: false,
      sequenceStart: sequence,
    });
    entries.push(...preResult.entries);
    sequence = preResult.sequence;
    startOffset += prewarm.duration;
  }
  const spikeResult = constantStage({
    startOffset,
    duration: spikeDuration,
    targetRps: spikeRps,
    stage: stagePrefix,
    includeInMetrics: true,
    sequenceStart: sequence,
  });
  entries.push(...spikeResult.entries);
  sequence = spikeResult.sequence;
  startOffset += spikeDuration;
  if (recoveryDuration > 0) {
    const recoveryResult = constantStage({
      startOffset,
      duration: recoveryDuration,
      targetRps: recoveryRps,
      stage: `${stagePrefix}-recovery`,
      includeInMetrics: true,
      sequenceStart: sequence,
    });
    entries.push(...recoveryResult.entries);
    sequence = recoveryResult.sequence;
    startOffset += recoveryDuration;
  }
  return { entries, sequence, offset: startOffset };
}

function buildPlan(scenarioDefinition) {
  const entries = [];
  let currentOffset = 0;
  let sequence = 0;
  const warmup = scenarioDefinition.warmup || {};
  const pattern = scenarioDefinition.pattern || {};
  const warmDuration = Number(warmup.duration_s || 0) * DURATION_SCALE;
  const warmTarget = Number(pattern.target_rps || pattern.lambda_rps || 1.0);
  if (warmDuration > 0) {
    const result = constantStage({
      startOffset: currentOffset,
      duration: warmDuration,
      targetRps: warmTarget,
      stage: 'warmup',
      includeInMetrics: !(warmup.discard_metrics === true),
      sequenceStart: sequence,
    });
    entries.push(...result.entries);
    sequence = result.sequence;
    currentOffset += warmDuration;
  }
  const patternType = pattern.type || 'steady';
  if (patternType === 'steady') {
    const duration = Number(pattern.duration_s || 1.0) * DURATION_SCALE;
    const target = Number(pattern.target_rps || 1.0);
    const result = constantStage({
      startOffset: currentOffset,
      duration,
      targetRps: target,
      stage: 'steady',
      includeInMetrics: true,
      sequenceStart: sequence,
    });
    entries.push(...result.entries);
    sequence = result.sequence;
    currentOffset += duration;
  } else if (patternType === 'poisson') {
    const duration = Number(pattern.duration_s || 1.0) * DURATION_SCALE;
    const lambdaRps = Number(pattern.lambda_rps || 1.0);
    const result = poissonStage({
      startOffset: currentOffset,
      duration,
      lambdaRps,
      stage: 'poisson',
      sequenceStart: sequence,
      seed: Number((scenarioDefinition.seed || {}).traffic || 0),
    });
    entries.push(...result.entries);
    sequence = result.sequence;
    currentOffset += duration;
  } else if (patternType === 'burst') {
    const stages = Array.isArray(pattern.stages) ? pattern.stages : [];
    stages.forEach((stageDef, index) => {
      const duration = Number(stageDef.duration_s || 1.0) * DURATION_SCALE;
      const target = Number(stageDef.target_rps || 1.0);
      const stageName = `burst-${index + 1}`;
      const result = constantStage({
        startOffset: currentOffset,
        duration,
        targetRps: target,
        stage: stageName,
        includeInMetrics: true,
        sequenceStart: sequence,
      });
      entries.push(...result.entries);
      sequence = result.sequence;
      currentOffset += duration;
    });
  } else if (patternType === 'ramp') {
    const phases = Array.isArray(pattern.phases) ? pattern.phases : [];
    phases.forEach((phase, index) => {
      const duration = Number(phase.duration_s || 1.0) * DURATION_SCALE;
      const startRps = Number(phase.start_rps || 1.0);
      const endRps = Number(phase.end_rps || startRps);
      const stageName = `ramp-${index + 1}`;
      const result = rampStage({
        startOffset: currentOffset,
        duration,
        startRps,
        endRps,
        stage: stageName,
        sequenceStart: sequence,
      });
      entries.push(...result.entries);
      sequence = result.sequence;
      currentOffset += duration;
    });
  } else if (patternType === 'spike') {
    const prewarmDuration = Number(pattern.pre_warm_duration_s || 0) * DURATION_SCALE;
    const spikeDuration = Number(pattern.spike_duration_s || 1.0) * DURATION_SCALE;
    const recoveryDuration = Number(pattern.recovery_duration_s || 0) * DURATION_SCALE;
    const spikeRps = Number(pattern.spike_rps || 1.0);
    const recoveryRps = Number(pattern.recovery_rps || Math.max(spikeRps * 0.3, 1.0));
    const prewarmRps = Number(pattern.pre_warm_rps || recoveryRps);
    const result = spikeStage({
      startOffset: currentOffset,
      prewarm: { duration: prewarmDuration, rps: prewarmRps },
      spikeDuration,
      recoveryDuration,
      spikeRps,
      recoveryRps,
      stagePrefix: 'spike',
      sequenceStart: sequence,
    });
    entries.push(...result.entries);
    sequence = result.sequence;
    currentOffset = result.offset ?? currentOffset + spikeDuration + recoveryDuration;
  } else {
    const result = constantStage({
      startOffset: currentOffset,
      duration: 1.0 * DURATION_SCALE,
      targetRps: 1.0,
      stage: 'fallback',
      includeInMetrics: true,
      sequenceStart: sequence,
    });
    entries.push(...result.entries);
    sequence = result.sequence;
    currentOffset += 1.0 * DURATION_SCALE;
  }
  entries.sort((a, b) => a.offset_s - b.offset_s);
  return { entries, totalDuration: currentOffset };
}

const plan = buildPlan(scenario);
let planEntries = plan.entries;
if (MAX_REQUESTS !== null && planEntries.length > MAX_REQUESTS) {
  planEntries = planEntries.slice(0, MAX_REQUESTS);
}
const totalEntries = planEntries.length;
const concurrency = Math.max(1, Number(scenario.concurrency || 1));
const iterationsPerVu = Math.ceil(totalEntries / concurrency);
const effectiveDuration = totalEntries > 0 ? planEntries[totalEntries - 1].offset_s : 0;
const maxDurationSeconds = Math.ceil(Math.max(plan.totalDuration, effectiveDuration) + 10);

export const options = {
  scenarios: {
    forzium: {
      executor: 'per-vu-iterations',
      vus: concurrency,
      iterations: iterationsPerVu,
      maxDuration: `${maxDurationSeconds}s`,
    },
  },
  thresholds: {
    http_req_failed: ['rate<0.05'],
  },
};

const payloadSeed = Number((scenario.seed || {}).payload || 0);
const trafficSeed = Number((scenario.seed || {}).traffic || 0);

function resolvePath(sequence) {
  const template = scenario.request.path || '/';
  const params = scenario.request.path_params || {};
  return template.replace(PATH_PARAM_REGEX, (match, name) => {
    const spec = params[name] || {};
    const seed = spec.seed !== undefined ? Number(spec.seed) : payloadSeed;
    const rng = new SeededRNG(seed + sequence * 31);
    const distribution = spec.distribution || 'sequential';
    if (distribution === 'zipf') {
      const expo = Number((spec.parameters || {}).s || 1.0);
      const size = Number((spec.parameters || {}).size || 1000);
      const weights = [];
      let total = 0;
      for (let index = 0; index < size; index += 1) {
        const weight = 1 / Math.pow(index + 1, expo);
        weights.push(weight);
        total += weight;
      }
      const probe = rng.next() * total;
      let cumulative = 0;
      for (let idx = 0; idx < size; idx += 1) {
        cumulative += weights[idx];
        if (probe <= cumulative) {
          return String(idx + 1);
        }
      }
      return String(size);
    }
    if (distribution === 'sequential') {
      const base = Number((spec.parameters || {}).start || 0);
      return String(base + sequence);
    }
    return String(Math.floor(rng.next() * 1_000_000));
  });
}

function samplePayloadSize(sequence) {
  const template = scenario.request;
  const baseSize = Number(template.payload_size_bytes || 0);
  if (!template.payload_distribution || template.payload_distribution === 'fixed' || baseSize <= 0) {
    return baseSize;
  }
  const rng = new SeededRNG(payloadSeed + sequence * 29);
  if (template.payload_distribution === 'lognormal') {
    const mean = Number((template.payload_parameters || {}).mean || 1.0);
    const sigma = Number((template.payload_parameters || {}).sigma || 0.25);
    return Math.floor(rng.lognormal(mean, sigma));
  }
  if (template.payload_distribution === 'gamma') {
    const shape = Number((template.payload_parameters || {}).shape || 2.0);
    const scale = Number((template.payload_parameters || {}).scale || 1.0);
    return Math.floor(rng.gammavariate(shape, scale));
  }
  if (template.payload_distribution === 'mixture') {
    const components = Array.isArray((template.payload_parameters || {}).components)
      ? template.payload_parameters.components
      : [];
    if (components.length === 0) {
      return baseSize;
    }
    const weights = components.map((component) => Number(component.weight || 1.0));
    const total = weights.reduce((acc, value) => acc + value, 0);
    const probe = rng.next() * (total || 1);
    let cumulative = 0;
    for (let index = 0; index < components.length; index += 1) {
      cumulative += weights[index];
      if (probe <= cumulative) {
        const component = components[index];
        const distribution = component.distribution || 'normal';
        const parameters = component.parameters || {};
        if (distribution === 'normal') {
          const mean = Number(parameters.mean || baseSize);
          const stddev = Number(parameters.stddev || mean * 0.1);
          return Math.max(1, Math.floor(Math.abs(rng.gauss(mean, stddev))));
        }
        if (distribution === 'exponential') {
          const rate = Number(parameters.rate || 1.0);
          return Math.max(1, Math.floor(rng.expovariate(rate)));
        }
        break;
      }
    }
    return baseSize;
  }
  return baseSize;
}

function buildPayload(sequence) {
  const method = (scenario.request.method || 'GET').toUpperCase();
  if (method === 'GET' || method === 'DELETE') {
    return null;
  }
  const size = Math.max(1, Math.min(samplePayloadSize(sequence), Math.max(Number(scenario.request.payload_size_bytes || 0) * 4, 1)));
  const blob = 'x'.repeat(size);
  return { sequence, blob };
}

function chooseTenant(entry) {
  const tenants = scenario.tenants || {};
  const header = tenants.header || 'X-Tenant-ID';
  if (Array.isArray(tenants.distribution)) {
    const weights = tenants.distribution.map((item) => Number(item.weight || 1.0));
    const values = tenants.distribution.map((item) => item.tenant || 'default');
    const total = weights.reduce((acc, value) => acc + value, 0);
    const rng = new SeededRNG(trafficSeed + entry.sequence * 17);
    const probe = rng.next() * (total || 1);
    let cumulative = 0;
    for (let index = 0; index < values.length; index += 1) {
      cumulative += weights[index];
      if (probe <= cumulative) {
        return { header, value: values[index] };
      }
    }
    return { header, value: values[values.length - 1] || 'default' };
  }
  if (tenants.rotation_order && Array.isArray(tenants.rotation_order.sequence)) {
    const sequence = tenants.rotation_order.sequence;
    if (sequence.length === 0) {
      return { header, value: 'default' };
    }
    const cycleSeconds = Number(tenants.rotation_order.cycle_seconds || 1.0);
    if (cycleSeconds > 0) {
      const cycleIndex = Math.floor(entry.offset_s / cycleSeconds) % sequence.length;
      return { header, value: sequence[cycleIndex] };
    }
    const index = entry.sequence % sequence.length;
    return { header, value: sequence[index] };
  }
  return { header, value: 'default' };
}

function resolveRequest(entry) {
  const method = (scenario.request.method || 'GET').toUpperCase();
  const path = resolvePath(entry.sequence);
  const payload = buildPayload(entry.sequence);
  const tenant = chooseTenant(entry);
  const headers = {};
  if (tenant.header) {
    headers[tenant.header] = tenant.value;
  }
  if (payload !== null) {
    headers['Content-Type'] = 'application/json';
  }
  return {
    method,
    path,
    body: payload,
    headers,
    include_in_metrics: entry.include_in_metrics !== false,
  };
}

const vuState = Array.from({ length: concurrency }, () => ({ lastOffset: 0 }));

export default function () {
  const vuIndex = (__VU || 1) - 1;
  const iteration = __ITER || 0;
  const index = vuIndex + iteration * concurrency;
  if (index >= totalEntries) {
    sleep(1);
    return;
  }
  const entry = planEntries[index];
  const state = vuState[vuIndex];
  const delta = Math.max(0, entry.offset_s - state.lastOffset);
  if (delta > 0) {
    sleep(delta);
  }
  state.lastOffset = entry.offset_s;
  const request = resolveRequest(entry);
  const body = request.body === null ? null : JSON.stringify(request.body);
  http.request(request.method, `${BASE_URL}${request.path}`, body, {
    headers: request.headers,
    tags: {
      scenario: scenario.id || scenario.name || SCENARIO_ID,
      stage: entry.stage,
      include: String(request.include_in_metrics),
    },
  });
}