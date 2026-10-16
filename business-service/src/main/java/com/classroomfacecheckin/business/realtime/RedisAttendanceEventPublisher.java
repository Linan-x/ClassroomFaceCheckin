package com.classroomfacecheckin.business.realtime;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.util.List;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.CopyOnWriteArrayList;
import java.util.function.Consumer;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.data.redis.connection.Message;
import org.springframework.data.redis.connection.MessageListener;
import org.springframework.stereotype.Component;

@Component
class RedisAttendanceEventPublisher implements AttendanceEventPublisher, MessageListener {
    static final String CHANNEL = "attendance:events";
    private final StringRedisTemplate redis;
    private final ObjectMapper objectMapper;
    private final RealtimeProperties properties;
    private final Map<Long, CopyOnWriteArrayList<Consumer<AttendanceEvent>>> subscribers = new ConcurrentHashMap<>();

    RedisAttendanceEventPublisher(
            StringRedisTemplate redis, ObjectMapper objectMapper, RealtimeProperties properties) {
        this.redis = redis;
        this.objectMapper = objectMapper;
        this.properties = properties;
    }

    @Override
    public void publish(AttendanceEvent event) {
        if (!properties.enabled()) {
            return;
        }
        String json = serialize(event);
        String key = eventKey(event.sessionId());
        redis.opsForList().rightPush(key, json);
        redis.opsForList().trim(key, -properties.maxEventsPerSession(), -1);
        redis.convertAndSend(CHANNEL, json);
    }

    @Override
    public List<AttendanceEvent> recent(Long sessionId) {
        if (!properties.enabled()) {
            return List.of();
        }
        List<String> events = redis.opsForList().range(eventKey(sessionId), 0, -1);
        return events == null ? List.of() : events.stream().map(this::deserialize).toList();
    }

    @Override
    public AutoCloseable subscribe(Long sessionId, Consumer<AttendanceEvent> subscriber) {
        subscribers.computeIfAbsent(sessionId, ignored -> new CopyOnWriteArrayList<>()).add(subscriber);
        return () -> subscribers.computeIfPresent(sessionId, (ignored, entries) -> {
            entries.remove(subscriber);
            return entries.isEmpty() ? null : entries;
        });
    }

    @Override
    public void onMessage(Message message, byte[] pattern) {
        AttendanceEvent event = deserialize(new String(message.getBody(), java.nio.charset.StandardCharsets.UTF_8));
        for (Consumer<AttendanceEvent> subscriber : subscribers.getOrDefault(event.sessionId(), new CopyOnWriteArrayList<>())) {
            subscriber.accept(event);
        }
    }

    private String eventKey(Long sessionId) {
        return "attendance:session:" + sessionId + ":events";
    }

    private String serialize(AttendanceEvent event) {
        try {
            return objectMapper.writeValueAsString(event);
        } catch (JsonProcessingException exception) {
            throw new IllegalStateException("Cannot serialize attendance event.", exception);
        }
    }

    private AttendanceEvent deserialize(String event) {
        try {
            return objectMapper.readValue(event, AttendanceEvent.class);
        } catch (JsonProcessingException exception) {
            throw new IllegalStateException("Cannot deserialize attendance event.", exception);
        }
    }
}
