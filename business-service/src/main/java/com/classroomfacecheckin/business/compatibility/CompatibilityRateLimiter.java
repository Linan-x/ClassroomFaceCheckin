package com.classroomfacecheckin.business.compatibility;

import java.time.Duration;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.stereotype.Component;
import org.springframework.web.server.ResponseStatusException;
import static org.springframework.http.HttpStatus.TOO_MANY_REQUESTS;

@Component
class CompatibilityRateLimiter {
    private final StringRedisTemplate redis;
    private final CompatibilityProperties properties;

    CompatibilityRateLimiter(StringRedisTemplate redis, CompatibilityProperties properties) {
        this.redis = redis;
        this.properties = properties;
    }

    void check(String clientKey) {
        String key = "attendance:compat:rate:" + Integer.toHexString(clientKey.hashCode())
                + ":" + System.currentTimeMillis() / 60_000;
        Long count = redis.opsForValue().increment(key);
        if (count != null && count == 1) {
            redis.expire(key, Duration.ofMinutes(2));
        }
        if (count == null || count > properties.checkinsPerMinute()) {
            throw new ResponseStatusException(TOO_MANY_REQUESTS, "Too many check-in uploads.");
        }
    }
}
