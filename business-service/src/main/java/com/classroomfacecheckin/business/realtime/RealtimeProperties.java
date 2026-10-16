package com.classroomfacecheckin.business.realtime;

import org.springframework.boot.context.properties.ConfigurationProperties;

@ConfigurationProperties(prefix = "realtime")
public record RealtimeProperties(boolean enabled, int maxEventsPerSession, String dashboardToken) {
    public RealtimeProperties {
        if (maxEventsPerSession <= 0) {
            maxEventsPerSession = 200;
        }
    }
}
