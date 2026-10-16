package com.classroomfacecheckin.business.compatibility;

import org.springframework.boot.context.properties.ConfigurationProperties;

@ConfigurationProperties(prefix = "compatibility")
public record CompatibilityProperties(
        boolean enabled,
        int maxImageBytes,
        int checkinsPerMinute,
        String facebankIdTemplate) {

    public CompatibilityProperties {
        if (maxImageBytes <= 0) {
            maxImageBytes = 5_000_000;
        }
        if (checkinsPerMinute <= 0) {
            checkinsPerMinute = 30;
        }
        if (facebankIdTemplate == null || facebankIdTemplate.isBlank()) {
            facebankIdTemplate = "course-%d-v1";
        }
    }
}
