package com.asterion.control;

/** Serializes native admission, cancellation and handoff between workspace and WSS requests. */
final class InferenceGate {
    static final class Request {
        private volatile boolean cancelled;
        private boolean started;
        boolean isCancelled() { return cancelled; }
    }

    private Request active;
    private final Runnable resetNative, abortNative;

    InferenceGate(Runnable resetNative, Runnable abortNative) {
        this.resetNative = resetNative;
        this.abortNative = abortNative;
    }

    synchronized void begin(Request request) throws InterruptedException {
        if (request.isCancelled()) throw new InterruptedException("user_cancelled");
        if (active != null) throw new IllegalStateException("on_device_inference_already_running");
        if (request.started) throw new IllegalStateException("generation_request_already_used");
        resetNative.run();
        request.started = true;
        active = request;
    }

    synchronized void cancel(Request request) {
        if (request.isCancelled()) return;
        request.cancelled = true;
        if (active == request) abortNative.run();
    }

    synchronized void end(Request request) {
        if (active == request) active = null;
    }

    synchronized boolean busy() { return active != null; }
}
