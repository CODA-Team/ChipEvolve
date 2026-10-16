## Platform execution ownership

The generated build/evaluation helpers submit to Execution Foundation and wait
for the terminal result under the existing experiment deadline. Start each
helper once, keep its command session, and wait on that same command session.
Queued work is a valid resource wait; repeated model turns calling the run API,
listing the queue, or inspecting unrelated host processes do not advance it.
Execution Foundation owns resource reservation, progress monitoring and cleanup.

While a helper is queued or running, keep its source and resource profile
unchanged. Continue independent source reasoning only when it cannot mutate the
submitted candidate. Do not launch a duplicate helper or replace the managed
experiment with a host EDA command. On an actual terminal infrastructure failure,
report the run identity, failure receipt and required capacity to the parent;
preserve the source for a platform-managed retry. Placement mechanisms, native
metrics, diagnosis, trial handling and promotion remain your original task.
