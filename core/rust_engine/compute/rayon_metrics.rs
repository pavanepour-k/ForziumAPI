use serde::Serialize;
use std::sync::atomic::{AtomicU64, AtomicUsize, Ordering};
use std::sync::{Mutex, OnceLock};
use std::time::{Duration, Instant};
use thiserror::Error;

/// Lazily constructed global metrics collector for the Rayon thread pool.
fn metrics() -> &'static RayonMetrics {
    static METRICS: OnceLock<RayonMetrics> = OnceLock::new();
    METRICS.get_or_init(RayonMetrics::default)
}

/// Guard returned when a Rayon task begins executing.
///
/// Dropping the guard records task completion and time spent executing.
pub struct RayonTaskGuard {
    metrics: &'static RayonMetrics,
    start: Instant,
}

impl RayonTaskGuard {
    fn new(metrics: &'static RayonMetrics) -> Self {
        let total_threads = rayon::current_num_threads();
        if total_threads > 0 {
            update_max_usize(&metrics.max_threads_observed, total_threads);
        }
        let active = metrics.active_workers.fetch_add(1, Ordering::AcqRel) + 1;
        update_max_usize(&metrics.max_active_workers, active);
        metrics.tasks_started.fetch_add(1, Ordering::Relaxed);
        Self {
            metrics,
            start: Instant::now(),
        }
    }
}

impl Drop for RayonTaskGuard {
    fn drop(&mut self) {
        let elapsed = self.start.elapsed();
        let nanos = duration_to_nanos(elapsed);
        self.metrics
            .busy_time_nanos
            .fetch_add(nanos, Ordering::Relaxed);
        update_max_u64(&self.metrics.max_task_time_nanos, nanos);
        update_min_u64(&self.metrics.min_task_time_nanos, nanos);
        self.metrics.tasks_completed.fetch_add(1, Ordering::Relaxed);
        self.metrics.active_workers.fetch_sub(1, Ordering::AcqRel);
    }
}

/// Snapshot of thread-pool utilisation statistics.
#[derive(Debug, Clone, Serialize, PartialEq)]
pub struct RayonPoolSnapshot {
    /// Maximum number of Rayon workers observed during the measurement window.
    pub observed_threads: usize,
    /// Highest number of concurrent Rayon workers recorded.
    pub max_active_threads: usize,
    /// Average number of busy workers across the observation window.
    pub mean_active_threads: f64,
    /// Percentage of observed worker capacity utilised on average.
    pub utilization_percent: f64,
    /// Peak saturation (max active / observed threads).
    pub peak_saturation: f64,
    /// Total number of tasks started.
    pub total_tasks_started: u64,
    /// Total number of tasks completed.
    pub total_tasks_completed: u64,
    /// Mean task duration in microseconds.
    pub mean_task_duration_us: f64,
    /// Longest task duration in microseconds.
    pub max_task_duration_us: f64,
    /// Shortest task duration in microseconds.
    pub min_task_duration_us: f64,
    /// Aggregate busy time across all workers in seconds.
    pub busy_time_seconds: f64,
    /// Total observation window in seconds.
    pub observation_seconds: f64,
}

impl RayonPoolSnapshot {
    fn from_metrics(metrics: &RayonMetrics) -> Self {
        let observed_threads = metrics.max_threads_observed.load(Ordering::Relaxed).max(1);
        let max_active = metrics.max_active_workers.load(Ordering::Relaxed);
        let total_started = metrics.tasks_started.load(Ordering::Relaxed);
        let total_completed = metrics.tasks_completed.load(Ordering::Relaxed);
        let busy_nanos = metrics.busy_time_nanos.load(Ordering::Relaxed);
        let max_task_nanos = metrics.max_task_time_nanos.load(Ordering::Relaxed);
        let min_task_nanos = metrics.min_task_time_nanos.load(Ordering::Relaxed);

        let elapsed = metrics.observation_elapsed();
        let elapsed_secs = elapsed.as_secs_f64();
        let busy_secs = busy_nanos as f64 / 1_000_000_000.0;
        let mean_active_threads = if elapsed_secs > 0.0 {
            busy_secs / elapsed_secs
        } else {
            0.0
        };
        let utilization_percent = if observed_threads > 0 {
            (mean_active_threads / observed_threads as f64) * 100.0
        } else {
            0.0
        };
        let mean_task_duration_us = if total_completed > 0 {
            (busy_nanos as f64 / total_completed as f64) / 1_000.0
        } else {
            0.0
        };
        let max_task_duration_us = max_task_nanos as f64 / 1_000.0;
        let min_task_duration_us = if total_completed > 0 && min_task_nanos != u64::MAX {
            min_task_nanos as f64 / 1_000.0
        } else {
            0.0
        };
        let peak_saturation = if observed_threads > 0 {
            max_active as f64 / observed_threads as f64
        } else {
            0.0
        };

        Self {
            observed_threads,
            max_active_threads: max_active,
            mean_active_threads,
            utilization_percent,
            peak_saturation,
            total_tasks_started: total_started,
            total_tasks_completed: total_completed,
            mean_task_duration_us,
            max_task_duration_us,
            min_task_duration_us,
            busy_time_seconds: busy_secs,
            observation_seconds: elapsed_secs,
        }
    }
}

/// Error returned when attempting to snapshot or reset metrics at an invalid time.
#[derive(Debug, Error, PartialEq, Eq)]
pub enum RayonMetricsError {
    /// Metrics reset requested while tasks are still executing.
    #[error("cannot reset rayon metrics while {0} worker(s) are active")]
    ActiveWorkers(usize),
}

