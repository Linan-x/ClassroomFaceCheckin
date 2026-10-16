package com.classroomfacecheckin.business.realtime;

import java.io.IOException;
import java.util.List;
import org.springframework.http.MediaType;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;
import org.springframework.web.server.ResponseStatusException;
import static org.springframework.http.HttpStatus.FORBIDDEN;
import static org.springframework.http.HttpStatus.NOT_FOUND;

@RestController
@RequestMapping("/api/v1/checkin-sessions")
public class AttendanceSseController {
    private final AttendanceEventPublisher events;
    private final RealtimeProperties properties;

    public AttendanceSseController(AttendanceEventPublisher events, RealtimeProperties properties) {
        this.events = events;
        this.properties = properties;
    }

    @GetMapping(value = "/{sessionId}/events", produces = MediaType.TEXT_EVENT_STREAM_VALUE)
    public SseEmitter events(
            @org.springframework.web.bind.annotation.PathVariable Long sessionId,
            @RequestParam("token") String token,
            @RequestHeader(value = "Last-Event-ID", required = false) String lastEventId) {
        authorize(token);
        SseEmitter emitter = new SseEmitter(30_000L);
        List<AttendanceEvent> backlog = events.recent(sessionId);
        try {
            for (AttendanceEvent event : backlog) {
                emitter.send(SseEmitter.event().name(event.type()).id(String.valueOf(event.attendanceRecordId())).data(event));
            }
        } catch (IOException exception) {
            emitter.completeWithError(exception);
            return emitter;
        }
        AutoCloseable subscription = events.subscribe(sessionId, event -> {
            try {
                emitter.send(SseEmitter.event().name(event.type()).id(String.valueOf(event.attendanceRecordId())).data(event));
            } catch (IOException exception) {
                emitter.completeWithError(exception);
            }
        });
        emitter.onCompletion(() -> close(subscription));
        emitter.onTimeout(() -> {
            close(subscription);
            emitter.complete();
        });
        return emitter;
    }

    private void authorize(String token) {
        if (!properties.enabled()) {
            throw new ResponseStatusException(NOT_FOUND, "Realtime monitoring is disabled.");
        }
        if (properties.dashboardToken() == null || properties.dashboardToken().isBlank()
                || !properties.dashboardToken().equals(token)) {
            throw new ResponseStatusException(FORBIDDEN, "A valid dashboard token is required.");
        }
    }

    private void close(AutoCloseable subscription) {
        try {
            subscription.close();
        } catch (Exception exception) {
            throw new IllegalStateException("Cannot close realtime subscription.", exception);
        }
    }
}
