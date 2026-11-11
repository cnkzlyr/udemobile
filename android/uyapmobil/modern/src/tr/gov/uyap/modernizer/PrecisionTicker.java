package tr.gov.uyap.modernizer;


/**
 * Windows'ta Thread.sleep / parkNanos / ScheduledExecutor zaman cozunurlugu ~15.6 ms'ye takilabiliyor
 * (olculen: 64 Hz). Bu sinif kaba beklemeyi uyku ile, son ~2.5 ms'yi kisa bir meşgul bekleme (spin)
 * ile yaparak 120/144/240 Hz'de duzgun kare araligi saglar. Sadece animasyon suresince (~200 ms) calisir.
 */
final class PrecisionTicker {
    private static final long SPIN_NANOS = 2_000_000L;

    static final class Handle {
        private volatile boolean cancelled;
        void cancel(boolean ignored) { cancelled = true; }
    }

    static Handle schedule(Runnable task, long periodNanos) {
        final Handle h = new Handle();
        Thread t = new Thread(() -> {
            long next = System.nanoTime();
            boolean coarseSleep = false;
            while (!h.cancelled) {
                task.run();
                next += periodNanos;
                long now = System.nanoTime();
                if (next < now) {
                    // Geride kalindi: biriken kareleri atla, ritmi koru
                    next = now + periodNanos - ((now - next) % periodNanos);
                }
                // parkNanos Windows'ta 15.6 ms'ye yuvarlanir; Thread.sleep(1) ise JDK'nin 1 ms zamanlayici
                // cozunurlugunu kullanir. Son ~2 ms spin ile hassas yakalanir.
                while (!h.cancelled) {
                    long remaining = next - System.nanoTime();
                    if (remaining <= 0) break;
                    if (remaining > SPIN_NANOS && !coarseSleep) {
                        long s0 = System.nanoTime();
                        try { Thread.sleep(1); } catch (InterruptedException e) { return; }
                        // Uyku beklenenden cok uzadiysa (zamanlayici cozunurlugu kaba) saf spin'e gec
                        if (System.nanoTime() - s0 > 4_000_000L) coarseSleep = true;
                    } else {
                        Thread.onSpinWait();
                    }
                }
            }
        }, "Modernizer-FrameTicker");
        t.setDaemon(true);
        t.setPriority(Thread.MAX_PRIORITY);
        t.start();
        return h;
    }

    private PrecisionTicker() {}
}
