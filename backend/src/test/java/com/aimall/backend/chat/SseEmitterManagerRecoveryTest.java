package com.aimall.backend.chat;
import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;
import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.*;

class SseEmitterManagerRecoveryTest {
    @Test void completingAnOldSocketMustNotRemoveTheNewSocketsHeartbeat() throws Exception {
        var manager = new SseEmitterManager();
        var old = mock(SseEmitter.class); var fresh = mock(SseEmitter.class);
        var callback = ArgumentCaptor.forClass(Runnable.class);
        manager.register(1L, 7L, old);
        verify(old).onCompletion(callback.capture());
        manager.register(1L, 7L, fresh);
        callback.getValue().run();
        manager.heartbeat();
        verify(fresh).send(any(SseEmitter.SseEventBuilder.class));
    }
}