struct RayonMetrics {
    active_workers: AtomicUsize,
    max_active_workers: AtomicUsize,
    max_threads_observed: AtomicUsize,
    tasks_started: AtomicU64,
    tasks_completed: AtomicU64,
    busy_time_nanos: AtomicU64,
    max_task_time_nanos: AtomicU64,
    min_task_time_nanos: AtomicU64,
    observation_start: Mutex<Instant>,
}

impl Default for RayonMetrics {
    fn default() -> Self {
        Self {
            active_workers: AtomicUsize::new(0),
            max_active_workers: AtomicUsize::new(0),
            max_threads_observed: AtomicUsize::new(0),
            tasks_started: AtomicU64::new(0),
            tasks_completed: AtomicU64::new(0),
            busy_time_nanos: AtomicU64::new(0),
            max_task_time_nanos: AtomicU64::new(0),
            min_task_time_nanos: AtomicU64::new(u64::MAX),
            observation_start: Mutex::new(Instant::now()),
        }
    }
}

impl RayonMetrics {
    fn observation_elapsed(&self) -> Duration {
        let start = self
            .observation_start
            .lock()
            .unwrap_or_else(|poisoned| {
                // Recover from poisoned mutex by clearing poison state
                poisoned.into_inner()
            });
        start.elapsed()
    }

    fn reset_unchecked(&self) {
        self.max_active_workers.store(0, Ordering::Relaxed);
        self.max_threads_observed.store(0, Ordering::Relaxed);
        self.tasks_started.store(0, Ordering::Relaxed);
        self.tasks_completed.store(0, Ordering::Relaxed);
        self.busy_time_nanos.store(0, Ordering::Relaxed);
        self.max_task_time_nanos.store(0, Ordering::Relaxed);
        self.min_task_time_nanos.store(u64::MAX, Ordering::Relaxed);
        let mut start = self
            .observation_start
            .lock()
            .unwrap_or_else(|poisoned| {
                // Recover from poisoned mutex by clearing poison state
                poisoned.into_inner()
            });
        *start = Instant::now();
    }
}

/// Register the start of a Rayon worker task and return a guard that records
/// completion statistics.
pub fn track_task() -> RayonTaskGuard {
    RayonTaskGuard::new(metrics())
}

/// Retrieve the current utilisation snapshot without mutating counters.
pub fn snapshot() -> RayonPoolSnapshot {
    RayonPoolSnapshot::from_metrics(metrics())
}

/// Retrieve utilisation metrics and reset counters. Fails if Rayon tasks are active.
pub fn snapshot_and_reset() -> Result<RayonPoolSnapshot, RayonMetricsError> {
    let metrics = metrics();
    let active = metrics.active_workers.load(Ordering::SeqCst);
    if active != 0 {
        return Err(RayonMetricsError::ActiveWorkers(active));
    }
    let snapshot = RayonPoolSnapshot::from_metrics(metrics);
    metrics.reset_unchecked();
    Ok(snapshot)
}

/// Reset metrics counters back to zero. Fails if Rayon tasks are active.
pub fn reset_metrics() -> Result<(), RayonMetricsError> {
    let metrics = metrics();
    let active = metrics.active_workers.load(Ordering::SeqCst);
    if active != 0 {
        return Err(RayonMetricsError::ActiveWorkers(active));
    }
    metrics.reset_unchecked();
    Ok(())
}

fn duration_to_nanos(duration: Duration) -> u64 {
    duration
        .as_nanos()
        .min(u128::from(u64::MAX))
        .try_into()
        .unwrap_or(u64::MAX)
}

fn update_max_usize(target: &AtomicUsize, value: usize) {
    let mut current = target.load(Ordering::Relaxed);
    while value > current {
        match target.compare_exchange(current, value, Ordering::Relaxed, Ordering::Relaxed) {
            Ok(_) => break,
            Err(previous) => current = previous,
        }
    }
}

fn update_max_u64(target: &AtomicU64, value: u64) {
    let mut current = target.load(Ordering::Relaxed);
    while value > current {
        match target.compare_exchange(current, value, Ordering::Relaxed, Ordering::Relaxed) {
            Ok(_) => break,
            Err(previous) => current = previous,
        }
    }
}

fn update_min_u64(target: &AtomicU64, value: u64) {
    let mut current = target.load(Ordering::Relaxed);
    while value < current {
        match target.compare_exchange(current, value, Ordering::Relaxed, Ordering::Relaxed) {
            Ok(_) => break,
            Err(previous) => current = previous,
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::thread;
    use std::time::Duration;

    #[test]
    fn guard_records_task_counts() {
        reset_metrics().unwrap();
        {
            let _g = track_task();
        }
        let snapshot = snapshot();
        assert_eq!(snapshot.total_tasks_started, 1);
        assert_eq!(snapshot.total_tasks_completed, 1);
        assert!(snapshot.mean_task_duration_us >= 0.0);
    }

    #[test]
    fn parallel_tasks_update_concurrency_metrics() {
        reset_metrics().unwrap();
        let handles: Vec<_> = (0..rayon::current_num_threads().max(4))
            .map(|_| {
                thread::spawn(|| {
                    let _guard = track_task();
                    std::thread::sleep(Duration::from_millis(5));
                })
            })
            .collect();
        for handle in handles {
            handle.join().unwrap();
        }
        let snapshot = snapshot();
        assert!(snapshot.max_active_threads >= 1);
        assert!(snapshot.total_tasks_completed as usize >= 4);
        assert!(snapshot.busy_time_seconds > 0.0);
    }

    #[test]
    fn cannot_reset_when_active() {
        reset_metrics().unwrap();
        let guard = track_task();
        let err = reset_metrics().unwrap_err();
        assert_eq!(err, RayonMetricsError::ActiveWorkers(1));
        drop(guard);
        reset_metrics().unwrap();
    }
}
