package com.classroomfacecheckin.business.realtime;

import java.util.List;
import java.util.function.Consumer;

public interface AttendanceEventPublisher {
    void publish(AttendanceEvent event);

    List<AttendanceEvent> recent(Long sessionId);

    AutoCloseable subscribe(Long sessionId, Consumer<AttendanceEvent> subscriber);
}
