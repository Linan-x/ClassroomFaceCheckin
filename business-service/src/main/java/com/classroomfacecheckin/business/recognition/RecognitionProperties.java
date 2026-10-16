package com.classroomfacecheckin.business.recognition;

import java.net.URI;
import org.springframework.boot.context.properties.ConfigurationProperties;

@ConfigurationProperties(prefix = "recognition")
public record RecognitionProperties(
        boolean enabled,
        URI baseUrl,
        String sharedToken,
        int connectTimeoutMs,
        int readTimeoutMs) {

    public RecognitionProperties {
        if (connectTimeoutMs <= 0 || readTimeoutMs <= 0) {
            throw new IllegalArgumentException("Recognition timeouts must be positive.");
        }
    }
}
